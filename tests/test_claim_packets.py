"""Tests for claim packets and agent provenance (Commit 23, slice 1)."""

from wayfinder.graph.packets import (
    ClaimEvidence,
    ClaimPacket,
    build_agent_trace,
)


def _packet(
    claim: str,
    *,
    agent: str = "repo_cartographer",
    risk: str = "high",
    status: str = "pending",
    evidence: tuple[ClaimEvidence, ...] = (),
) -> ClaimPacket:
    return ClaimPacket(
        claim=claim,
        source_agent=agent,  # type: ignore[arg-type]
        risk_level=risk,  # type: ignore[arg-type]
        evidence=evidence,
        status=status,  # type: ignore[arg-type]
    )


def test_packet_defaults() -> None:
    packet = ClaimPacket(
        claim="build_graph wires the supervisor",
        source_agent="repo_cartographer",
        risk_level="medium",
    )
    assert packet.status == "pending"
    assert packet.evidence == ()
    assert packet.limitations == ()


def test_has_grounding_evidence_true_for_ast() -> None:
    packet = _packet(
        "x is defined at a.py:1",
        evidence=(ClaimEvidence(kind="ast", detail="found", source_tool="mcp-ast-explorer"),),
    )
    assert packet.has_grounding_evidence() is True


def test_community_evidence_is_not_grounding() -> None:
    packet = _packet(
        "library is popular",
        evidence=(ClaimEvidence(kind="community", detail="blog post"),),
    )
    assert packet.has_grounding_evidence() is False
    # Evidence is still preserved, just not treated as grounding.
    assert packet.evidence[0].kind == "community"


def test_build_agent_trace_groups_by_agent_and_counts_statuses() -> None:
    packets = (
        _packet("a", agent="repo_cartographer", status="verified"),
        _packet("b", agent="repo_cartographer", status="unverified"),
        _packet("c", agent="symbol_investigator", status="contradicted"),
        _packet("d", agent="symbol_investigator", status="verified"),
    )

    trace = build_agent_trace(packets)

    assert len(trace) == 2
    cartographer = trace[0]
    assert cartographer.agent == "repo_cartographer"
    assert cartographer.claims_made == 2
    assert cartographer.verified == 1
    assert cartographer.unverified == 1
    assert cartographer.contradicted == 0

    investigator = trace[1]
    assert investigator.agent == "symbol_investigator"
    assert investigator.claims_made == 2
    assert investigator.verified == 1
    assert investigator.contradicted == 1


def test_build_agent_trace_preserves_first_seen_order() -> None:
    packets = (
        _packet("a", agent="symbol_investigator"),
        _packet("b", agent="repo_cartographer"),
    )
    trace = build_agent_trace(packets)
    assert [c.agent for c in trace] == ["symbol_investigator", "repo_cartographer"]


def test_build_agent_trace_empty() -> None:
    assert build_agent_trace(()) == ()
