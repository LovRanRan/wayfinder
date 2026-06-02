"""Architecture-mapper scanner and result-shaping helpers."""

import asyncio
from typing import Protocol, cast

from wayfinder.graph.state import WayfinderState
from wayfinder.mcp.models import MCPToolCall, MCPToolCallResult


class ArchitectureScanner(Protocol):
    def scan_repo(self, repo_path: str) -> dict[str, object]: ...


class _PlaceholderArchitectureScanner:
    def scan_repo(self, repo_path: str) -> dict[str, object]:
        return _placeholder_scan_result(root=repo_path)


class _MCPAdapter(Protocol):
    async def call_tool(self, call: MCPToolCall) -> MCPToolCallResult: ...


class MCPArchitectureScanner:
    def __init__(self, adapter: _MCPAdapter) -> None:
        self._adapter = adapter

    def scan_repo(self, repo_path: str) -> dict[str, object]:
        call = MCPToolCall(
            tool_name="scan_repo",
            arguments={"path": repo_path},
        )
        result = self._call_adapter(call)

        content: object = result.content

        if not isinstance(content, dict):
            raise TypeError("mcp-repo-mapper scan_repo returned non-dict content")

        return cast(dict[str, object], content)

    def _call_adapter(self, call: MCPToolCall) -> MCPToolCallResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._adapter.call_tool(call))

        raise RuntimeError(
            "MCP architecture scanner cannot run inside an active event loop"
        )


def repo_path_from_state(state: WayfinderState) -> str | None:
    repo_handle = state.get("repo_handle")
    if repo_handle is None:
        return None

    return str(repo_handle.local_path)


def architect_mapper_missing_repo_path() -> WayfinderState:
    return {
        "errors": [
            {
                "node": "architect_mapper",
                "error_type": "missing_repo_path",
                "message": "architect_mapper requires a local repo path from ingestion.",
                "retryable": False,
            }
        ],
        "partial_summaries": {
            "architect_mapper": (
                "Placeholder architecture summary unavailable: I cannot map "
                "the repository architecture because no local repo path was "
                "available from ingestion."
            )
        },
        "next_agent": "final_writer",
    }


def architecture_state_from_scan_result(scan_result: object) -> WayfinderState:
    if not isinstance(scan_result, dict):
        return _architect_mapper_invalid_scan_result()

    scan_data = cast(dict[str, object], scan_result)
    root = scan_data.get("root")
    raw_languages = scan_data.get("languages")
    languages: list[str] = (
        [str(item) for item in cast(list[object], raw_languages)]
        if isinstance(raw_languages, list)
        else []
    )

    raw_frameworks = scan_data.get("frameworks")
    frameworks: list[str] = (
        [str(item) for item in cast(list[object], raw_frameworks)]
        if isinstance(raw_frameworks, list)
        else []
    )

    repo_metadata: dict[str, object] = {
        "root": root if isinstance(root, str) else "",
        "languages": languages,
        "frameworks": frameworks,
    }

    dependency_graph = scan_data.get("dependency_graph")
    module_dep_graph: dict[str, object] | None = (
        cast(dict[str, object], dependency_graph)
        if isinstance(dependency_graph, dict)
        else None
    )
    raw_entry_points = scan_data.get("entry_points")
    entry_points: list[str] = (
        [str(item) for item in cast(list[object], raw_entry_points)]
        if isinstance(raw_entry_points, list)
        else []
    )

    summary = _architecture_summary_from_fields(
        root=repo_metadata["root"],
        languages=languages,
        frameworks=frameworks,
        entry_points=entry_points,
        module_dep_graph=module_dep_graph,
    )

    return {
        "repo_metadata": repo_metadata,
        "module_dep_graph": module_dep_graph,
        "entry_points": entry_points,
        "partial_summaries": {"architect_mapper": summary},
        "next_agent": "final_writer",
    }


def scan_repo_for_architecture(
    repo_path: str,
    *,
    scanner: ArchitectureScanner | None = None,
) -> dict[str, object]:
    active_scanner = scanner or _PlaceholderArchitectureScanner()
    return active_scanner.scan_repo(repo_path)


def _architecture_summary_from_fields(
    *,
    root: object,
    languages: list[str],
    frameworks: list[str],
    entry_points: list[str],
    module_dep_graph: dict[str, object] | None,
) -> str:
    language_text = ", ".join(languages) if languages else "unknown"
    framework_text = ", ".join(frameworks) if frameworks else "none detected"
    entry_point_text = ", ".join(entry_points) if entry_points else "no strong entry point evidence"
    dependency_text = "available" if module_dep_graph is not None else "unavailable or degraded"

    return (
        f"Repository root: {root or 'unknown'}\n"
        f"Languages: {language_text}\n"
        f"Frameworks: {framework_text}\n"
        f"Entry points: {entry_point_text}\n"
        f"Dependency graph: {dependency_text}\n"
        "What I cannot prove: function behavior, runtime behavior, and test-backed claims."
    )


def _architect_mapper_invalid_scan_result() -> WayfinderState:
    return {
        "errors": [
            {
                "node": "architect_mapper",
                "error_type": "invalid_scan_result",
                "message": "mcp-repo-mapper returned an invalid scan result shape.",
                "retryable": False,
            }
        ],
        "partial_summaries": {
            "architect_mapper": (
                "Architecture summary unavailable: repo-mapper returned an "
                "invalid scan result shape."
            )
        },
        "next_agent": "final_writer",
    }


def _placeholder_scan_result(*, root: str = "") -> dict[str, object]:
    return {
        "root": root,
        "files": [],
        "languages": [],
        "entry_points": [],
        "dependency_graph": {"nodes": [], "edges": []},
        "frameworks": [],
    }
