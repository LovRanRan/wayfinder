import asyncio
from pathlib import Path
from typing import cast

import pytest

from wayfinder.graph import build_graph
from wayfinder.graph.entry import (
    MCPEntryScanner,
    _console_script_symbol,
    _is_cli_entry_query,
    _symbol_from_script_target,
    entry_explainer_missing_repo_path,
    entry_explainer_missing_symbol_candidate,
    entry_state_from_ast_result,
    repo_path_from_state,
    scan_symbol_for_entry,
    symbol_candidate_from_state,
)
from wayfinder.graph.nodes import build_entry_explainer_node, entry_explainer_node
from wayfinder.ingestion.models import RepoHandle, RepoSource
from wayfinder.mcp.adapter import MCPToolCallError
from wayfinder.mcp.models import MCPToolCall, MCPToolCallResult, MCPToolError


class FakeEntryAdapter:
    def __init__(self, content_by_tool: dict[str, object]) -> None:
        self.content_by_tool = content_by_tool
        self.calls: list[MCPToolCall] = []

    async def call_tool(self, call: MCPToolCall) -> MCPToolCallResult:
        self.calls.append(call)
        return MCPToolCallResult(
            tool_name=call.tool_name,
            content=self.content_by_tool[call.tool_name],
        )


class FakeSequentialEntryAdapter:
    def __init__(self, contents: list[object]) -> None:
        self.contents = contents
        self.calls: list[MCPToolCall] = []

    async def call_tool(self, call: MCPToolCall) -> MCPToolCallResult:
        self.calls.append(call)
        return MCPToolCallResult(
            tool_name=call.tool_name,
            content=self.contents[len(self.calls) - 1],
        )


class FailingEntryAdapter:
    def __init__(self, error: MCPToolError) -> None:
        self.error = error
        self.calls: list[MCPToolCall] = []

    async def call_tool(self, call: MCPToolCall) -> MCPToolCallResult:
        self.calls.append(call)
        raise MCPToolCallError(self.error)


class FakeEntryScanner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def explain_symbol(self, repo_path: str, symbol: str) -> dict[str, object]:
        self.calls.append((repo_path, symbol))
        return {"symbol": symbol, "definition": {"path": "app/main.py", "line": 12}}


def test_repo_path_from_state_reads_repo_handle_local_path(tmp_path: Path) -> None:
    repo_handle = RepoHandle(
        source=RepoSource(kind="local", original_ref=str(tmp_path)),
        local_path=tmp_path,
    )

    assert repo_path_from_state({"repo_handle": repo_handle}) == str(tmp_path)


def test_symbol_candidate_from_state_uses_first_entry_point() -> None:
    result = symbol_candidate_from_state(
        {"entry_points": ["app.main:create_app", "app.cli:main"]}
    )

    assert result == "app.main:create_app"


def test_symbol_candidate_from_state_uses_single_explicit_query_symbol() -> None:
    result = symbol_candidate_from_state(
        {"query": "Explain the data flow through app.service.create_user"}
    )

    assert result == "app.service.create_user"


def test_symbol_candidate_from_state_uses_backticked_bare_symbol() -> None:
    result = symbol_candidate_from_state({"query": "Explain `build_graph`"})

    assert result == "build_graph"


def test_symbol_candidate_from_state_uses_contextual_bare_code_symbol() -> None:
    result = symbol_candidate_from_state(
        {"query": "Explain the behavior and data flow through build_graph"}
    )

    assert result == "build_graph"


def test_symbol_candidate_from_state_ignores_plain_language_context_word() -> None:
    result = symbol_candidate_from_state({"query": "Explain the behavior of routing"})

    assert result is None


def test_symbol_candidate_from_state_rejects_ambiguous_query_symbols() -> None:
    result = symbol_candidate_from_state(
        {"query": "Compare app.service.create_user and app.api.create_user"}
    )

    assert result is None


def test_symbol_candidate_prefers_real_symbol_over_filename() -> None:
    # Live failure: the filename state.py was picked and merge_summaries missed
    # (design note 022). The real symbol must win.
    result = symbol_candidate_from_state(
        {"query": "What does the merge_summaries reducer do in state.py?"}
    )

    assert result == "merge_summaries"


