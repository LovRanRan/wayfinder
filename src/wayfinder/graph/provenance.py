"""Agent provenance trace built from the live claim flow (Commit 23 slice 2c).

The compiled graph resolves claims as ``Claim`` TypedDicts into
``verified_claims`` / ``unverified_claims`` / ``contradicted_claims``. This
module turns those into a serializable per-agent provenance trace
(``list[dict]``) that the final synthesizer attaches to state and the API can
surface — without putting non-serializable dataclasses into the checkpointer.
"""

from collections import OrderedDict
from collections.abc import Sequence

from wayfinder.graph.state import Claim, WayfinderState


def agent_trace_from_state(state: WayfinderState) -> list[dict[str, object]]:
    """Build the provenance trace from a state's resolved claim lists."""
    return agent_trace_from_claims(
        verified=state.get("verified_claims", []),
        unverified=state.get("unverified_claims", []),
        contradicted=state.get("contradicted_claims", []),
    )


def agent_trace_from_claims(
    *,
    verified: Sequence[Claim],
    unverified: Sequence[Claim],
    contradicted: Sequence[Claim],
) -> list[dict[str, object]]:
    """Group resolved claims by source agent into serializable provenance rows.

    Agents appear in first-seen order (verified, then unverified, then
    contradicted) so the trace is deterministic.
    """
    counts: OrderedDict[str, dict[str, int]] = OrderedDict()

    def _bump(claims: Sequence[Claim], key: str) -> None:
        for claim in claims:
            agent = str(claim.get("source_agent", "unknown"))
            entry = counts.setdefault(
                agent,
                {"verified": 0, "unverified": 0, "contradicted": 0},
            )
            entry[key] += 1

    _bump(verified, "verified")
    _bump(unverified, "unverified")
    _bump(contradicted, "contradicted")

    trace: list[dict[str, object]] = []
    for agent, entry in counts.items():
        made = entry["verified"] + entry["unverified"] + entry["contradicted"]
        trace.append(
            {
                "agent": agent,
                "claims_made": made,
                "verified": entry["verified"],
                "unverified": entry["unverified"],
                "contradicted": entry["contradicted"],
                "summary": (
                    f"{agent}: {made} claim(s) — "
                    f"{entry['verified']} verified, "
                    f"{entry['unverified']} unverified, "
                    f"{entry['contradicted']} contradicted."
                ),
            }
        )
    return trace
