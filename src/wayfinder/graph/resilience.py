"""Reflection and resilience helpers for final Wayfinder output."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from wayfinder.graph.state import Claim, GraphError, WayfinderState
from wayfinder.ingestion.models import RepoHandle, RepoSizePolicy
from wayfinder.ingestion.resolver import assess_repo_size


@dataclass(frozen=True)
class ReflectionFeedback:
    is_safe: bool
    reasons: tuple[str, ...] = ()


class ReflectionReviewer(Protocol):
    def review(
        self,
        output: str,
        state: WayfinderState,
    ) -> ReflectionFeedback: ...


class DefaultReflectionReviewer:
    def review(
        self,
        output: str,
        state: WayfinderState,
    ) -> ReflectionFeedback:
        reasons: list[str] = []
        lowered = output.lower()
        for claim in state.get("contradicted_claims", []):
            text = claim.get("text", "")
            if not text:
                continue
            text_lowered = text.lower()
            if text_lowered in lowered and not _claim_already_labeled(output, text):
                reasons.append(f"contradicted claim appears as true: {text}")

        if _states_verification_success(output) and state.get("unverified_claims"):
            reasons.append("draft states verification success while claims are unverified")

        for error in state.get("errors", []):
            if not _is_resilience_relevant_error(error):
                continue
            message = error.get("message", "")
            if message and message not in output:
                reasons.append(f"draft omits error limitation: {error['error_type']}")

        return ReflectionFeedback(is_safe=not reasons, reasons=tuple(reasons))


class AlwaysRejectingReflectionReviewer:
    def review(
        self,
        output: str,
        state: WayfinderState,
    ) -> ReflectionFeedback:
        del output, state
        return ReflectionFeedback(is_safe=False, reasons=("forced rejection",))


def apply_resilience_to_final_output(
    state: WayfinderState,
    draft_output: str,
    *,
    reviewer: ReflectionReviewer | None = None,
    max_reflection_iterations: int = 2,
) -> WayfinderState:
    resilient_state = _state_with_resilience_errors(state)
    reflected_output, reflection_summary, reflection_errors = (
        rewrite_final_output_with_reflection(
            resilient_state,
            draft_output,
            reviewer=reviewer,
            max_iterations=max_reflection_iterations,
        )
    )
    final_output = _append_resilience_sections(reflected_output, resilient_state)

    partial_summaries = dict(state.get("partial_summaries", {}))
    if reflection_summary:
        partial_summaries["reflection"] = reflection_summary

    return {
        "final_output": final_output,
        "partial_summaries": partial_summaries,
        "errors": [*resilient_state.get("errors", []), *reflection_errors],
        "next_agent": None,
    }


def rewrite_final_output_with_reflection(
    state: WayfinderState,
    draft_output: str,
    *,
    reviewer: ReflectionReviewer | None = None,
    max_iterations: int = 2,
) -> tuple[str, str, list[GraphError]]:
    active_reviewer = reviewer or DefaultReflectionReviewer()
    output = draft_output
    rewrites = 0

    while rewrites < max_iterations:
        feedback = active_reviewer.review(output, state)
        if feedback.is_safe:
            if rewrites == 0:
                return output, "Reflection summary: no rewrite needed.", []
            return (
                output,
                (
                    "Reflection summary: removed or relabeled contradicted "
                    f"claims in {rewrites} pass(es)."
                ),
                [],
            )

        output = _repair_output(output, state, feedback.reasons)
        rewrites += 1

    final_feedback = active_reviewer.review(output, state)
    if final_feedback.is_safe:
        return (
            output,
            f"Reflection summary: removed or relabeled contradicted claims in {rewrites} pass(es).",
            [],
        )

    return (
        (
            f"{output}\n\n"
            f"Reflection stopped after {max_iterations} iterations. "
            "The safest available answer is partial and preserves the unresolved limitations."
        ),
        "Reflection summary: reflection cap reached before all issues were cleared.",
        [
            {
                "node": "reflection",
                "error_type": "reflection_cap_reached",
                "message": "Reflection loop reached its hard cap before producing a safe draft.",
                "retryable": False,
            }
        ],
    )


def _repair_output(
    output: str,
    state: WayfinderState,
    reasons: Sequence[str],
) -> str:
    repaired = output
    for claim in state.get("contradicted_claims", []):
        text = claim.get("text", "")
        if text and text in repaired and not _claim_already_labeled(repaired, text):
            repaired = repaired.replace(text, f"Contradicted claim: {text}")

    if _states_verification_success(repaired) and state.get("unverified_claims"):
        repaired = repaired.replace("verified", "not fully verified")
        repaired = repaired.replace("Verified", "Not fully verified")

    if reasons:
        repaired = f"{repaired}\n\nReflection feedback: {'; '.join(reasons)}"

    return repaired


def _state_with_resilience_errors(state: WayfinderState) -> WayfinderState:
    errors = list(state.get("errors", []))
    repo_handle = state.get("repo_handle")
    if repo_handle is not None:
        oversized_error = _oversized_repo_error(repo_handle)
        if oversized_error is not None and not _has_error(errors, "repo_oversized"):
            errors.append(oversized_error)

    result = dict(state)
    result["errors"] = errors
    return cast(WayfinderState, result)


def _oversized_repo_error(repo_handle: RepoHandle) -> GraphError | None:
    assessment = assess_repo_size(repo_handle, RepoSizePolicy())
    if not assessment.is_oversized:
        return None

    return {
        "node": "ingestion",
        "error_type": "repo_oversized",
        "message": (
            f"Repository size guard: repo has {assessment.file_count} files, "
            f"which exceeds the {assessment.max_files} file limit; "
            "sampling/user confirmation is required before claiming full coverage."
        ),
        "retryable": False,
    }


def _append_resilience_sections(output: str, state: WayfinderState) -> str:
    sections: list[str] = []
    claim_section = _claim_limitations_section(
        unverified_claims=state.get("unverified_claims", []),
        contradicted_claims=state.get("contradicted_claims", []),
    )
    if claim_section:
        sections.append(claim_section)

    error_section = _error_limitations_section(state.get("errors", []))
    if error_section:
        sections.append(error_section)

    if not sections:
        return output

    return f"{output}\n\n" + "\n\n".join(sections)


def _claim_limitations_section(
    *,
    unverified_claims: Sequence[Claim],
    contradicted_claims: Sequence[Claim],
) -> str:
    lines: list[str] = []
    if contradicted_claims:
        lines.append("Contradicted claims:")
        lines.extend(f"- {claim.get('text', '')}" for claim in contradicted_claims)
    if unverified_claims:
        lines.append("Unverified claims:")
        lines.extend(f"- {claim.get('text', '')}" for claim in unverified_claims)

    return "\n".join(line for line in lines if line.strip())


def _error_limitations_section(errors: Sequence[GraphError]) -> str:
    relevant_errors = [error for error in errors if _is_resilience_relevant_error(error)]
    if not relevant_errors:
        return ""

    lines = ["Resilience limitations:"]
    for error in relevant_errors:
        lines.append(f"- {error['error_type']}: {error['message']}")

    return "\n".join(lines)


def _claim_already_labeled(output: str, claim_text: str) -> bool:
    claim_index = output.lower().find(claim_text.lower())
    if claim_index < 0:
        return False
    prefix = output[max(0, claim_index - 40) : claim_index].lower()
    return "contradicted" in prefix or "not verified" in prefix


def _states_verification_success(output: str) -> bool:
    lowered = output.lower()
    return "verified" in lowered and "unverified" not in lowered and "contradicted" not in lowered


def _is_resilience_relevant_error(error: GraphError) -> bool:
    return error["error_type"] in {
        "repo_oversized",
        "architecture_scan_tool_error",
        "unsupported_language",
        "ast_parse_error",
        "ast_tool_error",
        "missing_symbol",
        "validation_timed_out",
        "test_suite_failed_unrelated",
        "reflection_cap_reached",
    }


def _has_error(errors: Sequence[Mapping[str, object]], error_type: str) -> bool:
    return any(error.get("error_type") == error_type for error in errors)
