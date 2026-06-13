"""Tests for the agent provenance trace built from the live claim flow."""

from wayfinder.graph.provenance import agent_trace_from_claims, agent_trace_from_state
from wayfinder.graph.state import Claim, WayfinderState


def _claim(agent: str, status: str) -> Claim:
    return {"text": f"{agent}-{status}", "source_agent": agent, "status": status}  # type: ignore[typeddict-item]


def test_groups_by_agent_and_counts_statuses() -> None:
    verified: list[Claim] = [_claim("symbol_investigator", "verified")]
    unverified: list[Claim] = [_claim("symbol_investigator", "unverified")]
    contradicted: list[Claim] = [_claim("repo_cartographer", "contradicted")]

    trace = agent_trace_from_claims(
        verified=verified,
        unverified=unverified,
        contradicted=contradicted,
    )

    by_agent = {row["agent"]: row for row in trace}
    assert by_agent["symbol_investigator"]["claims_made"] == 2
    assert by_agent["symbol_investigator"]["verified"] == 1
    assert by_agent["symbol_investigator"]["unverified"] == 1
    assert by_agent["repo_cartographer"]["contradicted"] == 1
    assert by_agent["repo_cartographer"]["claims_made"] == 1


def test_summary_text_is_present() -> None:
    trace = agent_trace_from_claims(
        verified=[_claim("symbol_investigator", "verified")],
        unverified=[],
        contradicted=[],
    )
    assert trace[0]["summary"] == (
        "symbol_investigator: 1 claim(s) — 1 verified, 0 unverified, 0 contradicted."
    )


def test_first_seen_order_is_deterministic() -> None:
    verified: list[Claim] = [_claim("repo_cartographer", "verified")]
    unverified: list[Claim] = [_claim("symbol_investigator", "unverified")]

    trace = agent_trace_from_claims(verified=verified, unverified=unverified, contradicted=[])

    assert [row["agent"] for row in trace] == ["repo_cartographer", "symbol_investigator"]


def test_empty_claims_produce_empty_trace() -> None:
    assert agent_trace_from_claims(verified=[], unverified=[], contradicted=[]) == []


def test_agent_trace_from_state_reads_claim_lists() -> None:
    state: WayfinderState = {
        "verified_claims": [_claim("symbol_investigator", "verified")],
        "unverified_claims": [_claim("symbol_investigator", "unverified")],
        "contradicted_claims": [],
    }

    trace = agent_trace_from_state(state)

    assert len(trace) == 1
    assert trace[0]["agent"] == "symbol_investigator"
    assert trace[0]["claims_made"] == 2


def test_agent_trace_from_empty_state() -> None:
    assert agent_trace_from_state({}) == []
