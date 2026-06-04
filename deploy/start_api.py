from __future__ import annotations

import os
import signal
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MCPProcessSpec:
    name: str
    import_spec: str
    port: int


_READER_MCP_SERVERS = (
    MCPProcessSpec(
        name="repo_mapper",
        import_spec="mcp_repo_mapper.server:mcp",
        port=8101,
    ),
    MCPProcessSpec(
        name="ast_explorer",
        import_spec="mcp_ast_explorer.server:mcp",
        port=8102,
    ),
)


def main() -> None:
    venv_python = Path(".venv/bin/python")
    uvicorn = Path(".venv/bin/uvicorn")
    child_processes: list[subprocess.Popen[bytes]] = []

    try:
        if _start_reader_mcp_sidecars():
            child_processes = _start_mcp_processes(venv_python)
            _apply_reader_mcp_env_defaults()

        _run_api(uvicorn)
    finally:
        _terminate_processes(child_processes)


def _start_reader_mcp_sidecars() -> bool:
    raw = os.getenv("WAYFINDER_START_PROJECT5_HTTP_MCP", "")
    if raw.strip() == "":
        return False

    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _start_mcp_processes(python: Path) -> list[subprocess.Popen[bytes]]:
    processes: list[subprocess.Popen[bytes]] = []
    for spec in _READER_MCP_SERVERS:
        env = {
            **os.environ,
            "PORT": str(spec.port),
            "MCP_HOST": "127.0.0.1",
            "MCP_PATH": "/mcp",
            "MCP_STATELESS_HTTP": "1",
        }
        process = subprocess.Popen(
            [
                str(python),
                "deploy/run_fastmcp_http.py",
                spec.import_spec,
            ],
            env=env,
        )
        processes.append(process)
    return processes


def _apply_reader_mcp_env_defaults() -> None:
    os.environ.setdefault("WAYFINDER_ARCHITECTURE_SCANNER", "mcp_http")
    os.environ.setdefault("WAYFINDER_ENTRY_SCANNER", "mcp_http")
    os.environ.setdefault("WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL", "http://127.0.0.1:8101/mcp")
    os.environ.setdefault("WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL", "http://127.0.0.1:8102/mcp")


def _run_api(uvicorn: Path) -> None:
    command = [
        str(uvicorn),
        "wayfinder.api.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        os.getenv("PORT", "8000"),
    ]
    completed = subprocess.run(command, check=False)
    raise SystemExit(completed.returncode)


def _terminate_processes(processes: Sequence[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is not None:
            continue
        process.send_signal(signal.SIGTERM)

    for process in processes:
        if process.poll() is not None:
            continue
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    main()
