import asyncio
from collections.abc import Sequence

import pytest

from wayfinder.mcp.adapter import MCPAdapter, MCPToolCallError, MCPToolLike
from wayfinder.mcp.models import MCPServerConfig, MCPToolCall


class FakeTool:
    def __init__(self, name: str, description: str, result: object) -> None:
        self.name = name
        self.description = description
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


class SlowClient:
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds

    async def get_tools(self) -> list[MCPToolLike]:
        await asyncio.sleep(self.delay_seconds)
        return []


class FailingTool:
    def __init__(self, name: str, description: str, error: Exception) -> None:
        self.name = name
        self.description = description
        self.error = error
        self.calls = 0

    async def ainvoke(self, input: dict[str, object]) -> object:
        self.calls += 1
        raise self.error


class SlowTool:
    def __init__(self, name: str, description: str, delay_seconds: float) -> None:
        self.name = name
        self.description = description
        self.delay_seconds = delay_seconds
        self.calls = 0

    async def ainvoke(self, input: dict[str, object]) -> object:
        self.calls += 1
        await asyncio.sleep(self.delay_seconds)
        return {"ok": True}


def test_stdio_server_config_builds_client_config() -> None:
    config = MCPServerConfig(
        name="repo_mapper",
        transport="stdio",
        command="mcp-repo-mapper",
        args=["--stdio"],
        env={"LOG_LEVEL": "warning"},
    )

    assert config.to_client_config() == {
        "transport": "stdio",
        "command": "mcp-repo-mapper",
        "args": ["--stdio"],
        "env": {"LOG_LEVEL": "warning"},
    }


def test_streamable_http_server_config_builds_client_config() -> None:
    config = MCPServerConfig(
        name="github_search",
        transport="streamable_http",
        url="http://localhost:8080/mcp",
    )

    assert config.to_client_config() == {
        "transport": "streamable_http",
        "url": "http://localhost:8080/mcp",
    }


def test_server_config_rejects_missing_required_connection_fields() -> None:
    with pytest.raises(ValueError, match="stdio MCP server config requires command"):
        MCPServerConfig(name="missing_command", transport="stdio").to_client_config()

    with pytest.raises(ValueError, match="streamable_http MCP server config requires url"):
        MCPServerConfig(name="missing_url", transport="streamable_http").to_client_config()


def test_adapter_lists_tools_from_client() -> None:
    adapter = MCPAdapter(
        FakeClient(
            [
                FakeTool("map_repo", "Map repository structure", {"ok": True}),
                FakeTool("run_tests", "", {"ok": True}),
            ]
        )
    )

    descriptors = asyncio.run(adapter.list_tools())

    assert [descriptor.model_dump() for descriptor in descriptors] == [
        {"name": "map_repo", "description": "Map repository structure"},
        {"name": "run_tests", "description": ""},
    ]


def test_adapter_calls_named_tool() -> None:
    tool = FakeTool("map_repo", "Map repository structure", {"modules": 3})
    adapter = MCPAdapter(FakeClient([tool]))

    result = asyncio.run(
        adapter.call_tool(
            MCPToolCall(tool_name="map_repo", arguments={"repo_path": "/tmp/repo"})
        )
    )

    assert result.tool_name == "map_repo"
    assert result.content == {"modules": 3}
    assert tool.calls == [{"repo_path": "/tmp/repo"}]


def test_adapter_decodes_single_text_json_content_item() -> None:
    tool = FakeTool(
        "scan_repo",
        "Scan repository",
        [{"type": "text", "text": '{"modules": 3}'}],
    )
    adapter = MCPAdapter(FakeClient([tool]))

    result = asyncio.run(adapter.call_tool(MCPToolCall(tool_name="scan_repo")))

    assert result.content == {"modules": 3}


def test_adapter_preserves_single_text_content_item_when_not_json() -> None:
    tool = FakeTool(
        "scan_repo",
        "Scan repository",
        [{"type": "text", "text": "plain text result"}],
    )
    adapter = MCPAdapter(FakeClient([tool]))

    result = asyncio.run(adapter.call_tool(MCPToolCall(tool_name="scan_repo")))

    assert result.content == "plain text result"


