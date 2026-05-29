import asyncio
import os
import shutil
import subprocess

import pytest

from wayfinder.mcp.adapter import MCPAdapter, build_mcp_client
from wayfinder.mcp.community import build_community_mcp_configs
from wayfinder.mcp.models import MCPServerConfig, MCPToolCall

pytestmark = pytest.mark.integration

COMMUNITY_INTEGRATION_ENABLED = (
    os.getenv("WAYFINDER_RUN_COMMUNITY_MCP_INTEGRATION") == "1"
)


def _config_by_name(name: str) -> MCPServerConfig:
    for config in build_community_mcp_configs():
        if config.name == name:
            return config

    raise AssertionError(f"Missing community MCP config: {name}")


def _skip_if_integration_disabled() -> None:
    if not COMMUNITY_INTEGRATION_ENABLED:
        pytest.skip("set WAYFINDER_RUN_COMMUNITY_MCP_INTEGRATION=1 to run real MCP tests")


def _skip_if_command_missing(config: MCPServerConfig) -> None:
    if config.command is None:
        pytest.skip(f"{config.name} does not use a local command")

    if shutil.which(config.command) is None:
        pytest.skip(f"Community MCP command is not installed: {config.command}")


def _skip_if_env_missing(env_vars: tuple[str, ...]) -> None:
    missing = [env_var for env_var in env_vars if not os.getenv(env_var)]
    if missing:
        pytest.skip(f"missing environment variables: {', '.join(missing)}")


def _skip_if_docker_unavailable(config: MCPServerConfig) -> None:
    if config.command != "docker":
        return

    result = subprocess.run(
        ["docker", "info"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("Docker daemon is not available")


def _arguments_for_tool(tool_name: str) -> dict[str, object]:
    if tool_name == "tavily_search":
        return {
            "query": "LangChain Runnable documentation",
            "max_results": 1,
        }

    if tool_name == "search_code":
        return {
            "query": "Runnable repo:langchain-ai/langchain",
            "perPage": 1,
        }

    raise AssertionError(f"Unsupported community happy-path tool: {tool_name}")


@pytest.mark.parametrize(
    ("server_name", "expected_tool", "required_env"),
    [
        ("tavily", "tavily_search", ("TAVILY_API_KEY",)),
        ("github_search", "search_code", ("GITHUB_PERSONAL_ACCESS_TOKEN",)),
    ],
)
def test_community_mcp_server_lists_and_calls_happy_path_tool(
    server_name: str,
    expected_tool: str,
    required_env: tuple[str, ...],
) -> None:
    _skip_if_integration_disabled()

    config = _config_by_name(server_name)
    _skip_if_command_missing(config)
    _skip_if_env_missing(required_env)
    _skip_if_docker_unavailable(config)

    adapter = MCPAdapter(build_mcp_client([config]))

    descriptors = asyncio.run(adapter.list_tools())
    assert expected_tool in {descriptor.name for descriptor in descriptors}

    result = asyncio.run(
        adapter.call_tool(
            MCPToolCall(
                tool_name=expected_tool,
                arguments=_arguments_for_tool(expected_tool),
            )
        )
    )

    assert result.tool_name == expected_tool
    assert result.content is not None
