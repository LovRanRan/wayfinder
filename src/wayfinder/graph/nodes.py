"""Placeholder nodes for the Commit 2 Supervisor graph."""

from wayfinder.graph.routing import build_route_decision
from wayfinder.graph.state import WayfinderState


def supervisor_node(state: WayfinderState) -> WayfinderState:
    route_decision = build_route_decision(state)
    return {
        "intent": route_decision["intent"],
        "next_agent": route_decision["next_agent"],
        "route_decision": route_decision,
    }


def architect_mapper_node(state: WayfinderState) -> WayfinderState:
    return {
        "partial_summaries": {
            "architect_mapper": "Placeholder architecture summary; real MCP mapping comes later."
        },
        "next_agent": "final_writer",
    }


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
