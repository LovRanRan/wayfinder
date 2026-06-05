"""FastAPI sandbox worker for bounded test execution."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, status

from wayfinder.sandbox.schemas import (
    SandboxHealthResult,
    SandboxTestObservation,
    SandboxTestRequest,
)

_DEFAULT_ALLOWED_ROOTS = (
    Path("/repo-cache/repos"),
    Path("/data/repos"),
    Path("/tmp/wayfinder/repos"),
)
_DEFAULT_TEMP_ROOT = Path("/tmp/wayfinder-sandbox")
_SHELL_META_CHARS = frozenset({"\n", "\r", "\0", ";", "&", "|", "`", "$", "<", ">", "!"})
_DENIED_FILTER_TOKENS = (
    "pip install",
    "uv pip",
    "uv add",
    "npm install",
    "pnpm install",
    "yarn add",
    "curl ",
    "wget ",
    "python -c",
    "bash ",
    " sh ",
    "rm -rf",
)
_IGNORED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}


@dataclass(frozen=True)
class SandboxWorkerConfig:
    allowed_roots: tuple[Path, ...] = _DEFAULT_ALLOWED_ROOTS
    temp_root: Path = _DEFAULT_TEMP_ROOT
    token: str | None = None
    max_output_bytes: int = 12000


def create_app(config: SandboxWorkerConfig | None = None) -> FastAPI:
    worker_config = config or sandbox_config_from_env(os.environ)
    app = FastAPI(
        title="wayfinder-test-sandbox",
        version="0.1.0",
        description="Bounded test runner worker for Wayfinder verifier claims.",
    )

    def require_token(
        x_wayfinder_sandbox_token: str | None = Header(default=None),
    ) -> None:
        expected = worker_config.token
        if expected is None:
            return
        if x_wayfinder_sandbox_token != expected:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid sandbox token",
            )

    @app.get("/health", response_model=SandboxHealthResult)
    def health() -> SandboxHealthResult:
        return SandboxHealthResult(status="ok")

    @app.post(
        "/run-test",
        response_model=SandboxTestObservation,
        dependencies=[Depends(require_token)],
    )
    def run_test(request: SandboxTestRequest) -> SandboxTestObservation:
        return run_sandboxed_test(request, worker_config)

    return app


def sandbox_config_from_env(env: Mapping[str, str]) -> SandboxWorkerConfig:
    return SandboxWorkerConfig(
        allowed_roots=_allowed_roots_from_env(env.get("WAYFINDER_SANDBOX_ALLOWED_ROOTS")),
        temp_root=Path(
            env.get("WAYFINDER_SANDBOX_TEMP_ROOT", str(_DEFAULT_TEMP_ROOT))
        ).expanduser(),
        token=_optional_env_value(env.get("WAYFINDER_SANDBOX_TOKEN")),
        max_output_bytes=_int_env_value(env.get("WAYFINDER_SANDBOX_MAX_OUTPUT_BYTES"), 12000),
    )


def run_sandboxed_test(
    request: SandboxTestRequest,
    config: SandboxWorkerConfig,
) -> SandboxTestObservation:
    denied_reason = _denied_reason(request, config)
    if denied_reason is not None:
        return SandboxTestObservation(
            test_ref=request.test_ref,
            status="tool_error",
            output=f"Sandbox denied request: {denied_reason}",
            cleanup_done=True,
            denied_reason=denied_reason,
        )

    source_path = Path(request.path).expanduser().resolve()
    config.temp_root.mkdir(parents=True, exist_ok=True)
    workdir = Path(
        tempfile.mkdtemp(
            prefix=f"wayfinder-{_safe_ref(request.test_ref)}-",
            dir=str(config.temp_root),
        )
    )
    repo_workdir = workdir / "repo"
    cleanup_done = False
    try:
        shutil.copytree(
            source_path,
            repo_workdir,
            ignore=shutil.ignore_patterns(*sorted(_IGNORED_DIRS)),
        )
        command = _command_for_request(request)
        completed = subprocess.run(
            command,
            cwd=repo_workdir,
            text=True,
            capture_output=True,
            timeout=request.timeout_seconds,
            check=False,
        )
        output = _bounded_output(
            _combined_output(completed.stdout, completed.stderr),
            min(request.max_output_bytes, config.max_output_bytes),
        )
        return _observation_from_completed_process(
            request=request,
            returncode=completed.returncode,
            output=output,
            cleanup_done=True,
        )
    except subprocess.TimeoutExpired as exc:
        output = _bounded_output(
            _combined_output(_string_or_empty(exc.stdout), _string_or_empty(exc.stderr)),
            min(request.max_output_bytes, config.max_output_bytes),
        )
        return SandboxTestObservation(
            test_ref=request.test_ref,
            status="timed_out",
            output=output or "sandbox test timed out",
            cleanup_done=True,
        )
    except Exception as exc:  # pragma: no cover - defensive worker boundary
        return SandboxTestObservation(
            test_ref=request.test_ref,
            status="tool_error",
            output=str(exc) or type(exc).__name__,
            cleanup_done=cleanup_done,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        cleanup_done = not workdir.exists()


def _denied_reason(request: SandboxTestRequest, config: SandboxWorkerConfig) -> str | None:
    if not _tool_matches_framework(request):
        return f"{request.tool_name} is not valid for {request.framework}"

    source_path = Path(request.path).expanduser().resolve()
    if not source_path.exists() or not source_path.is_dir():
        return "repo path does not exist or is not a directory"

    if not _is_under_allowed_root(source_path, config.allowed_roots):
        return "repo path is outside sandbox allowed roots"

    test_filter = request.test_filter.strip()
    if any(character in test_filter for character in _SHELL_META_CHARS):
        return "test filter contains shell metacharacters"

    lowered = f" {test_filter.lower()} "
    if any(token in lowered for token in _DENIED_FILTER_TOKENS):
        return "test filter contains denied command token"

    path_part = _path_part_from_filter(test_filter)
    if Path(path_part).is_absolute():
        return "absolute test target paths are denied"
    if ".." in Path(path_part).parts:
        return "path traversal is denied"

    return None


def _tool_matches_framework(request: SandboxTestRequest) -> bool:
    if request.tool_name == "run_pytest":
        return request.framework == "pytest"
    if request.tool_name == "run_jest":
        return request.framework == "jest"
    return request.framework in ("pytest", "jest")


def _is_under_allowed_root(path: Path, allowed_roots: Sequence[Path]) -> bool:
    resolved_roots = [root.expanduser().resolve() for root in allowed_roots]
    return any(path == root or root in path.parents for root in resolved_roots)


def _command_for_request(request: SandboxTestRequest) -> list[str]:
    target = request.test_filter.removeprefix("jest:").strip()
    if request.framework == "pytest":
        return [sys.executable, "-m", "pytest", target, "-q"]
    return ["npm", "test", "--", "--runInBand", target]


def _observation_from_completed_process(
    *,
    request: SandboxTestRequest,
    returncode: int,
    output: str,
    cleanup_done: bool,
) -> SandboxTestObservation:
    passed, failed, skipped = _parse_counts(output)
    failures = _parse_failures(output)
    return SandboxTestObservation(
        test_ref=request.test_ref,
        status="passed" if returncode == 0 else "failed",
        output=output,
        passed=passed,
        failed=failed,
        skipped=skipped,
        failures=failures,
        cleanup_done=cleanup_done,
    )


def _parse_counts(output: str) -> tuple[int, int, int]:
    return (
        _first_count(output, "passed"),
        _first_count(output, "failed"),
        _first_count(output, "skipped"),
    )


def _first_count(output: str, label: str) -> int:
    match = re.search(rf"(\d+)\s+{re.escape(label)}", output)
    return int(match.group(1)) if match else 0


def _parse_failures(output: str) -> list[str]:
    failures: list[str] = []
    for line in output.splitlines():
        if line.startswith("FAILED "):
            failures.append(line.removeprefix("FAILED ").split(" - ", 1)[0].strip())
    return failures[:10]


def _combined_output(stdout: str, stderr: str) -> str:
    if stdout and stderr:
        return f"{stdout.rstrip()}\n{stderr.rstrip()}"
    return stdout or stderr


def _bounded_output(output: str, max_output_bytes: int) -> str:
    encoded = output.encode("utf-8", errors="replace")
    if len(encoded) <= max_output_bytes:
        return output
    truncated = encoded[:max_output_bytes].decode("utf-8", errors="replace")
    return f"{truncated}\n[wayfinder sandbox output truncated]"


def _path_part_from_filter(test_filter: str) -> str:
    return test_filter.removeprefix("jest:").split("::", 1)[0].strip()


def _safe_ref(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value)[:64] or "test"


def _string_or_empty(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value if isinstance(value, str) else ""


def _allowed_roots_from_env(raw: str | None) -> tuple[Path, ...]:
    if not raw:
        return _DEFAULT_ALLOWED_ROOTS
    roots = tuple(Path(item.strip()).expanduser() for item in raw.split(",") if item.strip())
    return roots or _DEFAULT_ALLOWED_ROOTS


def _optional_env_value(raw: str | None) -> str | None:
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None


def _int_env_value(raw: str | None, default: int) -> int:
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(256, min(value, 64000))


app = create_app()
