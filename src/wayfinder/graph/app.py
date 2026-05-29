"""Minimal LangGraph app shell for Commit 0."""

from typing import Protocol, cast

from langgraph.graph import END, START, StateGraph

from wayfinder.graph.state import WayfinderState


class WayfinderGraph(Protocol):
    """Supported graph interface used by the API layer and tests."""

    def invoke(self, input: WayfinderState) -> WayfinderState: ...


def bootstrap_node(state: WayfinderState) -> WayfinderState:
    """Return a deterministic placeholder summary until real agents are wired."""
    query = state.get("query", "")
    repo_url = state.get("repo_url", "")
    return {
        "intent": "mixed",
        "repo_metadata": {"repo_url": repo_url, "scaffold": True},
        "pending_claims": [],
        "verified_claims": [],
        "unverified_claims": [],
        "contradicted_claims": [],
        "partial_summaries": {
            "bootstrap": "Commit 0 scaffold compiled; agent nodes are not wired yet."
        },
        "next_agent": None,
        "final_output": f"Wayfinder scaffold accepted query for {repo_url}: {query}",
    }


def build_graph() -> WayfinderGraph:
    """Build the current LangGraph workflow."""
    graph = StateGraph(WayfinderState)
    graph.add_node("bootstrap", bootstrap_node)
    graph.add_edge(START, "bootstrap")
    graph.add_edge("bootstrap", END)
    return cast(WayfinderGraph, graph.compile())
