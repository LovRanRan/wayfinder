from typing import Any, Protocol, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import StateSnapshot

from wayfinder.graph.nodes import (
    architect_mapper_node,
    entry_explainer_node,
    final_writer_node,
    supervisor_node,
    verifier_node,
)
from wayfinder.graph.state import AgentName, WayfinderState

GraphCheckpointer = bool | BaseCheckpointSaver[Any] | None


class WayfinderGraph(Protocol):
    """Supported graph interface used by the API layer and tests."""

    def invoke(
        self,
        input: WayfinderState,
        config: RunnableConfig | None = None,
    ) -> WayfinderState: ...

    def get_state(self, config: RunnableConfig) -> StateSnapshot: ...


def route_from_supervisor(state: WayfinderState) -> AgentName:
    """Return the next placeholder agent selected by the supervisor."""
    next_agent = state.get("next_agent")
    if next_agent in ("architect_mapper", "entry_explainer", "verifier"):
        return next_agent

    # Commit 2 safe default: if routing is missing or invalid, use architecture path.
    return "architect_mapper"


def build_graph(checkpointer: GraphCheckpointer = None) -> WayfinderGraph:
    """Build the Commit 2 Supervisor graph skeleton."""
    # LangGraph's builder exposes incomplete type information to static checkers.
    # Keep that uncertainty at this boundary instead of leaking it into nodes/state.
    graph: Any = StateGraph(WayfinderState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("architect_mapper", architect_mapper_node)
    graph.add_node("entry_explainer", entry_explainer_node)
    graph.add_node("verifier", verifier_node)
    graph.add_node("final_writer", final_writer_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "architect_mapper": "architect_mapper",
            "entry_explainer": "entry_explainer",
            "verifier": "verifier",
        },
    )
    graph.add_edge("architect_mapper", "final_writer")
    graph.add_edge("entry_explainer", "final_writer")
    graph.add_edge("verifier", "final_writer")
    graph.add_edge("final_writer", END)

    return cast(WayfinderGraph, graph.compile(checkpointer=checkpointer))
