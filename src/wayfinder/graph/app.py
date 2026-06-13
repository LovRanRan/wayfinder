import os
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
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
    deterministic_final_writer_output,
)
from wayfinder.graph.routing import LLMRouter, build_safe_default_route_decision
from wayfinder.graph.state import AgentName, GraphError, WayfinderState
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


def route_after_architect(state: WayfinderState) -> str:
    """Continue a multi-worker plan to the symbol path, else finish.

    For single-worker (architectural) plans ``pending_workers`` is empty, so the
    edge behaves exactly like the old direct ``architect_mapper -> final_writer``.
    For a mixed plan the supervisor queued ``entry_explainer`` here, so the run
    fans out to the symbol path (and then the verifier) before final synthesis.
    """
    if "entry_explainer" in state.get("pending_workers", []):
        return "entry_explainer"
    return "final_writer"


def build_graph(
    checkpointer: GraphCheckpointer = None,
    *,
    architecture_scanner: ArchitectureScanner | None = None,
    entry_scanner: EntryScanner | None = None,
    verifier_runner: TestRunner | None = None,
    llm_router: LLMRouter | None = None,
    final_synthesizer: FinalSynthesizer | None = None,
    community_context_provider: CommunityContextProvider | None = None,
    node_timeout_seconds: float | None = None,
) -> WayfinderGraph:
    """Build the Commit 2 Supervisor graph skeleton."""
    # LangGraph's builder exposes incomplete type information to static checkers.
    # Keep that uncertainty at this boundary instead of leaking it into nodes/state.
    graph: Any = StateGraph(WayfinderState)
    active_node_timeout_seconds = (
        _graph_node_timeout_seconds_from_env()
        if node_timeout_seconds is None
        else node_timeout_seconds
    )

    graph.add_node(
        "supervisor",
        _with_node_timeout(
            "supervisor",
            build_supervisor_node(llm_router),
            active_node_timeout_seconds,
        ),
    )
    graph.add_node(
        "architect_mapper",
        _with_node_timeout(
            "architect_mapper",
            build_architect_mapper_node(architecture_scanner),
            active_node_timeout_seconds,
        ),
    )
    graph.add_node(
        "entry_explainer",
        _with_node_timeout(
            "entry_explainer",
            build_entry_explainer_node(entry_scanner),
            active_node_timeout_seconds,
        ),
    )
    graph.add_node(
        "verifier",
        _with_verifier_timeout_when_preapproved(
            build_verifier_node(verifier_runner),
            active_node_timeout_seconds,
        ),
    )
    graph.add_node(
        "final_writer",
        _with_node_timeout(
            "final_writer",
            build_final_writer_node(final_synthesizer, community_context_provider),
            active_node_timeout_seconds,
        ),
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
    graph.add_conditional_edges(
        "architect_mapper",
        route_after_architect,
        {
            "entry_explainer": "entry_explainer",
            "final_writer": "final_writer",
        },
    )
    graph.add_edge("entry_explainer", "verifier")
    graph.add_edge("verifier", "final_writer")
    graph.add_edge("final_writer", END)

    return cast(WayfinderGraph, graph.compile(checkpointer=checkpointer))


def _with_node_timeout(
    node_name: str,
    node: Callable[[WayfinderState], WayfinderState],
    timeout_seconds: float,
) -> Callable[[WayfinderState], WayfinderState]:
    if timeout_seconds <= 0:
        return node

    def _guarded(state: WayfinderState) -> WayfinderState:
        executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix=f"wayfinder-{node_name}",
        )
        future = executor.submit(node, state)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError:
            future.cancel()
            return _node_timeout_state(node_name, state, timeout_seconds)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    return _guarded


def _with_verifier_timeout_when_preapproved(
    node: Callable[[WayfinderState], WayfinderState],
    timeout_seconds: float,
) -> Callable[[WayfinderState], WayfinderState]:
    if timeout_seconds <= 0:
        return node

    timed_node = _with_node_timeout("verifier", node, timeout_seconds)

    def _guarded(state: WayfinderState) -> WayfinderState:
        approval_decision = state.get("verifier_approval_decision")
        if isinstance(approval_decision, Mapping):
            return timed_node(state)
        return node(state)

    return _guarded


def _node_timeout_state(
    node_name: str,
    state: WayfinderState,
    timeout_seconds: float,
) -> WayfinderState:
    message = f"{node_name} exceeded {timeout_seconds:g}s node timeout."
    error: GraphError = {
        "node": node_name,
        "error_type": "graph_node_timeout",
        "message": message,
        "retryable": True,
    }
    errors: list[GraphError] = [
        *state.get("errors", []),
        error,
    ]

    if node_name == "supervisor":
        route_decision = build_safe_default_route_decision(message)
        return {
            "intent": route_decision["intent"],
            "next_agent": route_decision["next_agent"],
            "route_decision": route_decision,
            "errors": errors,
        }

    if node_name == "final_writer":
        return {
            "final_output": (
                f"{deterministic_final_writer_output(state)}\n\n"
                f"Runtime limitation: {message}"
            ),
            "errors": errors,
        }

    partial_summaries = dict(state.get("partial_summaries", {}))
    partial_summaries[node_name] = (
        f"{node_name} timed out before producing complete evidence. "
        "Wayfinder is returning the safe available summary and marking this "
        "step as unverified."
    )
    return {
        "partial_summaries": partial_summaries,
        "errors": errors,
        "next_agent": "final_writer",
    }


def _graph_node_timeout_seconds_from_env() -> float:
    raw = os.getenv("WAYFINDER_GRAPH_NODE_TIMEOUT_SECONDS", "30").strip()
    try:
        timeout_seconds = float(raw)
    except ValueError:
        return 30.0
    if timeout_seconds <= 0:
        return 0.0
    return timeout_seconds
