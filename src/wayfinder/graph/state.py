"""State contracts for the Wayfinder graph."""

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

Intent = Literal["architectural", "runtime", "behavioral", "debug", "mixed"]
RiskLevel = Literal["low", "medium", "high"]
TestStrategy = Literal["existing_test", "generate_test", "skip"]
ClaimStatus = Literal["pending", "verified", "unverified", "contradicted"]


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


class WayfinderState(TypedDict, total=False):
    """Shared state passed through the Supervisor workflow."""

    query: str
    repo_url: str
    intent: Intent
    repo_metadata: dict[str, object]
    module_dep_graph: dict[str, object] | None
    entry_points: list[str] | None
    ast_index: dict[str, object] | None
    pending_claims: list[Claim]
    verified_claims: list[Claim]
    unverified_claims: list[Claim]
    contradicted_claims: list[Claim]
    test_results: dict[str, TestResult] | None
    partial_summaries: dict[str, str]
    next_agent: str | None
    user_corrections: list[str]
    final_output: str | None
    messages: Annotated[list[BaseMessage], add_messages]