def test_symbol_candidate_ignores_filename_only_query() -> None:
    result = symbol_candidate_from_state({"query": "Explain state.py"})

    assert result is None


def test_symbol_candidate_uses_standalone_camelcase_symbol() -> None:
    result = symbol_candidate_from_state({"query": "How does WayfinderState work?"})

    assert result == "WayfinderState"


def test_symbol_candidate_keeps_dotted_symbol_despite_filename_in_query() -> None:
    result = symbol_candidate_from_state(
        {"query": "Trace app.service.create_user defined in service.py"}
    )

    assert result == "app.service.create_user"


def test_symbol_candidate_ignores_uppercase_acronym() -> None:
    # Live failure on CloakBrowser: "verify the exact CLI" sent "CLI" to
    # find_definition -> "Symbol not found: CLI". All-caps acronyms must not be
    # treated as bare symbols (design note 024).
    assert symbol_candidate_from_state({"query": "verify the exact CLI"}) is None


def test_symbol_candidate_ignores_multiple_acronyms_in_context() -> None:
    assert (
        symbol_candidate_from_state({"query": "How does the API build the URL?"})
        is None
    )


def test_symbol_candidate_keeps_real_symbol_alongside_acronym() -> None:
    # An acronym in the sentence must not block a genuine bare symbol: without
    # the stopword the query has two bare candidates (real + acronym) and is
    # rejected as ambiguous.
    result = symbol_candidate_from_state(
        {"query": "Does resolve_proxy_geo build the URL?"}
    )

    assert result == "resolve_proxy_geo"


def test_symbol_from_script_target_converts_module_object() -> None:
    assert (
        _symbol_from_script_target("cloakbrowser.__main__:main")
        == "cloakbrowser.__main__.main"
    )
    assert _symbol_from_script_target("pkg.cli:App.run") == "pkg.cli.App"
    assert _symbol_from_script_target("pkg.cli:main [gui]") == "pkg.cli.main"
    assert _symbol_from_script_target("pkg.module") == "pkg.module"
    assert _symbol_from_script_target("   ") is None


def test_console_script_symbol_reads_project_scripts(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "cloakbrowser"\n\n'
        '[project.scripts]\ncloakbrowser = "cloakbrowser.__main__:main"\n',
        encoding="utf-8",
    )

    assert _console_script_symbol(str(tmp_path)) == "cloakbrowser.__main__.main"


def test_console_script_symbol_missing_pyproject_returns_none(tmp_path: Path) -> None:
    assert _console_script_symbol(str(tmp_path)) is None


def test_is_cli_entry_query_matches_cli_and_run_phrases() -> None:
    assert _is_cli_entry_query("verify the exact CLI")
    assert _is_cli_entry_query("how do I run this tool?")
    assert _is_cli_entry_query("what is the entry point")
    # Must not fire on unrelated words that merely contain the letters "cli".
    assert not _is_cli_entry_query("explain the client connection")


def test_symbol_candidate_resolves_cli_query_via_pyproject(tmp_path: Path) -> None:
    # Live failure on CloakBrowser: "verify the exact CLI" fell back to a
    # Dockerfile entry point and missed. The real CLI comes from pyproject.
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "cloakbrowser"\n\n'
        '[project.scripts]\ncloakbrowser = "cloakbrowser.__main__:main"\n',
        encoding="utf-8",
    )
    repo_handle = RepoHandle(
        source=RepoSource(kind="local", original_ref=str(tmp_path)),
        local_path=tmp_path,
    )

    result = symbol_candidate_from_state(
        {
            "query": "verify the exact CLI",
            "repo_handle": repo_handle,
            "entry_points": ["Dockerfile"],
        }
    )

    assert result == "cloakbrowser.__main__.main"


