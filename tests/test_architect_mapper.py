import asyncio
from pathlib import Path
from typing import cast

import pytest

from wayfinder.graph import build_graph
from wayfinder.graph.architecture import (
    MCPArchitectureScanner,
    architecture_state_from_scan_result,
)
from wayfinder.graph.nodes import architect_mapper_node
from wayfinder.ingestion.models import RepoHandle, RepoSource
from wayfinder.mcp.models import MCPToolCall, MCPToolCallResult


class FakeArchitectureAdapter:
    def __init__(self, content: object) -> None:
        self.content = content
        self.calls: list[MCPToolCall] = []

    async def call_tool(self, call: MCPToolCall) -> MCPToolCallResult:
        self.calls.append(call)
        return MCPToolCallResult(tool_name=call.tool_name, content=self.content)


class FakeArchitectureScanner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def scan_repo(self, repo_path: str) -> dict[str, object]:
        self.calls.append(repo_path)
        return {
            "root": repo_path,
            "languages": ["Python"],
            "entry_points": ["app/main.py"],
            "dependency_graph": {"nodes": ["app.main"], "edges": []},
            "frameworks": ["FastAPI"],
        }


def test_architecture_state_from_scan_result_maps_structured_fields() -> None:
    result = architecture_state_from_scan_result(
        {
            "root": "/tmp/example-repo",
            "files": [],
            "languages": [{"language": "Python", "files": 3, "bytes": 1200}],
            "entry_points": [{"path": "app/main.py", "kind": "fastapi", "confidence": 0.9}],
            "dependency_graph": {"nodes": ["app.main"], "edges": []},
            "frameworks": [{"name": "FastAPI", "evidence": ["app/main.py"], "confidence": 0.9}],
        }
    )

    assert "repo_metadata" in result
    assert "module_dep_graph" in result
    assert "entry_points" in result
    assert "partial_summaries" in result

    repo_metadata = result["repo_metadata"]
    languages = cast(list[str], repo_metadata["languages"])
    frameworks = cast(list[str], repo_metadata["frameworks"])

    assert repo_metadata["root"] == "/tmp/example-repo"
    assert "Python" in languages[0]
    assert "FastAPI" in frameworks[0]
    assert result["module_dep_graph"] == {"nodes": ["app.main"], "edges": []}

    assert result["entry_points"] is not None
    assert "app/main.py" in result["entry_points"][0]

    summary = result["partial_summaries"]["architect_mapper"]
    assert "Repository root: /tmp/example-repo" in summary
    assert "What I cannot prove" in summary


def test_architecture_state_from_scan_result_rejects_invalid_shape() -> None:
    result = architecture_state_from_scan_result("not a scan result")

    assert "errors" in result
    assert "next_agent" in result

    assert result["errors"][0]["node"] == "architect_mapper"
    assert result["errors"][0]["error_type"] == "invalid_scan_result"
    assert result["next_agent"] == "final_writer"


def test_architect_mapper_node_uses_repo_handle_path_boundary(tmp_path: Path) -> None:
    repo_handle = RepoHandle(
        source=RepoSource(kind="local", original_ref=str(tmp_path)),
        local_path=tmp_path,
    )

    result = architect_mapper_node({"repo_handle": repo_handle})

    assert "repo_metadata" in result
    assert "partial_summaries" in result
    assert "next_agent" in result

    assert result["next_agent"] == "final_writer"

    summary = result["partial_summaries"]["architect_mapper"]
    assert "Repository root:" in summary
    assert str(tmp_path) in summary


def test_architect_mapper_node_returns_error_without_repo_handle() -> None:
    result = architect_mapper_node({})

    assert "errors" in result
    assert "partial_summaries" in result
    assert "next_agent" in result

    assert result["errors"][0]["node"] == "architect_mapper"
    assert result["errors"][0]["error_type"] == "missing_repo_path"
    assert result["next_agent"] == "final_writer"
    assert "no local repo path" in result["partial_summaries"]["architect_mapper"]


def test_mcp_architecture_scanner_calls_scan_repo_with_local_path() -> None:
    content: dict[str, object] = {
        "root": "/tmp/example-repo",
        "languages": [],
        "entry_points": [],
        "dependency_graph": {"nodes": [], "edges": []},
        "frameworks": [],
    }
    adapter = FakeArchitectureAdapter(content)
    scanner = MCPArchitectureScanner(adapter)

    result = scanner.scan_repo("/tmp/example-repo")

    assert result == content
    assert len(adapter.calls) == 1
    assert adapter.calls[0].tool_name == "scan_repo"
    assert adapter.calls[0].arguments == {"path": "/tmp/example-repo"}


def test_mcp_architecture_scanner_rejects_non_dict_content() -> None:
    adapter = FakeArchitectureAdapter(["not", "a", "dict"])
    scanner = MCPArchitectureScanner(adapter)

    with pytest.raises(TypeError, match="scan_repo returned non-dict content"):
        scanner.scan_repo("/tmp/example-repo")

    assert len(adapter.calls) == 1
    assert adapter.calls[0].tool_name == "scan_repo"
    assert adapter.calls[0].arguments == {"path": "/tmp/example-repo"}


def test_mcp_architecture_scanner_rejects_active_event_loop() -> None:
    adapter = FakeArchitectureAdapter({"root": "/tmp/example-repo"})
    scanner = MCPArchitectureScanner(adapter)

    async def call_inside_event_loop() -> None:
        with pytest.raises(RuntimeError, match="cannot run inside an active event loop"):
            scanner.scan_repo("/tmp/example-repo")

    asyncio.run(call_inside_event_loop())

    assert adapter.calls == []


def test_graph_can_inject_architecture_scanner(tmp_path: Path) -> None:
    scanner = FakeArchitectureScanner()
    graph = build_graph(architecture_scanner=scanner)

    repo_handle = RepoHandle(
        source=RepoSource(kind="local", original_ref=str(tmp_path)),
        local_path=tmp_path,
    )

    result = graph.invoke(
        {
            "query": "Explain architecture",
            "repo_handle": repo_handle,
        }
    )

    assert scanner.calls == [str(tmp_path)]
    assert "partial_summaries" in result
    assert "FastAPI" in result["partial_summaries"]["architect_mapper"]
