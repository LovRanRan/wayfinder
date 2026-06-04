import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from wayfinder.mcp.models import MCPServerConfig

_PROJECTS_ROOT = Path(__file__).resolve().parents[4]
_PROJECT5_ROOT = _PROJECTS_ROOT / "project5"


@dataclass(frozen=True)
class Project5MCPServer:
    name: str
    command: str
    source_dir: Path
    primary_tools: tuple[str, ...]
    http_url_env: str | None = None


PROJECT5_MCP_SERVERS: tuple[Project5MCPServer, ...] = (
    Project5MCPServer(
        name="repo_mapper",
        command="mcp-repo-mapper",
        source_dir=_PROJECT5_ROOT / "mcp-repo-mapper" / "src",
        primary_tools=(
            "scan_repo",
            "find_entry_points",
            "language_breakdown",
            "detect_framework",
        ),
        http_url_env="WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL",
    ),
    Project5MCPServer(
        name="ast_explorer",
        command="mcp-ast-explorer",
        source_dir=_PROJECT5_ROOT / "mcp-ast-explorer" / "src",
        primary_tools=(
            "find_definition",
            "find_references",
            "function_signature",
            "call_chain",
            "class_hierarchy",
        ),
        http_url_env="WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL",
    ),
    Project5MCPServer(
        name="test_runner",
        command="mcp-test-runner",
        source_dir=_PROJECT5_ROOT / "mcp-test-runner" / "src",
        primary_tools=(
            "run_pytest",
            "run_jest",
            "run_single_test",
            "parse_test_output",
        ),
    ),
)


def build_project5_mcp_configs() -> list[MCPServerConfig]:
    return [
        MCPServerConfig(
            name=server.name,
            transport="stdio",
            command=server.command,
            env={"PYTHONPATH": str(server.source_dir)},
        )
        for server in PROJECT5_MCP_SERVERS
    ]


def build_project5_mcp_http_configs(
    env: Mapping[str, str] | None = None,
) -> list[MCPServerConfig]:
    env_map = os.environ if env is None else env
    configs: list[MCPServerConfig] = []
    for server in PROJECT5_MCP_SERVERS:
        if server.http_url_env is None:
            continue

        url = env_map.get(server.http_url_env, "").strip()
        if url:
            configs.append(
                MCPServerConfig(
                    name=server.name,
                    transport="streamable_http",
                    url=url,
                )
            )
    return configs


def project5_primary_tool_names() -> set[str]:
    return {
        tool_name
        for server in PROJECT5_MCP_SERVERS
        for tool_name in server.primary_tools
    }
