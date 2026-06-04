import asyncio
from collections.abc import Sequence
from pathlib import Path

from wayfinder.mcp.adapter import MCPAdapter, MCPToolLike
from wayfinder.mcp.models import MCPToolCall
from wayfinder.mcp.project5 import (
    build_project5_mcp_configs,
    build_project5_mcp_http_configs,
    project5_primary_tool_names,
)


class FakeTool:
    def __init__(self, name: str, result: object) -> None:
        self.name = name
        self.description = f"{name} Project 5 tool"
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def ainvoke(self, input: dict[str, object]) -> object:
        self.calls.append(input)
        return self.result


class FakeClient:
    def __init__(self, tools: Sequence[MCPToolLike]) -> None:
        self._tools = list(tools)

    async def get_tools(self) -> list[MCPToolLike]:
        return self._tools


def test_project5_configs_use_published_stdio_entrypoints() -> None:
    configs = build_project5_mcp_configs()
    project5_root = Path(__file__).resolve().parents[1] / "../project5"

    assert [config.to_client_config() for config in configs] == [
        {
            "transport": "stdio",
            "command": "mcp-repo-mapper",
            "args": [],
            "env": {
                "PYTHONPATH": str(
                    (project5_root / "mcp-repo-mapper" / "src").resolve()
                )
            },
        },
        {
            "transport": "stdio",
            "command": "mcp-ast-explorer",
            "args": [],
            "env": {
                "PYTHONPATH": str(
                    (project5_root / "mcp-ast-explorer" / "src").resolve()
                )
            },
        },
        {
            "transport": "stdio",
            "command": "mcp-test-runner",
            "args": [],
            "env": {
                "PYTHONPATH": str(
                    (project5_root / "mcp-test-runner" / "src").resolve()
                )
            },
        },
    ]


def test_project5_http_configs_use_streamable_http_reader_services() -> None:
    configs = build_project5_mcp_http_configs(
        {
            "WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL": "https://repo-mapper.example/mcp",
            "WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL": "https://ast-explorer.example/mcp",
        }
    )

    assert [config.to_client_config() for config in configs] == [
        {
            "transport": "streamable_http",
            "url": "https://repo-mapper.example/mcp",
        },
        {
            "transport": "streamable_http",
            "url": "https://ast-explorer.example/mcp",
        },
    ]


def test_project5_http_configs_ignore_missing_reader_urls() -> None:
    configs = build_project5_mcp_http_configs(
        {
            "WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL": "https://repo-mapper.example/mcp",
        }
    )

    assert len(configs) == 1
    assert configs[0].name == "repo_mapper"


def test_project5_primary_tool_contract_is_declared() -> None:
    assert project5_primary_tool_names() == {
        "scan_repo",
        "find_entry_points",
        "language_breakdown",
        "detect_framework",
        "find_definition",
        "find_references",
        "function_signature",
        "call_chain",
        "class_hierarchy",
        "run_pytest",
        "run_jest",
        "run_single_test",
        "parse_test_output",
    }


def test_project5_tool_names_flow_through_adapter_contract() -> None:
    tools = [
        FakeTool(name=tool_name, result={"ok": True})
        for tool_name in sorted(project5_primary_tool_names())
    ]
    adapter = MCPAdapter(FakeClient(tools))

    descriptors = asyncio.run(adapter.list_tools())

    assert {descriptor.name for descriptor in descriptors} == project5_primary_tool_names()


def test_adapter_calls_project5_happy_path_tool_contract() -> None:
    tool = FakeTool(name="scan_repo", result={"repo": "mapped"})
    adapter = MCPAdapter(FakeClient([tool]))

    result = asyncio.run(
        adapter.call_tool(
            MCPToolCall(
                tool_name="scan_repo",
                arguments={"path": "/tmp/example-repo"},
            )
        )
    )

    assert result.tool_name == "scan_repo"
    assert result.content == {"repo": "mapped"}
    assert tool.calls == [{"path": "/tmp/example-repo"}]
