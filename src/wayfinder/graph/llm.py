"""Small LLM client boundary for routing and grounded synthesis."""

from __future__ import annotations

import contextvars
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol, cast

# Per-run LLM token accumulator. Set inside the graph worker thread via
# `start_token_capture`; every OpenAI call adds its usage. Read back with
# `collected_token_usage` to surface cost in trace_metadata.
_TOKEN_USAGE: contextvars.ContextVar[dict[str, int] | None] = contextvars.ContextVar(
    "wayfinder_token_usage", default=None
)


def start_token_capture() -> None:
    """Begin accumulating LLM token usage in the current context."""
    _TOKEN_USAGE.set({"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})


def collected_token_usage() -> dict[str, int] | None:
    """Return the accumulated token usage for the current context, if capturing."""
    return _TOKEN_USAGE.get()


def _record_token_usage(body: dict[str, object]) -> None:
    bucket = _TOKEN_USAGE.get()
    if bucket is None:
        return
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, (int, float)):
            bucket[key] += int(value)


class LLMCallError(Exception):
    """Raised when an LLM call cannot produce usable text."""


class LLMClient(Protocol):
    def complete(self, *, instructions: str, input_text: str) -> str: ...


@dataclass(frozen=True)
class OpenAIResponsesClient:
    """Minimal sync client for the OpenAI Responses API."""

    api_key: str
    model: str
    timeout_seconds: float = 30.0
    max_output_tokens: int = 1200
    api_url: str = "https://api.openai.com/v1/responses"

    def complete(self, *, instructions: str, input_text: str) -> str:
        if not self.api_key.strip():
            raise LLMCallError("OPENAI_API_KEY is missing")
        if not self.model.strip():
            raise LLMCallError("OpenAI model is missing")

        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": input_text,
            "max_output_tokens": self.max_output_tokens,
        }
        request = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            response = urllib.request.urlopen(request, timeout=self.timeout_seconds)
        except urllib.error.HTTPError as exc:
            raise LLMCallError(_http_error_message(exc)) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LLMCallError(f"OpenAI Responses API call failed: {exc}") from exc

        try:
            with response:
                raw_body = response.read().decode("utf-8")
        except TimeoutError as exc:
            raise LLMCallError("OpenAI Responses API response timed out") from exc

        try:
            body: object = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise LLMCallError("OpenAI Responses API returned invalid JSON") from exc

        if not isinstance(body, dict):
            raise LLMCallError("OpenAI Responses API returned a non-object response")

        _record_token_usage(cast(dict[str, object], body))
        text = extract_response_text(cast(dict[str, object], body)).strip()
        if not text:
            raise LLMCallError("OpenAI Responses API returned empty text")

        return text


def extract_response_text(response_body: dict[str, object]) -> str:
    output_text = response_body.get("output_text")
    if isinstance(output_text, str):
        return output_text

    output = response_body.get("output")
    if not isinstance(output, list):
        return ""

    texts: list[str] = []
    for output_item in cast(list[object], output):
        texts.extend(_texts_from_output_item(output_item))

    return "\n".join(text for text in texts if text.strip())


def _texts_from_output_item(output_item: object) -> list[str]:
    if not isinstance(output_item, dict):
        return []

    output_dict = cast(dict[str, object], output_item)
    direct_text = output_dict.get("text")
    if isinstance(direct_text, str):
        return [direct_text]

    content = output_dict.get("content")
    if not isinstance(content, list):
        return []

    texts: list[str] = []
    for content_item in cast(list[object], content):
        if not isinstance(content_item, dict):
            continue
        content_dict = cast(dict[str, object], content_item)
        text = content_dict.get("text")
        if isinstance(text, str):
            texts.append(text)

    return texts


def _http_error_message(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8")[:500]
    except Exception:
        body = ""

    suffix = f": {body}" if body else ""
    return f"OpenAI Responses API returned HTTP {exc.code}{suffix}"

