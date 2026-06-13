"""Structured worker outputs and provenance for the multi-agent graph (Commit 23).

Workers stop returning prose and return :class:`ClaimPacket` objects: a claim,
typed evidence, explicit limitations, and a status. :func:`build_agent_trace`
turns a batch of packets into per-agent :class:`AgentContribution` provenance
that the final synthesizer surfaces. Pure and additive — no graph wiring here.
"""

from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass, field

from wayfinder.graph.agents import AgentRoleName
from wayfinder.graph.state import ClaimStatus, RiskLevel

# Evidence kinds that deterministically ground a code claim. Community/external
# context is supporting-only and is intentionally excluded (Commit 16 policy).
GROUNDING_EVIDENCE_KINDS: frozenset[str] = frozenset({"ast", "test", "repo_structure"})


@dataclass(frozen=True)
class ClaimEvidence:
    """A single piece of evidence backing (or failing to back) a claim."""

    kind: str
    detail: str
    source_tool: str | None = None


@dataclass(frozen=True)
class ClaimPacket:
    """A worker's structured output: one claim with evidence and limitations."""

    claim: str
    source_agent: AgentRoleName
    risk_level: RiskLevel
    evidence: tuple[ClaimEvidence, ...] = ()
    limitations: tuple[str, ...] = ()
    status: ClaimStatus = "pending"

    def has_grounding_evidence(self) -> bool:
        """Return True if any deterministic (non-community) evidence is present."""
        return any(item.kind in GROUNDING_EVIDENCE_KINDS for item in self.evidence)


@dataclass(frozen=True)
class AgentContribution:
    """Per-agent provenance summary derived from that agent's claim packets."""

    agent: AgentRoleName
    claims_made: int
    verified: int
    unverified: int
    contradicted: int
    summary: str


@dataclass
class _Counts:
    made: int = 0
    verified: int = 0
    unverified: int = 0
    contradicted: int = 0
    claims: list[str] = field(default_factory=list)


def build_agent_trace(packets: Sequence[ClaimPacket]) -> tuple[AgentContribution, ...]:
    """Group packets by source agent into provenance contributions.

    Agents appear in first-seen order so the trace is deterministic.
    """
    counts_by_agent: OrderedDict[AgentRoleName, _Counts] = OrderedDict()
    for packet in packets:
        counts = counts_by_agent.setdefault(packet.source_agent, _Counts())
        counts.made += 1
        counts.claims.append(packet.claim)
        if packet.status == "verified":
            counts.verified += 1
        elif packet.status == "contradicted":
            counts.contradicted += 1
        elif packet.status == "unverified":
            counts.unverified += 1

    return tuple(
        AgentContribution(
            agent=agent,
            claims_made=counts.made,
            verified=counts.verified,
            unverified=counts.unverified,
            contradicted=counts.contradicted,
            summary=_contribution_summary(agent, counts),
        )
        for agent, counts in counts_by_agent.items()
    )


def _contribution_summary(agent: AgentRoleName, counts: _Counts) -> str:
    return (
        f"{agent}: {counts.made} claim(s) — "
        f"{counts.verified} verified, "
        f"{counts.unverified} unverified, "
        f"{counts.contradicted} contradicted."
    )
