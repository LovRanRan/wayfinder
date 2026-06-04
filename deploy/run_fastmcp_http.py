from __future__ import annotations

import importlib
import os
import sys
from typing import Any, Protocol, cast


class FastMCPServer(Protocol):
    def run(
        self,
        transport: str | None = None,
        show_banner: bool | None = None,
        **transport_kwargs: Any,
    ) -> None: ...


def main() -> None:
    import_spec = _import_spec_from_args()
    server = _load_server(import_spec)
    server.run(
        transport="http",
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=_port_from_env(),
        path=os.getenv("MCP_PATH", "/mcp"),
        stateless_http=_bool_from_env("MCP_STATELESS_HTTP", default=True),
        show_banner=False,
    )


def _import_spec_from_args() -> str:
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()

    import_spec = os.getenv("MCP_SERVER_IMPORT", "").strip()
    if import_spec:
        return import_spec

    raise SystemExit("MCP server import is required, for example mcp_repo_mapper.server:mcp")


def _load_server(import_spec: str) -> FastMCPServer:
    module_name, separator, attribute_name = import_spec.partition(":")
    if not separator or not module_name or not attribute_name:
        raise SystemExit(f"Invalid MCP server import: {import_spec}")

    module = importlib.import_module(module_name)
    server = getattr(module, attribute_name)
    return cast(FastMCPServer, server)


def _port_from_env() -> int:
    raw = os.getenv("PORT", "8000")
    try:
        return int(raw)
    except ValueError as exc:
        raise SystemExit(f"PORT must be an integer: {raw}") from exc


def _bool_from_env(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default

    return raw.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    main()