def test_symbol_candidate_non_cli_query_ignores_pyproject(tmp_path: Path) -> None:
    # A non-CLI query must not read pyproject; it keeps the old entry-point
    # fallback behaviour.
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "cloakbrowser"\n\n'
        '[project.scripts]\ncloakbrowser = "cloakbrowser.__main__:main"\n',
        encoding="utf-8",
    )
    repo_handle = RepoHandle(
        source=RepoSource(kind="local", original_ref=str(tmp_path)),
        local_path=tmp_path,
    )

    result = symbol_candidate_from_state(
        {
            "query": "give me the overall architecture",
            "repo_handle": repo_handle,
            "entry_points": ["Dockerfile"],
        }
    )

    assert result == "Dockerfile"


def test_symbol_candidate_module_query_beats_entry_point_fallback(
    tmp_path: Path,
) -> None:
    # Regression (live miss on CloakBrowser 2026-06-22): architect_mapper
    # populates entry_points (often a Dockerfile), so symbol_candidate_from_state
    # returned that fallback and the module-source resolution never ran. A
    # module-naming behavioural query must resolve to the real symbol BEFORE the
    # entry_points[0] fallback (design note 025).
    pkg = tmp_path / "cloakbrowser"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "geoip.py").write_text(
        "def resolve_proxy_geo(proxy_url):\n    return None, None\n",
        encoding="utf-8",
    )
    repo_handle = RepoHandle(
        source=RepoSource(kind="local", original_ref=str(tmp_path)),
        local_path=tmp_path,
    )

    result = symbol_candidate_from_state(
        {
            "query": "what does geoip do?",
            "repo_handle": repo_handle,
            "entry_points": ["Dockerfile"],
        }
    )

    assert result == "resolve_proxy_geo"


def test_entry_explainer_missing_repo_path_returns_degraded_state() -> None:
    result = entry_explainer_missing_repo_path()
    errors = result.get("errors")
    next_agent = result.get("next_agent")
    partial_summaries = result.get("partial_summaries")

    assert errors is not None
    assert next_agent is not None
    assert partial_summaries is not None
    assert errors[0]["node"] == "entry_explainer"
    assert errors[0]["error_type"] == "missing_repo_path"
    assert next_agent == "final_writer"
    assert "no local repo path" in partial_summaries["entry_explainer"]


def test_entry_explainer_missing_symbol_candidate_returns_degraded_state() -> None:
    result = entry_explainer_missing_symbol_candidate()
    errors = result.get("errors")
    next_agent = result.get("next_agent")
    partial_summaries = result.get("partial_summaries")

    assert errors is not None
    assert next_agent is not None
    assert partial_summaries is not None
    assert errors[0]["node"] == "entry_explainer"
    assert errors[0]["error_type"] == "missing_symbol_candidate"
    assert next_agent == "final_writer"
    assert "no symbol candidate" in partial_summaries["entry_explainer"]


def test_entry_state_from_ast_result_maps_minimal_ast_evidence() -> None:
    ast_result = {
        "symbol": "app.main:create_app",
        "definition": {"path": "app/main.py", "line": 12},
        "signature": "create_app() -> FastAPI",
        "references": [{"path": "tests/test_app.py", "line": 4}],
        "call_chain": [{"caller": "app.cli:main", "callee": "app.main:create_app"}],
    }

    result = entry_state_from_ast_result(ast_result)
    ast_index = result.get("ast_index")
    next_agent = result.get("next_agent")
    partial_summaries = result.get("partial_summaries")

    assert ast_index is not None
    assert next_agent is not None
    assert partial_summaries is not None
    assert ast_index == ast_result
    assert next_agent == "final_writer"
    assert "app.main:create_app" in partial_summaries["entry_explainer"]


