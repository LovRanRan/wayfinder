import os
from dataclasses import dataclass

from wayfinder.mcp.models import MCPServerConfig

NPM_CACHE_DIR = "/private/tmp/wayfinder-npm-cache"


@dataclass(frozen=True)
class CommunityMCPServer:
    name: str
    command: str
    args: tuple[str, ...]
    primary_tools: tuple[str, ...]
    required_env: tuple[str, ...]
    extra_env: tuple[tuple[str, str], ...] = ()


COMMUNITY_MCP_SERVERS: tuple[CommunityMCPServer, ...] = (
    CommunityMCPServer(
        name="tavily",
        command="npx",
        args=("-y", "tavily-mcp@latest"),
        primary_tools=("tavily_search",),
        required_env=("TAVILY_API_KEY",),
        extra_env=(
            ("NPM_CONFIG_CACHE", NPM_CACHE_DIR),
            ("npm_config_cache", NPM_CACHE_DIR),
        ),
    ),
    CommunityMCPServer(
        name="github_search",
        command="docker",
        args=(
            "run",
            "-i",
            "--rm",
            "-e",
            "GITHUB_PERSONAL_ACCESS_TOKEN",
            "-e",
            "GITHUB_TOOLSETS=repos,issues,pull_requests",
            "-e",
            "GITHUB_READ_ONLY=1",
            "ghcr.io/github/github-mcp-server",
        ),
        primary_tools=("search_code", "search_issues", "search_pull_requests"),
        required_env=("GITHUB_PERSONAL_ACCESS_TOKEN",),
    ),
)


def _env_for_server(server: CommunityMCPServer) -> dict[str, str]:
    env = dict(server.extra_env)
    for env_var in server.required_env:
        value = os.getenv(env_var)
        if value:
            env[env_var] = value
    return env


def build_community_mcp_configs() -> list[MCPServerConfig]:
    return [
        MCPServerConfig(
            name=server.name,
            transport="stdio",
            command=server.command,
            args=list(server.args),
            env=_env_for_server(server),
        )
        for server in COMMUNITY_MCP_SERVERS
    ]


def community_primary_tool_names() -> set[str]:
    return {
        tool_name
        for server in COMMUNITY_MCP_SERVERS
        for tool_name in server.primary_tools
    }


def community_required_env_vars() -> set[str]:
    return {
        env_var
        for server in COMMUNITY_MCP_SERVERS
        for env_var in server.required_env
    }
