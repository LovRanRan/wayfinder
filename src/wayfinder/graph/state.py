"""State contracts for the Wayfinder graph."""

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from wayfinder.ingestion.models import RepoHandle

AgentName = Literal["architect_mapper", "entry_explainer", "verifier", "final_writer"]
RoutingSource = Literal["rule", "llm", "user_correction", "safe_default"]
Intent = Literal["architectural", "runtime", "behavioral", "debug", "mixed"]
RiskLevel = Literal["low", "medium", "high"]
TestStrategy = Literal["existing_test", "generate_test", "skip"]
ClaimStatus = Literal["pending", "verified", "unverified", "contradicted"]


def merge_summaries(left: dict[str, str], right: dict[str, str]) -> dict[str, str]:
    """Accumulate per-agent partial summaries instead of overwriting.

    Used as the ``partial_summaries`` channel reducer so a multi-worker plan
    (Commit 23) keeps every worker's summary when workers run in sequence.
    Behaviour for a single worker is unchanged (merge into an empty/absent map).
    """
    merged = dict(left)
    merged.update(right)
    return merged


class RouteDecision(TypedDict):
    intent: Intent
    next_agent: AgentName
    source: RoutingSource
    reason: str
    needs_human_review: bool


class GraphError(TypedDict):
    node: str
    error_type: str
    message: str
    retryable: bool


class Claim(TypedDict, total=False):
    """A testable or explicitly untestable code-understanding claim."""

    text: str
    source_agent: str
    risk_level: RiskLevel
    test_strategy: TestStrategy
    test_id: str | None
    status: ClaimStatus


class TestResult(TypedDict, total=False):
    """Normalized test result attached to a claim."""

    status: Literal["passed", "failed", "skipped", "timed_out"]
    output: str
    claim_ref: str | None


class CommunityContextItem(TypedDict):
    """External context that supports but never verifies code facts."""

    source: str
    title: str
    snippet: str
    url: str | None


class WayfinderState(TypedDict, total=False):
    query: str
    repo_url: str
    repo_handle: RepoHandle
    thread_id: str
    user_id: str
    conversation_thread_id: str
    source_message_id: str
    conversation_memory: str

    intent: Intent
    route_decision: RouteDecision
    next_agent: AgentName | None
    # Graph nodes to run after the first worker, for multi-worker plans (Commit 23).
    pending_workers: list[str]

    repo_metadata: dict[str, object]
    module_dep_graph: dict[str, object] | None
    entry_points: list[str] | None
    ast_index: dict[str, object] | None

    pending_claims: list[Claim]
    verified_claims: list[Claim]
    unverified_claims: list[Claim]
    contradicted_claims: list[Claim]

    test_results: dict[str, TestResult]
    community_context: list[CommunityContextItem]
    partial_summaries: Annotated[dict[str, str], merge_summaries]
    user_corrections: list[str]
    verifier_approval_decision: dict[str, object]
    errors: list[GraphError]
    final_output: str | None

    messages: Annotated[list[BaseMessage], add_messages]
