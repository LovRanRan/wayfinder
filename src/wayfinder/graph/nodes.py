"""Placeholder nodes for the Commit 2 Supervisor graph."""

from collections.abc import Callable

from wayfinder.graph.architecture import (
    ArchitectureScanner,
    architect_mapper_missing_repo_path,
    architecture_state_from_scan_result,
    scan_repo_for_architecture,
)
from wayfinder.graph.architecture import (
    repo_path_from_state as architecture_repo_path_from_state,
)
from wayfinder.graph.entry import (
    EntryScanner,
    entry_explainer_missing_repo_path,
    entry_explainer_missing_symbol_candidate,
    entry_state_from_ast_result,
    scan_symbol_for_entry,
    symbol_candidate_from_state,
)
from wayfinder.graph.entry import (
    repo_path_from_state as entry_repo_path_from_state,
)
from wayfinder.graph.resilience import apply_resilience_to_final_output
from wayfinder.graph.routing import build_route_decision
from wayfinder.graph.state import WayfinderState
from wayfinder.graph.verifier import TestRunner, verifier_state_from_state


def supervisor_node(state: WayfinderState) -> WayfinderState:
    route_decision = build_route_decision(state)
    return {
        "intent": route_decision["intent"],
        "next_agent": route_decision["next_agent"],
        "route_decision": route_decision,
    }


def build_architect_mapper_node(
    scanner: ArchitectureScanner | None = None,
) -> Callable[[WayfinderState], WayfinderState]:
    def _node(state: WayfinderState) -> WayfinderState:
        repo_path = architecture_repo_path_from_state(state)

        if repo_path is None:
            return architect_mapper_missing_repo_path()

        scan_result = scan_repo_for_architecture(repo_path, scanner=scanner)
        return architecture_state_from_scan_result(scan_result)

    return _node


def architect_mapper_node(state: WayfinderState) -> WayfinderState:
    return build_architect_mapper_node()(state)


def build_entry_explainer_node(
    scanner: EntryScanner | None = None,
) -> Callable[[WayfinderState], WayfinderState]:
    def _node(state: WayfinderState) -> WayfinderState:
        repo_path = entry_repo_path_from_state(state)
        if repo_path is None:
            return entry_explainer_missing_repo_path()

        symbol = symbol_candidate_from_state(state)
        if symbol is None:
            return entry_explainer_missing_symbol_candidate()

        ast_result = scan_symbol_for_entry(repo_path, symbol, scanner=scanner)
        return entry_state_from_ast_result(ast_result)

    return _node


def entry_explainer_node(state: WayfinderState) -> WayfinderState:
    return build_entry_explainer_node()(state)


def build_verifier_node(
    test_runner: TestRunner | None = None,
) -> Callable[[WayfinderState], WayfinderState]:
    def _node(state: WayfinderState) -> WayfinderState:
        return verifier_state_from_state(state, test_runner=test_runner)

    return _node


def verifier_node(state: WayfinderState) -> WayfinderState:
    return build_verifier_node()(state)


def final_writer_node(state: WayfinderState) -> WayfinderState:
    query = state.get("query", "")
    repo_ref = state.get("repo_url", "unknown repo")
    partial_summaries = state.get("partial_summaries", {})
    entry_summary = partial_summaries.get("entry_explainer")
    verifier_summary = partial_summaries.get("verifier")
    if entry_summary is not None:
        verification_section = (
            f"\n\n{verifier_summary}" if verifier_summary is not None else ""
        )
        return apply_resilience_to_final_output(
            state,
            (
                f"Entry explanation for {repo_ref}: {query}\n\n"
                f"{entry_summary}{verification_section}"
            ),
        )

    if verifier_summary is not None:
        return apply_resilience_to_final_output(
            state,
            f"Verification result for {repo_ref}: {query}\n\n{verifier_summary}",
        )

    return apply_resilience_to_final_output(
        state,
        f"Placeholder final output for {repo_ref}: {query}",
    )
