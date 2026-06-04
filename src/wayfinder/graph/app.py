from typing import Any, Protocol, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, StateSnapshot

from wayfinder.graph.architecture import ArchitectureScanner
from wayfinder.graph.community_context import CommunityContextProvider
from wayfinder.graph.entry import EntryScanner
from wayfinder.graph.nodes import (
    build_architect_mapper_node,
    build_entry_explainer_node,
    build_final_writer_node,
    build_supervisor_node,
    build_verifier_node,
)
from wayfinder.graph.routing import LLMRouter
from wayfinder.graph.state import AgentName, WayfinderState
from wayfinder.graph.synthesis import FinalSynthesizer
from wayfinder.graph.verifier import TestRunner

GraphCheckpointer = bool | BaseCheckpointSaver[Any] | None


class WayfinderGraph(Protocol):
    """Supported graph interface used by the API layer and tests."""

    def invoke(
        self,
        input: WayfinderState | Command[object],
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


def build_graph(
    checkpointer: GraphCheckpointer = None,
    *,
    architecture_scanner: ArchitectureScanner | None = None,
    entry_scanner: EntryScanner | None = None,
    verifier_runner: TestRunner | None = None,
    llm_router: LLMRouter | None = None,
    final_synthesizer: FinalSynthesizer | None = None,
    community_context_provider: CommunityContextProvider | None = None,
) -> WayfinderGraph:
    """Build the Commit 2 Supervisor graph skeleton."""
    # LangGraph's builder exposes incomplete type information to static checkers.
    # Keep that uncertainty at this boundary instead of leaking it into nodes/state.
    graph: Any = StateGraph(WayfinderState)

    graph.add_node("supervisor", build_supervisor_node(llm_router))
    graph.add_node(
        "architect_mapper",
        build_architect_mapper_node(architecture_scanner),
    )
    graph.add_node(
        "entry_explainer",
        build_entry_explainer_node(entry_scanner),
    )
    graph.add_node("verifier", build_verifier_node(verifier_runner))
    graph.add_node(
        "final_writer",
        build_final_writer_node(final_synthesizer, community_context_provider),
    )

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
    graph.add_edge("entry_explainer", "verifier")
    graph.add_edge("verifier", "final_writer")
    graph.add_edge("final_writer", END)

    return cast(WayfinderGraph, graph.compile(checkpointer=checkpointer))
