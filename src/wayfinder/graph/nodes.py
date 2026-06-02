"""Placeholder nodes for the Commit 2 Supervisor graph."""

from collections.abc import Callable

from wayfinder.graph.architecture import (
    ArchitectureScanner,
    architect_mapper_missing_repo_path,
    architecture_state_from_scan_result,
    repo_path_from_state,
    scan_repo_for_architecture,
)
from wayfinder.graph.routing import build_route_decision
from wayfinder.graph.state import WayfinderState


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
        repo_path = repo_path_from_state(state)

        if repo_path is None:
            return architect_mapper_missing_repo_path()

        scan_result = scan_repo_for_architecture(repo_path, scanner=scanner)
        return architecture_state_from_scan_result(scan_result)

    return _node


def architect_mapper_node(state: WayfinderState) -> WayfinderState:
    return build_architect_mapper_node()(state)


def entry_explainer_node(state: WayfinderState) -> WayfinderState:
    return {
        "partial_summaries": {
            "entry_explainer": "Placeholder entry explanation; real AST evidence comes later."
        },
        "next_agent": "final_writer",
    }


def verifier_node(state: WayfinderState) -> WayfinderState:
    return {
        "partial_summaries": {
            "verifier": "Placeholder verifier result; real test execution comes later."
        },
        "next_agent": "final_writer",
    }


def final_writer_node(state: WayfinderState) -> WayfinderState:
    query = state.get("query", "")
    repo_ref = state.get("repo_url", "unknown repo")
    return {
        "final_output": f"Placeholder final output for {repo_ref}: {query}",
        "next_agent": None,
    }
