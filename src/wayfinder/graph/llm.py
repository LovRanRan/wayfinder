"""Small LLM client boundary for routing and grounded synthesis."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol, cast

# Per-run LLM token accumulator. A module-level, lock-guarded dict (rather than a
# contextvar) because LLM calls happen across LangGraph's internal worker threads,
# which a contextvar does not reliably cross. `start_token_capture` resets it at
# the start of a run; every OpenAI call adds its usage; `collected_token_usage`
# reads the total. NOTE: assumes runs execute sequentially (true for the eval
# harness); concurrent runs would share the accumulator.
_TOKEN_LOCK = threading.Lock()
_TOKEN_USAGE: dict[str, int] | None = None


def start_token_capture() -> None:
    """Begin (reset) accumulating LLM token usage for the current run."""
    global _TOKEN_USAGE
    with _TOKEN_LOCK:
        _TOKEN_USAGE = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def collected_token_usage() -> dict[str, int] | None:
    """Return a copy of the accumulated token usage, or None if not capturing."""
    with _TOKEN_LOCK:
        return dict(_TOKEN_USAGE) if _TOKEN_USAGE is not None else None


def stop_token_capture() -> dict[str, int] | None:
    """Read the accumulated usage and stop capturing."""
    global _TOKEN_USAGE
    with _TOKEN_LOCK:
        usage = dict(_TOKEN_USAGE) if _TOKEN_USAGE is not None else None
        _TOKEN_USAGE = None
        return usage


def _record_token_usage(body: dict[str, object]) -> None:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return
    with _TOKEN_LOCK:
        if _TOKEN_USAGE is None:
            return
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = usage.get(key)
            if isinstance(value, (int, float)):
                _TOKEN_USAGE[key] += int(value)


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

