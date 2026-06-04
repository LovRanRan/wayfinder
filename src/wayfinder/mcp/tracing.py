"""Optional LangSmith tracing helpers for MCP tool calls."""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager, suppress
from importlib import import_module
from typing import Any

from wayfinder.mcp.models import MCPToolCall


@asynccontextmanager
async def trace_mcp_tool_call(call: MCPToolCall) -> AsyncIterator[None]:
    if not _tracing_enabled(os.environ):
        yield
        return

    trace_factory = _langsmith_trace_factory()
    if trace_factory is None:
        yield
        return

    try:
        trace_context = trace_factory(
            name=f"mcp:{call.tool_name}",
            run_type="tool",
            inputs={"arguments": call.arguments},
            metadata=_metadata_for_tool_call(call),
            tags=["wayfinder", "mcp_tool"],
        )
    except Exception:
        yield
        return

    try:
        trace_context.__enter__()
    except Exception:
        yield
        return

    try:
        yield
    except Exception:
        exc_info = sys.exc_info()
        with suppress(Exception):
            trace_context.__exit__(*exc_info)
        raise
    else:
        with suppress(Exception):
            trace_context.__exit__(None, None, None)


def _metadata_for_tool_call(call: MCPToolCall) -> dict[str, object]:
    return {
        "agent_name": None,
        "tool_name": call.tool_name,
        "mcp_server": None,
        "tokens": 0,
        "latency": 0.0,
        "cost_usd": 0.0,
        "claim_id": None,
    }


def _tracing_enabled(env: Mapping[str, str]) -> bool:
    return env.get("LANGSMITH_TRACING", "").strip().lower() in {"1", "true", "yes", "on"}


def _langsmith_trace_factory() -> Any | None:
    try:
        module = import_module("langsmith")
    except ImportError:
        return None

    trace_factory = getattr(module, "trace", None)
    if not callable(trace_factory):
        return None

    return trace_factory
