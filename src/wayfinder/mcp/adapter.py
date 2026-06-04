import asyncio
import json
from typing import Protocol, TypeAlias, cast

from langchain_mcp_adapters.client import (
    MultiServerMCPClient,
    SSEConnection,
    StdioConnection,
    StreamableHttpConnection,
    WebsocketConnection,
)
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from wayfinder.mcp.models import (
    MCPServerConfig,
    MCPToolCall,
    MCPToolCallResult,
    MCPToolDescriptor,
    MCPToolError,
    MCPToolErrorType,
)
from wayfinder.mcp.tracing import trace_mcp_tool_call

MCPConnection: TypeAlias = (
    StdioConnection | SSEConnection | StreamableHttpConnection | WebsocketConnection
)


class MCPToolCallError(Exception):
    def __init__(self, error: MCPToolError) -> None:
        super().__init__(error.message)
        self.error = error


class MCPToolLike(Protocol):
    name: str
    description: str

    async def ainvoke(self, input: dict[str, object]) -> object: ...


class MCPClientLike(Protocol):
    async def get_tools(self) -> list[MCPToolLike]: ...


_RETRYABLE_TOOL_ERRORS = (TimeoutError, ConnectionError)


class MCPAdapter:
    def __init__(
        self,
        client: MCPClientLike,
        *,
        max_attempts: int = 3,
        timeout_seconds: float = 30.0,
        retry_wait_multiplier_seconds: float = 0.1,
        retry_wait_max_seconds: float = 2.0,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if retry_wait_multiplier_seconds < 0:
            raise ValueError("retry_wait_multiplier_seconds cannot be negative")
        if retry_wait_max_seconds < 0:
            raise ValueError("retry_wait_max_seconds cannot be negative")

        self._client = client
        self._max_attempts = max_attempts
        self._timeout_seconds = timeout_seconds
        self._retry_wait_multiplier_seconds = retry_wait_multiplier_seconds
        self._retry_wait_max_seconds = retry_wait_max_seconds

    async def list_tools(self) -> list[MCPToolDescriptor]:
        tools = await self._client.get_tools()
        return [
            MCPToolDescriptor(name=tool.name, description=tool.description or "")
            for tool in tools
        ]

    async def call_tool(self, call: MCPToolCall) -> MCPToolCallResult:
        tools = await self._client.get_tools()
        tools_by_name = {tool.name: tool for tool in tools}

        try:
            tool = tools_by_name[call.tool_name]
        except KeyError as exc:
            raise self._tool_call_error(
                tool_name=call.tool_name,
                error_type="not_found",
                message=f"MCP tool not found: {call.tool_name}",
                retryable=False,
            ) from exc

        try:
            async with trace_mcp_tool_call(call):
                result = await self._invoke_tool(tool, call)
        except TimeoutError as exc:
            raise self._tool_call_error(
                tool_name=call.tool_name,
                error_type="timeout",
                message=str(exc) or f"MCP tool timed out after {self._timeout_seconds:g}s",
                retryable=True,
            ) from exc
        except RuntimeError as exc:
            raise self._tool_call_error(
                tool_name=call.tool_name,
                error_type="tool_error",
                message=str(exc),
                retryable=False,
            ) from exc
        except ConnectionError as exc:
            raise self._tool_call_error(
                tool_name=call.tool_name,
                error_type="tool_error",
                message=str(exc),
                retryable=True,
            ) from exc

        return MCPToolCallResult(
            tool_name=call.tool_name,
            content=_normalize_tool_content(result),
        )

    async def _invoke_tool(self, tool: MCPToolLike, call: MCPToolCall) -> object:
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(
                multiplier=self._retry_wait_multiplier_seconds,
                min=0,
                max=self._retry_wait_max_seconds,
            ),
            retry=retry_if_exception_type(_RETRYABLE_TOOL_ERRORS),
            reraise=True,
        )

        async for attempt in retrying:
            with attempt:
                return await asyncio.wait_for(
                    tool.ainvoke(call.arguments),
                    timeout=self._timeout_seconds,
                )

        raise RuntimeError("MCP tool retry loop exited without result")

    @staticmethod
    def _tool_call_error(
        *,
        tool_name: str,
        error_type: MCPToolErrorType,
        message: str,
        retryable: bool,
    ) -> MCPToolCallError:
        return MCPToolCallError(
            MCPToolError(
                tool_name=tool_name,
                error_type=error_type,
                message=message,
                retryable=retryable,
            )
        )


def build_mcp_client(configs: list[MCPServerConfig]) -> MCPClientLike:
    client_config: dict[str, MCPConnection] = {
        config.name: cast(MCPConnection, config.to_client_config()) for config in configs
    }
    return cast(MCPClientLike, MultiServerMCPClient(client_config))


def _normalize_tool_content(content: object) -> object:
    if isinstance(content, dict):
        return _normalize_text_content_item(content) or content

    if isinstance(content, list) and len(content) == 1:
        item = content[0]
        if isinstance(item, dict):
            return _normalize_text_content_item(item) or content

    return content


def _normalize_text_content_item(item: dict[object, object]) -> object | None:
    if item.get("type") != "text":
        return None

    text = item.get("text")
    if not isinstance(text, str):
        return None

    try:
        return cast(object, json.loads(text))
    except json.JSONDecodeError:
        return text
