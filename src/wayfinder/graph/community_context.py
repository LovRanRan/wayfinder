"""Community context collection for final synthesis."""

from __future__ import annotations

import asyncio
from typing import Protocol, cast
from urllib.parse import urlparse

from wayfinder.graph.state import CommunityContextItem, WayfinderState
from wayfinder.mcp.adapter import MCPToolCallError
from wayfinder.mcp.models import MCPToolCall, MCPToolCallResult


class CommunityContextProvider(Protocol):
    def collect(self, state: WayfinderState) -> list[CommunityContextItem]: ...


class _MCPAdapter(Protocol):
    async def call_tool(self, call: MCPToolCall) -> MCPToolCallResult: ...


class MCPCommunityContextProvider:
    """Collect optional Tavily/GitHub context without blocking core repo facts."""

    def __init__(self, adapter: _MCPAdapter, *, max_items: int = 3) -> None:
        self._adapter = adapter
        self._max_items = max_items

    def collect(self, state: WayfinderState) -> list[CommunityContextItem]:
        query = _community_query_from_state(state)
        if not query:
            return []

        items: list[CommunityContextItem] = []
        items.extend(self._safe_call("tavily_search", {"query": query, "max_results": 2}))

        github_query = _github_query_from_state(state)
        if github_query:
            items.extend(self._safe_call("search_code", {"query": github_query, "perPage": 2}))

        return items[: self._max_items]

    def _safe_call(
        self,
        tool_name: str,
        arguments: dict[str, object],
    ) -> list[CommunityContextItem]:
        try:
            result = self._call_adapter(MCPToolCall(tool_name=tool_name, arguments=arguments))
        except (MCPToolCallError, RuntimeError, TypeError, ValueError):
            return []

        return _items_from_tool_result(tool_name=tool_name, content=result.content)

    def _call_adapter(self, call: MCPToolCall) -> MCPToolCallResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._adapter.call_tool(call))

        raise RuntimeError("Community context provider cannot run inside an active event loop")


def community_context_summary(items: list[CommunityContextItem]) -> str:
    if not items:
        return "Community context unavailable or skipped."

    lines = ["Community context (supporting only; repository facts still win):"]
    for item in items:
        title = item.get("title") or item.get("source") or "external context"
        snippet = item.get("snippet") or ""
        url = item.get("url") or ""
        suffix = f" ({url})" if url else ""
        lines.append(f"- {title}: {snippet}{suffix}")

    return "\n".join(lines)


def _community_query_from_state(state: WayfinderState) -> str:
    query = state.get("query", "").strip()
    repo_ref = state.get("repo_url", "").strip()
    if not query and not repo_ref:
        return ""
    if repo_ref:
        return f"{repo_ref} {query}".strip()
    return query


def _github_query_from_state(state: WayfinderState) -> str:
    repo_name = _github_repo_name(state.get("repo_url", ""))
    query = state.get("query", "").strip()
    if repo_name is None or not query:
        return ""

    return f"{query} repo:{repo_name}"


def _github_repo_name(repo_url: str) -> str | None:
    parsed = urlparse(repo_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "github.com":
        return None

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        return None

    return f"{parts[0]}/{parts[1].removesuffix('.git')}"


def _items_from_tool_result(
    *,
    tool_name: str,
    content: object,
) -> list[CommunityContextItem]:
    raw_items = _raw_result_items(content)
    if not raw_items and isinstance(content, str):
        return [
            {
                "source": tool_name,
                "title": tool_name,
                "snippet": content,
                "url": None,
            }
        ]

    items: list[CommunityContextItem] = []
    for raw_item in raw_items:
        normalized = _normalize_context_item(tool_name=tool_name, raw_item=raw_item)
        if normalized is not None:
            items.append(normalized)

    return items


def _raw_result_items(content: object) -> list[object]:
    if isinstance(content, list):
        return cast(list[object], content)

    if not isinstance(content, dict):
        return []

    content_dict = cast(dict[str, object], content)
    for key in ("results", "items", "data"):
        value = content_dict.get(key)
        if isinstance(value, list):
            return cast(list[object], value)

    return [content]


def _normalize_context_item(
    *,
    tool_name: str,
    raw_item: object,
) -> CommunityContextItem | None:
    if isinstance(raw_item, str):
        return {
            "source": tool_name,
            "title": tool_name,
            "snippet": raw_item,
            "url": None,
        }

    if not isinstance(raw_item, dict):
        return None

    item = cast(dict[str, object], raw_item)
    title = _first_string(item, ("title", "name", "path", "html_url")) or tool_name
    snippet = _first_string(item, ("snippet", "content", "body", "text", "description")) or ""
    url = _first_string(item, ("url", "html_url", "link"))

    if not snippet and not url:
        return None

    return {
        "source": tool_name,
        "title": title,
        "snippet": snippet,
        "url": url,
    }


def _first_string(item: dict[str, object], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None