def test_adapter_rejects_unknown_tool_with_structured_error() -> None:
    adapter = MCPAdapter(FakeClient([FakeTool("map_repo", "Map repository", {})]))

    with pytest.raises(MCPToolCallError) as exc_info:
        asyncio.run(adapter.call_tool(MCPToolCall(tool_name="missing_tool")))

    assert exc_info.value.error.model_dump() == {
        "tool_name": "missing_tool",
        "error_type": "not_found",
        "message": "MCP tool not found: missing_tool",
        "retryable": False,
    }


def test_adapter_retries_timeout_then_raises_structured_error() -> None:
    tool = FailingTool("scan_repo", "Scan repository", TimeoutError("server timed out"))
    adapter = MCPAdapter(
        FakeClient([tool]),
        retry_wait_multiplier_seconds=0,
        retry_wait_max_seconds=0,
    )

    with pytest.raises(MCPToolCallError) as exc_info:
        asyncio.run(adapter.call_tool(MCPToolCall(tool_name="scan_repo")))

    assert tool.calls == 3
    assert exc_info.value.error.model_dump() == {
        "tool_name": "scan_repo",
        "error_type": "timeout",
        "message": "server timed out",
        "retryable": True,
    }


def test_adapter_enforces_per_attempt_timeout() -> None:
    tool = SlowTool("scan_repo", "Scan repository", delay_seconds=1.0)
    adapter = MCPAdapter(
        FakeClient([tool]),
        timeout_seconds=0.01,
        retry_wait_multiplier_seconds=0,
        retry_wait_max_seconds=0,
    )

    with pytest.raises(MCPToolCallError) as exc_info:
        asyncio.run(adapter.call_tool(MCPToolCall(tool_name="scan_repo")))

    assert tool.calls == 3
    assert exc_info.value.error.model_dump() == {
        "tool_name": "scan_repo",
        "error_type": "timeout",
        "message": "MCP tool timed out after 0.01s",
        "retryable": True,
    }


def test_adapter_enforces_tool_discovery_timeout() -> None:
    adapter = MCPAdapter(
        SlowClient(delay_seconds=1.0),
        timeout_seconds=0.01,
        retry_wait_multiplier_seconds=0,
        retry_wait_max_seconds=0,
    )

    with pytest.raises(MCPToolCallError) as exc_info:
        asyncio.run(adapter.call_tool(MCPToolCall(tool_name="scan_repo")))

    assert exc_info.value.error.model_dump() == {
        "tool_name": "scan_repo",
        "error_type": "timeout",
        "message": "MCP tool discovery timed out after 0.01s",
        "retryable": True,
    }


def test_adapter_does_not_retry_runtime_error() -> None:
    tool = FailingTool("scan_repo", "Scan repository", RuntimeError("bad tool input"))
    adapter = MCPAdapter(FakeClient([tool]))

    with pytest.raises(MCPToolCallError) as exc_info:
        asyncio.run(adapter.call_tool(MCPToolCall(tool_name="scan_repo")))

    assert tool.calls == 1
    assert exc_info.value.error.model_dump() == {
        "tool_name": "scan_repo",
        "error_type": "tool_error",
        "message": "bad tool input",
        "retryable": False,
    }


def test_adapter_retries_connection_error_then_raises_structured_error() -> None:
    tool = FailingTool("scan_repo", "Scan repository", ConnectionError("server unavailable"))
    adapter = MCPAdapter(
        FakeClient([tool]),
        retry_wait_multiplier_seconds=0,
        retry_wait_max_seconds=0,
    )

    with pytest.raises(MCPToolCallError) as exc_info:
        asyncio.run(adapter.call_tool(MCPToolCall(tool_name="scan_repo")))

    assert tool.calls == 3
    assert exc_info.value.error.model_dump() == {
        "tool_name": "scan_repo",
        "error_type": "tool_error",
        "message": "server unavailable",
        "retryable": True,
    }
