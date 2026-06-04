from pathlib import Path
from typing import Literal

from wayfinder.graph.nodes import final_writer_node
from wayfinder.graph.resilience import (
    AlwaysRejectingReflectionReviewer,
    apply_resilience_to_final_output,
    rewrite_final_output_with_reflection,
)
from wayfinder.graph.routing import build_route_decision
from wayfinder.graph.state import Claim, GraphError, WayfinderState
from wayfinder.ingestion.models import RepoHandle, RepoSource


def _repo_handle(tmp_path: Path, *, file_count: int | None = None) -> RepoHandle:
    return RepoHandle(
        source=RepoSource(kind="local", original_ref=str(tmp_path)),
        local_path=tmp_path,
        file_count=file_count,
    )


def _claim(
    text: str,
    *,
    status: Literal["pending", "verified", "unverified", "contradicted"],
) -> Claim:
    return {
        "text": text,
        "source_agent": "entry_explainer",
        "risk_level": "high",
        "test_strategy": "existing_test",
        "test_id": "tests/test_service.py::test_behavior",
        "status": status,
    }


def _error(error_type: str, message: str) -> GraphError:
    return {
        "node": "entry_explainer",
        "error_type": error_type,
        "message": message,
        "retryable": False,
    }


def test_reflection_rewrites_contradicted_claim_text() -> None:
    state: WayfinderState = {
        "contradicted_claims": [
            _claim("parse_user returns a User for invalid input", status="contradicted")
        ],
    }

    output, summary, errors = rewrite_final_output_with_reflection(
        state,
        "parse_user returns a User for invalid input",
    )

    assert "Contradicted claim:" in output
    assert "removed or relabeled contradicted claims" in summary
    assert errors == []


def test_reflection_cap_stops_after_two_failed_repairs() -> None:
    state: WayfinderState = {
        "contradicted_claims": [
            _claim("parse_user returns a User for invalid input", status="contradicted")
        ],
    }

    output, summary, errors = rewrite_final_output_with_reflection(
        state,
        "parse_user returns a User for invalid input",
        reviewer=AlwaysRejectingReflectionReviewer(),
        max_iterations=2,
    )

    assert "Reflection stopped after 2 iterations" in output
    assert "reflection cap reached" in summary
    assert errors[0]["error_type"] == "reflection_cap_reached"


def test_final_writer_surfaces_oversized_repo_limitation(tmp_path: Path) -> None:
    result = final_writer_node(
        {
            "repo_url": str(tmp_path),
            "repo_handle": _repo_handle(tmp_path, file_count=10001),
            "partial_summaries": {"architect_mapper": "Repository root: sample"},
        }
    )

    assert result["final_output"] is not None
    assert "Repository size guard" in result["final_output"]
    assert "10001 files" in result["final_output"]
    assert result["errors"][0]["error_type"] == "repo_oversized"


def test_final_writer_surfaces_unsupported_language_and_parse_error() -> None:
    result = apply_resilience_to_final_output(
        {
            "errors": [
                _error("unsupported_language", "Unsupported language: javascript"),
                _error("ast_parse_error", "AST parse error in app/bad.py"),
            ],
            "unverified_claims": [
                _claim("javascript function routes requests", status="unverified")
            ],
        },
        "Entry explanation draft.",
    )

    assert result["final_output"] is not None
    assert "Unsupported language: javascript" in result["final_output"]
    assert "AST parse error in app/bad.py" in result["final_output"]
    assert "Unverified claims" in result["final_output"]


def test_reflection_accepts_partial_tool_error_limitation_text() -> None:
    output, summary, errors = rewrite_final_output_with_reflection(
        {
            "errors": [
                _error(
                    "architecture_scan_tool_error",
                    (
                        "Error calling tool 'scan_repo': 'utf-8' codec can't decode "
                        "byte 0xb1 in position 23: invalid start byte"
                    ),
                )
            ],
        },
        (
            "The repository scan failed with a tool error: 'utf-8' codec can't "
            "decode byte 0xb1 in position 23: invalid start byte."
        ),
    )

    assert "Reflection feedback" not in output
    assert summary == "Reflection summary: no rewrite needed."
    assert errors == []


def test_final_writer_does_not_rewrite_missing_symbol_into_fact() -> None:
    result = apply_resilience_to_final_output(
        {
            "errors": [_error("missing_symbol", "Symbol not found: app.fake.run")],
        },
        "app.fake.run handles startup.",
    )

    assert result["final_output"] is not None
    assert "Symbol not found: app.fake.run" in result["final_output"]
    assert "verified" not in result["final_output"].lower()


def test_safe_default_route_can_be_corrected_by_user() -> None:
    decision = build_route_decision(
        {
            "query": "Help me understand this repo",
            "user_corrections": ["intent=behavioral"],
        }
    )

    assert decision["intent"] == "behavioral"
    assert decision["next_agent"] == "entry_explainer"
    assert decision["source"] == "user_correction"
    assert decision["needs_human_review"] is False
