"""Remote sandbox adapter for verifier test execution."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from wayfinder.graph.verifier import TestRunObservation, TestRunRequest
from wayfinder.sandbox.schemas import (
    SandboxHealthResult,
    SandboxTestObservation,
    SandboxTestRequest,
)


@dataclass(frozen=True)
class SandboxHealthCheck:
    ok: bool
    message: str


class RemoteSandboxTestRunner:
    def __init__(
        self,
        sandbox_url: str,
        *,
        token: str | None = None,
        request_timeout_seconds: float = 30.0,
        max_output_bytes: int = 12000,
    ) -> None:
        self.sandbox_url = sandbox_url.rstrip("/")
        self.token = token
        self.request_timeout_seconds = request_timeout_seconds
        self.max_output_bytes = max_output_bytes

    def run_test(self, request: TestRunRequest) -> TestRunObservation:
        payload = SandboxTestRequest(
            test_ref=request.test_ref,
            claim_refs=list(request.claim_refs),
            framework=request.framework,
            tool_name=request.tool_name,
            path=request.path,
            test_filter=request.test_filter,
            timeout_seconds=request.timeout_seconds,
            max_output_bytes=min(request.max_output_bytes, self.max_output_bytes),
            job_id=request.job_id,
            run_owner=request.run_owner,
            repo_url=request.repo_url,
        )
        try:
            response = _json_request(
                f"{self.sandbox_url}/run-test",
                method="POST",
                payload=payload.model_dump(mode="json"),
                token=self.token,
                timeout=self.request_timeout_seconds,
            )
            observation = SandboxTestObservation.model_validate(response)
        except Exception as exc:
            return TestRunObservation(
                test_ref=request.test_ref,
                status="tool_error",
                output=str(exc) or type(exc).__name__,
            )

        return TestRunObservation(
            test_ref=observation.test_ref,
            status=observation.status,
            output=observation.output,
            passed=observation.passed,
            failed=observation.failed,
            skipped=observation.skipped,
            failures=tuple(observation.failures),
        )


def check_sandbox_health(
    sandbox_url: str,
    *,
    token: str | None = None,
    timeout_seconds: float = 1.0,
) -> SandboxHealthCheck:
    try:
        payload = _json_request(
            f"{sandbox_url.rstrip('/')}/health",
            method="GET",
            payload=None,
            token=token,
            timeout=timeout_seconds,
        )
        health = SandboxHealthResult.model_validate(payload)
    except Exception as exc:
        return SandboxHealthCheck(ok=False, message=str(exc) or type(exc).__name__)

    if health.status != "ok":
        return SandboxHealthCheck(
            ok=False,
            message=health.message or "sandbox health returned non-ok status",
        )
    return SandboxHealthCheck(ok=True, message=health.message or "sandbox worker is healthy")


def _json_request(
    url: str,
    *,
    method: str,
    payload: dict[str, object] | None,
    token: str | None,
    timeout: float,
) -> object:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, data=data, method=method)
    request.add_header("accept", "application/json")
    if payload is not None:
        request.add_header("content-type", "application/json")
    if token is not None:
        request.add_header("x-wayfinder-sandbox-token", token)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"sandbox request failed with HTTP {exc.code}: {body}") from exc

    return json.loads(body) if body else {}