def test_entry_state_from_ast_result_writes_entry_path_explanation() -> None:
    ast_result: dict[str, object] = {
        "status": "found",
        "symbol": "app.main:create_app",
        "definition": {
            "found": True,
            "symbol": "app.main:create_app",
            "kind": "function",
            "location": {"relative_path": "app/main.py", "line": 12},
            "source_code": "def create_app() -> FastAPI:\n    return FastAPI()\n",
        },
        "signature": {
            "found": True,
            "symbol": "app.main:create_app",
            "signature": "create_app() -> FastAPI",
        },
        "references": {
            "found": True,
            "symbol": "app.main:create_app",
            "references": [
                {"location": {"relative_path": "tests/test_app.py", "line": 4}},
            ],
        },
        "call_chain": {
            "found": True,
            "symbol": "app.main:create_app",
            "callers": [{"symbol": "app.cli:main"}],
        },
        "limitations": [],
    }

    result = entry_state_from_ast_result(ast_result)
    partial_summaries = result.get("partial_summaries")

    assert partial_summaries is not None
    summary = partial_summaries["entry_explainer"]
    assert "Definition: app/main.py:12" in summary
    assert "Signature: create_app() -> FastAPI" in summary
    assert "Call chain: app.cli:main -> app.main:create_app" in summary
    assert "References: tests/test_app.py:4" in summary
    assert "Data flow evidence" in summary
    assert "Source citations: app/main.py:12; tests/test_app.py:4" in summary
    assert "Assumptions" in summary


def test_entry_state_from_ast_result_does_not_treat_empty_call_chain_as_unused() -> None:
    ast_result: dict[str, object] = {
        "status": "found",
        "symbol": "app.main:create_app",
        "definition": {
            "found": True,
            "symbol": "app.main:create_app",
            "kind": "function",
            "location": {"relative_path": "app/main.py", "line": 12},
        },
        "signature": {
            "found": True,
            "symbol": "app.main:create_app",
            "signature": "create_app() -> FastAPI",
        },
        "references": {"found": True, "symbol": "app.main:create_app", "references": []},
        "call_chain": {"found": True, "symbol": "app.main:create_app", "callers": []},
        "limitations": [],
    }

    result = entry_state_from_ast_result(ast_result)
    partial_summaries = result.get("partial_summaries")

    assert partial_summaries is not None
    summary = partial_summaries["entry_explainer"]
    assert "Call chain: none returned" in summary
    assert "References: none returned" in summary
    assert "not proof of unused code" in summary


def test_entry_state_from_ast_result_maps_missing_symbol_evidence() -> None:
    ast_result: dict[str, object] = {
        "status": "missing",
        "symbol": "app.main:missing",
        "definition": {
            "found": False,
            "symbol": "app.main:missing",
            "error": "Symbol not found: app.main:missing",
        },
        "signature": None,
        "references": [],
        "call_chain": [],
        "limitations": ["Symbol not found: app.main:missing"],
    }

    result = entry_state_from_ast_result(ast_result)
    ast_index = result.get("ast_index")
    errors = result.get("errors")
    partial_summaries = result.get("partial_summaries")

    assert ast_index == ast_result
    assert errors is not None
    assert partial_summaries is not None
    assert errors[0]["node"] == "entry_explainer"
    assert errors[0]["error_type"] == "missing_symbol"
    assert errors[0]["retryable"] is False
    assert "app.main:missing" in partial_summaries["entry_explainer"]
    assert "not found" in partial_summaries["entry_explainer"]
    assert "call chain" in partial_summaries["entry_explainer"]


def test_entry_state_from_ast_result_maps_unsupported_language_evidence() -> None:
    ast_result: dict[str, object] = {
        "status": "unsupported",
        "symbol": "app.main:create_app",
        "definition": {
            "found": False,
            "symbol": "app.main:create_app",
            "error": "Unsupported language: javascript",
        },
        "signature": None,
        "references": [],
        "call_chain": [],
        "limitations": ["Unsupported language: javascript"],
    }

    result = entry_state_from_ast_result(ast_result)
    ast_index = result.get("ast_index")
    errors = result.get("errors")
    partial_summaries = result.get("partial_summaries")

    assert ast_index == ast_result
    assert errors is not None
    assert partial_summaries is not None
    assert errors[0]["node"] == "entry_explainer"
    assert errors[0]["error_type"] == "unsupported_language"
    assert errors[0]["retryable"] is False
    assert "unsupported" in partial_summaries["entry_explainer"]
    assert "python" in partial_summaries["entry_explainer"]


