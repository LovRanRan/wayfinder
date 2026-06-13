"""Tests for the verifier challenge loop (Commit 23, slice 1)."""

from wayfinder.graph.challenge import (
    VerifierEvidence,
    apply_challenges,
    challenge_claim,
)
from wayfinder.graph.packets import ClaimEvidence, ClaimPacket


def _packet(
    claim: str,
    *,
    risk: str = "high",
    evidence: tuple[ClaimEvidence, ...] = (),
) -> ClaimPacket:
    return ClaimPacket(
        claim=claim,
        source_agent="symbol_investigator",
        risk_level=risk,  # type: ignore[arg-type]
        evidence=evidence,
    )


def test_failing_test_contradicts_claim() -> None:
    packet = _packet("parse() returns a dict")
    evidence = VerifierEvidence(claim=packet.claim, test_status="failed", detail="assert err")
    outcome = challenge_claim(packet, evidence)
    assert outcome.action == "contradicted"
    assert outcome.packet.status == "contradicted"


def test_contradicting_test_contradicts_claim() -> None:
    packet = _packet("retry() never raises")
    evidence = VerifierEvidence(claim=packet.claim, test_status="contradicting")
    outcome = challenge_claim(packet, evidence)
    assert outcome.action == "contradicted"
    assert outcome.packet.status == "contradicted"


def test_passing_test_upholds_and_verifies() -> None:
    packet = _packet("validate() rejects empty input")
    evidence = VerifierEvidence(claim=packet.claim, test_status="passed")
    outcome = challenge_claim(packet, evidence)
    assert outcome.action == "upheld"
    assert outcome.packet.status == "verified"


def test_ast_evidence_upholds_without_a_test() -> None:
    packet = _packet(
        "build_graph is defined at app.py:53",
        evidence=(ClaimEvidence(kind="ast", detail="found", source_tool="mcp-ast-explorer"),),
    )
    outcome = challenge_claim(packet, None)
    assert outcome.action == "upheld"
    assert outcome.packet.status == "verified"


def test_high_risk_claim_without_evidence_is_downgraded() -> None:
    packet = _packet("the cache evicts on write")
    outcome = challenge_claim(packet, VerifierEvidence(claim=packet.claim, test_status="missing"))
    assert outcome.action == "downgraded"
    assert outcome.packet.status == "unverified"


def test_high_risk_claim_with_no_evidence_object_is_downgraded() -> None:
    packet = _packet("the worker mutates shared state")
    outcome = challenge_claim(packet, None)
    assert outcome.action == "downgraded"
    assert outcome.packet.status == "unverified"


def test_community_only_high_risk_claim_is_downgraded() -> None:
    packet = _packet(
        "this is the standard pattern",
        evidence=(ClaimEvidence(kind="community", detail="blog"),),
    )
    outcome = challenge_claim(packet, None)
    assert outcome.action == "downgraded"
    assert outcome.packet.status == "unverified"


def test_low_risk_claim_without_evidence_is_left_alone() -> None:
    packet = _packet("the module has a docstring", risk="low")
    outcome = challenge_claim(packet, None)
    assert outcome.action == "upheld"
    assert outcome.packet.status == "pending"


def test_apply_challenges_over_mixed_batch() -> None:
    packets = (
        _packet("a() returns None"),
        _packet(
            "b is defined at b.py:1",
            evidence=(ClaimEvidence(kind="ast", detail="found"),),
        ),
        _packet("c() raises on bad input"),
    )
    evidence_by_claim = {
        "a() returns None": VerifierEvidence(claim="a() returns None", test_status="passed"),
        "c() raises on bad input": VerifierEvidence(
            claim="c() raises on bad input", test_status="failed"
        ),
    }

    outcomes = apply_challenges(packets, evidence_by_claim)

    assert [o.action for o in outcomes] == ["upheld", "upheld", "contradicted"]
    assert [o.packet.status for o in outcomes] == ["verified", "verified", "contradicted"]
