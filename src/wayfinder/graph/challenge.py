"""Verifier challenge loop for the multi-agent graph (Commit 23).

The verification agent is adversarial: given a worker's :class:`ClaimPacket`
and the verifier's evidence, it can uphold, downgrade, or contradict the claim
before final synthesis. Pure functions only; no graph wiring or tool calls.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from wayfinder.graph.packets import ClaimPacket

VerifierTestStatus = Literal["passed", "failed", "contradicting", "missing"]
ChallengeAction = Literal["upheld", "downgraded", "contradicted"]


@dataclass(frozen=True)
class VerifierEvidence:
    """What the verifier found for a specific claim."""

    claim: str
    test_status: VerifierTestStatus
    detail: str = ""


@dataclass(frozen=True)
class ChallengeOutcome:
    """The verifier's ruling on a claim packet."""

    packet: ClaimPacket
    action: ChallengeAction
    reason: str


def challenge_claim(
    packet: ClaimPacket,
    evidence: VerifierEvidence | None,
) -> ChallengeOutcome:
    """Rule on a single claim packet given the verifier's evidence.

    Policy:
      * failing / contradicting test -> contradicted.
      * passing test -> upheld (verified).
      * deterministic ast/repo_structure evidence -> upheld (verified).
      * high-risk claim with no grounding evidence and no passing test ->
        downgraded (unverified). Community context never upgrades a claim.
      * otherwise -> upheld at the packet's incoming status.
    """
    if evidence is not None and evidence.test_status in ("failed", "contradicting"):
        return ChallengeOutcome(
            packet=replace(packet, status="contradicted"),
            action="contradicted",
            reason=evidence.detail or f"verifier test {evidence.test_status}",
        )

    if evidence is not None and evidence.test_status == "passed":
        return ChallengeOutcome(
            packet=replace(packet, status="verified"),
            action="upheld",
            reason=evidence.detail or "verifier test passed",
        )

    if packet.has_grounding_evidence():
        return ChallengeOutcome(
            packet=replace(packet, status="verified"),
            action="upheld",
            reason="deterministic ast/repo evidence",
        )

    if packet.risk_level == "high":
        return ChallengeOutcome(
            packet=replace(packet, status="unverified"),
            action="downgraded",
            reason="high-risk claim with no test or deterministic evidence",
        )

    return ChallengeOutcome(
        packet=packet,
        action="upheld",
        reason="low/medium-risk claim left at incoming status",
    )


def apply_challenges(
    packets: Sequence[ClaimPacket],
    evidence_by_claim: Mapping[str, VerifierEvidence],
) -> tuple[ChallengeOutcome, ...]:
    """Challenge every packet, keyed by claim text, preserving input order."""
    return tuple(
        challenge_claim(packet, evidence_by_claim.get(packet.claim)) for packet in packets
    )