def test_entry_state_from_ast_result_maps_parse_error_evidence() -> None:
    ast_result: dict[str, object] = {
        "status": "tool_error",
        "symbol": "app.bad:broken",
        "definition": None,
        "signature": None,
        "references": [],
        "call_chain": [],
        "retryable": False,
        "limitations": ["AST parse error in app/bad.py: invalid syntax"],
    }

    result = entry_state_from_ast_result(ast_result)
    errors = result.get("errors")
    partial_summaries = result.get("partial_summaries")

    assert errors is not None
    assert partial_summaries is not None
    assert errors[0]["error_type"] == "ast_parse_error"
    assert errors[0]["retryable"] is False
    assert "parse error" in partial_summaries["entry_explainer"]


def test_entry_state_from_ast_result_maps_retryable_tool_error() -> None:
    ast_result: dict[str, object] = {
        "status": "tool_error",
        "symbol": "app.main:create_app",
        "definition": None,
        "signature": None,
        "references": [],
        "call_chain": [],
        "retryable": True,
        "limitations": ["mcp-ast-explorer find_definition timed out"],
    }

    result = entry_state_from_ast_result(ast_result)
    errors = result.get("errors")

    assert errors is not None
    assert errors[0]["error_type"] == "ast_tool_error"
    assert errors[0]["retryable"] is True


def test_scan_symbol_for_entry_uses_injected_scanner() -> None:
    scanner = FakeEntryScanner()

    result = scan_symbol_for_entry(
        "/tmp/example-repo",
        "app.main:create_app",
        scanner=scanner,
    )

    assert scanner.calls == [("/tmp/example-repo", "app.main:create_app")]
    assert result["symbol"] == "app.main:create_app"


def test_build_entry_explainer_node_scans_symbol_and_shapes_state(tmp_path: Path) -> None:
    scanner = FakeEntryScanner()
    node = build_entry_explainer_node(scanner)

    repo_handle = RepoHandle(
        source=RepoSource(kind="local", original_ref=str(tmp_path)),
        local_path=tmp_path,
    )

    result = node(
        {
            "repo_handle": repo_handle,
            "entry_points": ["app.main:create_app"],
        }
    )
    ast_index = result.get("ast_index")
    partial_summaries = result.get("partial_summaries")
    next_agent = result.get("next_agent")

    assert scanner.calls == [(str(tmp_path), "app.main:create_app")]
    assert ast_index is not None
    assert partial_summaries is not None
    assert next_agent == "final_writer"
    assert ast_index["symbol"] == "app.main:create_app"
    assert "app.main:create_app" in partial_summaries["entry_explainer"]


def test_entry_explainer_node_uses_placeholder_scanner_by_default(tmp_path: Path) -> None:
    repo_handle = RepoHandle(
        source=RepoSource(kind="local", original_ref=str(tmp_path)),
        local_path=tmp_path,
    )

    result = entry_explainer_node(
        {
            "repo_handle": repo_handle,
            "entry_points": ["app.main:create_app"],
        }
    )
    ast_index = result.get("ast_index")
    partial_summaries = result.get("partial_summaries")

    assert ast_index is not None
    assert partial_summaries is not None
    assert ast_index["symbol"] == "app.main:create_app"
    assert "app.main:create_app" in partial_summaries["entry_explainer"]


def test_mcp_entry_scanner_collects_definition_before_other_evidence() -> None:
    content_by_tool: dict[str, object] = {
        "find_definition": {
            "found": True,
            "symbol": "app.main:create_app",
            "location": {"relative_path": "app/main.py", "line": 12},
            "signature": "create_app() -> FastAPI",
        },
        "function_signature": {
            "found": True,
            "symbol": "app.main:create_app",
            "signature": "create_app() -> FastAPI",
        },
        "find_references": {
            "found": True,
            "symbol": "app.main:create_app",
            "references": [{"location": {"relative_path": "tests/test_app.py"}}],
        },
        "call_chain": {
            "found": True,
            "symbol": "app.main:create_app",
            "callers": [{"symbol": "app.cli:main"}],
        },
    }
    adapter = FakeEntryAdapter(content_by_tool)
    scanner = MCPEntryScanner(adapter)

    result = scanner.explain_symbol("/tmp/example-repo", "app.main:create_app")

    assert result["status"] == "found"
    assert result["definition"] == content_by_tool["find_definition"]
    assert result["signature"] == content_by_tool["function_signature"]
    assert result["references"] == content_by_tool["find_references"]
    assert result["call_chain"] == content_by_tool["call_chain"]
    assert [call.tool_name for call in adapter.calls] == [
        "find_definition",
        "function_signature",
        "find_references",
        "call_chain",
    ]
    assert adapter.calls[0].arguments == {
        "path": "/tmp/example-repo",
        "symbol": "app.main:create_app",
        "language": "python",
    }
    assert adapter.calls[3].arguments == {
        "path": "/tmp/example-repo",
        "from_symbol": "app.main:create_app",
        "depth": 2,
        "language": "python",
    }


