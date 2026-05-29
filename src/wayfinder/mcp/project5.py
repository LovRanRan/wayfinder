from dataclasses import dataclass

from wayfinder.mcp.models import MCPServerConfig


@dataclass(frozen=True)
class Project5MCPServer:
    name: str
    command: str
    primary_tools: tuple[str, ...]


PROJECT5_MCP_SERVERS: tuple[Project5MCPServer, ...] = (
    Project5MCPServer(
        name="repo_mapper",
        command="mcp-repo-mapper",
        primary_tools=(
            "scan_repo",
            "find_entry_points",
            "language_breakdown",
            "detect_framework",
        ),
    ),
    Project5MCPServer(
        name="ast_explorer",
        command="mcp-ast-explorer",
        primary_tools=(
            "find_definition",
            "find_references",
            "function_signature",
            "call_chain",
        ),
    ),
    Project5MCPServer(
        name="test_runner",
        command="mcp-test-runner",
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
        )
        for server in PROJECT5_MCP_SERVERS
    ]


def project5_primary_tool_names() -> set[str]:
    return {
        tool_name
        for server in PROJECT5_MCP_SERVERS
        for tool_name in server.primary_tools
    }