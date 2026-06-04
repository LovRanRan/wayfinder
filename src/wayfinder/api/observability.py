"""Runtime trace metadata helpers for the API boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import cast

from langchain_core.runnables import RunnableConfig

from wayfinder.graph.state import Claim, WayfinderState

TraceMetadataValue = str | int | float | bool | None
TraceMetadata = dict[str, TraceMetadataValue]

REQUIRED_TRACE_METADATA_KEYS = (
    "agent_name",
    "tool_name",
    "mcp_server",
    "tokens",
    "latency",
    "cost_usd",
    "claim_id",
)


@dataclass(frozen=True)
class TraceContext:
    job_id: str
    phase: str
    started_at: float
    metadata: TraceMetadata


def start_trace_context(
    *,
    job_id: str,
    phase: str,
    state: WayfinderState,
    env: Mapping[str, str],
) -> TraceContext:
    metadata = _with_required_trace_keys(
        {
            "job_id": job_id,
            "thread_id": job_id,
            "phase": phase,
            "status": "running",
            "langsmith_tracing": _env_flag(env.get("LANGSMITH_TRACING")),
            "langsmith_project": _non_empty(env.get("LANGSMITH_PROJECT")),
            **_state_metadata(state),
        }
    )
    return TraceContext(
        job_id=job_id,
        phase=phase,
        started_at=perf_counter(),
        metadata=metadata,
    )


def runnable_config_for_trace(context: TraceContext) -> RunnableConfig:
    return cast(
        RunnableConfig,
        {
            "configurable": {"thread_id": context.job_id},
            "metadata": context.metadata,
            "tags": ["wayfinder", f"phase:{context.phase}"],
        },
    )


def finish_trace_metadata(
    context: TraceContext,
    *,
    state: WayfinderState | None = None,
    error: Exception | None = None,
) -> TraceMetadata:
    latency_seconds = round(perf_counter() - context.started_at, 6)
    metadata = dict(context.metadata)
    if state is not None:
        metadata.update(_state_metadata(state))

    metadata["latency"] = latency_seconds
    metadata["status"] = "failed" if error is not None else "completed"
    if error is not None:
        metadata["error_type"] = type(error).__name__

    return _with_required_trace_keys(metadata)


def _state_metadata(state: WayfinderState) -> TraceMetadata:
    agent_name = _agent_name_from_state(state)
    tool_name, mcp_server = _tool_metadata_for_agent(agent_name)
    return {
        "agent_name": agent_name,
        "tool_name": tool_name,
        "mcp_server": mcp_server,
        "tokens": 0,
        "latency": 0.0,
        "cost_usd": 0.0,
        "claim_id": _claim_id_from_state(state),
    }


def _agent_name_from_state(state: WayfinderState) -> str:
    next_agent = state.get("next_agent")
    if isinstance(next_agent, str):
        return next_agent

    route_decision = state.get("route_decision")
    if isinstance(route_decision, dict):
        route_next = route_decision.get("next_agent")
        if isinstance(route_next, str):
            return route_next

    return "supervisor"


def _tool_metadata_for_agent(agent_name: str) -> tuple[str | None, str | None]:
    if agent_name == "architect_mapper":
        return "repo_structure", "repo_mapper"
    if agent_name == "entry_explainer":
        return "find_references", "ast_explorer"
    if agent_name == "verifier":
        return "run_pytest", "test_runner"
    return None, None


def _claim_id_from_state(state: WayfinderState) -> str | None:
    for key in (
        "pending_claims",
        "verified_claims",
        "unverified_claims",
        "contradicted_claims",
    ):
        claims = cast(list[Claim], state.get(key, []))
        for index, claim in enumerate(claims):
            claim_id = _claim_id(claim)
            if claim_id is not None:
                return claim_id
            if claim.get("text"):
                return f"{key}-{index}"

    return None


def _claim_id(claim: Claim) -> str | None:
    test_id = claim.get("test_id")
    if isinstance(test_id, str) and test_id:
        return test_id
    return None


def _with_required_trace_keys(metadata: TraceMetadata) -> TraceMetadata:
    normalized = dict(metadata)
    for key in REQUIRED_TRACE_METADATA_KEYS:
        normalized.setdefault(key, None)
    normalized.setdefault("tokens", 0)
    normalized.setdefault("latency", 0.0)
    normalized.setdefault("cost_usd", 0.0)
    return normalized


def _env_flag(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _non_empty(value: str | None) -> str | None:
    stripped = (value or "").strip()
    return stripped or None