def test_mcp_entry_scanner_retries_src_layout_symbol_fallback() -> None:
    adapter = FakeSequentialEntryAdapter(
        [
            {
                "found": False,
                "symbol": "wayfinder.graph.app.build_graph",
                "error": "Symbol not found: wayfinder.graph.app.build_graph",
            },
            {
                "found": True,
                "symbol": "src.wayfinder.graph.app.build_graph",
                "location": {"relative_path": "src/wayfinder/graph/app.py", "line": 45},
                "signature": "build_graph(checkpointer)",
            },
            {
                "found": True,
                "symbol": "src.wayfinder.graph.app.build_graph",
                "signature": "build_graph(checkpointer)",
            },
            {
                "found": True,
                "symbol": "src.wayfinder.graph.app.build_graph",
                "references": [],
            },
            {
                "found": True,
                "symbol": "src.wayfinder.graph.app.build_graph",
                "callers": [],
            },
        ]
    )
    scanner = MCPEntryScanner(adapter)

    result = scanner.explain_symbol(
        "/tmp/example-repo",
        "wayfinder.graph.app.build_graph",
    )

    assert result["status"] == "found"
    assert result["symbol"] == "src.wayfinder.graph.app.build_graph"
    assert [call.tool_name for call in adapter.calls] == [
        "find_definition",
        "find_definition",
        "function_signature",
        "find_references",
        "call_chain",
    ]
    assert adapter.calls[0].arguments["symbol"] == "wayfinder.graph.app.build_graph"
    assert adapter.calls[1].arguments["symbol"] == "src.wayfinder.graph.app.build_graph"
    assert adapter.calls[4].arguments["from_symbol"] == (
        "src.wayfinder.graph.app.build_graph"
    )


def test_mcp_entry_scanner_calls_class_hierarchy_for_class_symbol() -> None:
    content_by_tool: dict[str, object] = {
        "find_definition": {
            "found": True,
            "symbol": "app.models:User",
            "kind": "class",
            "location": {"relative_path": "app/models.py", "line": 3},
        },
        "find_references": {
            "found": True,
            "symbol": "app.models:User",
            "references": [],
        },
        "call_chain": {
            "found": True,
            "symbol": "app.models:User",
            "callers": [],
        },
        "class_hierarchy": {
            "found": True,
            "class_name": "app.models:User",
            "subclasses": [{"class_name": "app.models:AdminUser"}],
        },
    }
    adapter = FakeEntryAdapter(content_by_tool)
    scanner = MCPEntryScanner(adapter)

    result = scanner.explain_symbol("/tmp/example-repo", "app.models:User")

    assert result["class_hierarchy"] == content_by_tool["class_hierarchy"]
    assert [call.tool_name for call in adapter.calls] == [
        "find_definition",
        "find_references",
        "call_chain",
        "class_hierarchy",
    ]
    assert adapter.calls[3].arguments == {
        "path": "/tmp/example-repo",
        "class_name": "app.models:User",
        "language": "python",
    }


def test_mcp_entry_scanner_stops_when_definition_is_missing() -> None:
    content_by_tool: dict[str, object] = {
        "find_definition": {
            "found": False,
            "symbol": "app.main:missing",
            "error": "Symbol not found: app.main:missing",
        },
    }
    adapter = FakeEntryAdapter(content_by_tool)
    scanner = MCPEntryScanner(adapter)

    result = scanner.explain_symbol("/tmp/example-repo", "app.main:missing")

    limitations = cast(list[str], result["limitations"])
    assert result["status"] == "missing"
    assert result["definition"] == content_by_tool["find_definition"]
    assert result["references"] == []
    assert result["call_chain"] == []
    assert "Symbol not found" in limitations[0]
    assert [call.tool_name for call in adapter.calls] == ["find_definition"]


def test_mcp_entry_scanner_marks_unsupported_language_result() -> None:
    content_by_tool: dict[str, object] = {
        "find_definition": {
            "found": False,
            "symbol": "app.main:create_app",
            "error": "Unsupported language: javascript",
        },
    }
    adapter = FakeEntryAdapter(content_by_tool)
    scanner = MCPEntryScanner(adapter)

    result = scanner.explain_symbol("/tmp/example-repo", "app.main:create_app")

    assert result["status"] == "unsupported"
    assert [call.tool_name for call in adapter.calls] == ["find_definition"]


def test_mcp_entry_scanner_marks_parse_error_result_as_tool_error() -> None:
    content_by_tool: dict[str, object] = {
        "find_definition": {
            "found": False,
            "symbol": "app.bad:broken",
            "error": "AST parse error in app/bad.py: invalid syntax",
        },
    }
    adapter = FakeEntryAdapter(content_by_tool)
    scanner = MCPEntryScanner(adapter)

    result = scanner.explain_symbol("/tmp/example-repo", "app.bad:broken")

    assert result["status"] == "tool_error"
    assert result["retryable"] is False
    assert [call.tool_name for call in adapter.calls] == ["find_definition"]


def test_mcp_entry_scanner_normalizes_adapter_tool_error() -> None:
    adapter = FailingEntryAdapter(
        MCPToolError(
            tool_name="find_definition",
            error_type="timeout",
            message="mcp-ast-explorer find_definition timed out",
            retryable=True,
        )
    )
    scanner = MCPEntryScanner(adapter)

    result = scanner.explain_symbol("/tmp/example-repo", "app.main:create_app")

    assert result["status"] == "tool_error"
    assert result["retryable"] is True
    assert result["limitations"] == ["mcp-ast-explorer find_definition timed out"]
    assert [call.tool_name for call in adapter.calls] == ["find_definition"]


def test_mcp_entry_scanner_rejects_non_dict_tool_content() -> None:
    adapter = FakeEntryAdapter({"find_definition": ["not", "a", "dict"]})
    scanner = MCPEntryScanner(adapter)

    with pytest.raises(TypeError, match="find_definition returned non-dict content"):
        scanner.explain_symbol("/tmp/example-repo", "app.main:create_app")

    assert len(adapter.calls) == 1
    assert adapter.calls[0].tool_name == "find_definition"


def test_mcp_entry_scanner_rejects_active_event_loop() -> None:
    adapter = FakeEntryAdapter({"find_definition": {"found": True}})
    scanner = MCPEntryScanner(adapter)

    async def call_inside_event_loop() -> None:
        with pytest.raises(RuntimeError, match="cannot run inside an active event loop"):
            scanner.explain_symbol("/tmp/example-repo", "app.main:create_app")

    asyncio.run(call_inside_event_loop())

    assert adapter.calls == []


def test_graph_can_inject_entry_scanner(tmp_path: Path) -> None:
    scanner = FakeEntryScanner()
    graph = build_graph(entry_scanner=scanner)

    repo_handle = RepoHandle(
        source=RepoSource(kind="local", original_ref=str(tmp_path)),
        local_path=tmp_path,
    )

    # Grounding questions now run architect_mapper first (design note 021), which
    # repopulates entry_points, so name the symbol explicitly in the query to
    # exercise the injected entry scanner deterministically.
    result = graph.invoke(
        {
            "query": "At runtime, how does app.main:create_app start the app?",
            "repo_handle": repo_handle,
            "entry_points": ["app.main:create_app"],
        }
    )
    partial_summaries = result.get("partial_summaries")

    assert scanner.calls == [(str(tmp_path), "app.main:create_app")]
    assert partial_summaries is not None
    assert "app.main:create_app" in partial_summaries["entry_explainer"]
