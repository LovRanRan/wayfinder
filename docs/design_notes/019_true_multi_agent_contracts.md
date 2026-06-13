# 019 — True multi-agent contracts (Commit 23, slice 1)

> Status: drafted by Cowork for Haichuan review. This is the first slice of
> Commit 23 "true multi-agent implementation deepening". It is intentionally
> **additive and graph-non-invasive**: it introduces the contracts and pure
> logic that later slices wire into the LangGraph fan-out. No existing module
> is edited, so the Commit 22.6 test suite stays green.

## Problem

Today Wayfinder is technically a supervisor + workers graph, but it behaves
like one persona: the supervisor routes to exactly **one** worker, each worker
emits prose into `partial_summaries`, and the verifier only runs after
`entry_explainer`. There is no shared, machine-checkable contract for "what a
worker produced", and the verifier cannot challenge a claim that another agent
made. For interviews this reads as "multi-node graph", not "multi-agent system".

Commit 23 closes that gap in five steps (roadmap):

1. Distinct role prompts/contracts per agent.
2. Supervisor plans that call more than one worker per question.
3. Worker outputs become claim/evidence/limitation packets, not prose.
4. A verifier challenge loop that can downgrade/contradict another agent's claim.
5. Tests proving multi-worker routing, challenge behaviour, and provenance.

**This slice delivers 1, 3, 4, and the provenance half of 5 as pure,
independently tested contracts.** The LangGraph rewiring for true parallel
fan-out (step 2 in full) is deliberately deferred to slice 2, because rewiring
the compiled graph blind (no local test execution available in this session)
is the highest-risk part and should be done with gates running.

## Contracts introduced

### Agent role (`graph/agents.py`)

`AgentRole` is a frozen dataclass giving each agent a **distinct** identity:

- `name`: one of `conversation_memory`, `supervisor`, `repo_cartographer`,
  `symbol_investigator`, `verification`, `final_synthesizer`.
- `mission`: one sentence on what only this agent is responsible for.
- `system_prompt`: the distinct persona/instructions (no shared prompt).
- `allowed_tools`: the MCP/tool surface this agent may use (least privilege).
- `output_contract`: what shape this agent must return.
- `graph_node`: the existing graph node it maps onto today (or `None` for the
  new conversation/supervisor roles), so the wiring slice has a translation map.

`repo_cartographer` ↔ `architect_mapper`, `symbol_investigator` ↔
`entry_explainer`, `verification` ↔ `verifier`, `final_synthesizer` ↔
`final_writer`. `conversation_memory` and `supervisor` are new first-class roles.

### Claim packet (`graph/packets.py`)

Workers stop returning prose and return a `ClaimPacket`:

- `claim`: the assertion text.
- `source_agent`: which `AgentRole` produced it.
- `risk_level`: reuses the existing `RiskLevel` (`low`/`medium`/`high`).
- `evidence`: tuple of `ClaimEvidence` (`kind` ∈ `ast`/`test`/`repo_structure`/
  `community`/`none`, plus `detail` and optional `source_tool`).
- `limitations`: tuple of explicit "what I cannot prove" strings.
- `status`: reuses the existing `ClaimStatus` (`pending` by default).

`build_agent_trace(packets)` groups packets by `source_agent` into
`AgentContribution` records (claims made / verified / unverified / contradicted
+ a one-line summary). That is the **provenance** the final synthesizer surfaces.

### Verifier challenge (`graph/challenge.py`)

The verifier becomes an adversary, not just a test runner:

- `VerifierEvidence(claim, test_status, detail)` where `test_status` ∈
  `passed` / `failed` / `contradicting` / `missing`.
- `challenge_claim(packet, evidence)` returns a `ChallengeOutcome(packet,
  action, reason)` where `action` ∈ `upheld` / `downgraded` / `contradicted`:
  - failing or contradicting test → **contradicted** (status `contradicted`).
  - passing test, OR deterministic `ast`/`repo_structure` evidence → **upheld**
    (status `verified`).
  - high-risk claim with only `none`/`community` evidence and no passing test →
    **downgraded** (status `unverified`). External/community context never
    upgrades a code claim — same policy as Commit 16.
  - otherwise upheld at its incoming status.
- `apply_challenges(packets, evidence_by_claim)` runs the rule over a batch.

## Failure cases handled

- A worker asserts a function that has no test and no AST evidence → downgraded
  to `unverified`, never silently accepted.
- Two workers contribute claims about the same area → provenance keeps them
  attributed separately; the trace shows who said what.
- Community/Tavily context attached as evidence → cannot move a claim to
  `verified`.
- Empty packet list → `build_agent_trace` returns `()`; `apply_challenges`
  returns `()`. No crashes.

## Tests (this slice)

- `test_agent_roles.py`: all 6 roles exist, prompts are distinct (no two share a
  `system_prompt`), `graph_node` map is correct, lookup raises on unknown.
- `test_claim_packets.py`: packet construction; `build_agent_trace` groups by
  agent and counts statuses; community-only evidence is preserved but flagged.
- `test_verifier_challenge.py`: failing→contradicted, passing→upheld/verified,
  high-risk+no-evidence→downgraded/unverified, ast-evidence→upheld/verified,
  community-only high-risk→downgraded; `apply_challenges` over a mixed batch.

## Deferred to slice 2 (needs gates running)

- Compile-time graph change so the supervisor can fan out to multiple workers
  for one query and merge their packets.
- Feeding `ClaimPacket`s through `WayfinderState` and into the verifier and
  final synthesizer nodes (touches state.py + nodes.py + app.py).
- API/dashboard surfacing of the provenance trace.

## Interview explanation

"Wayfinder isn't one prompt pretending to be many. Each agent has its own
mission, system prompt, and least-privilege tool set. Workers don't return
prose — they return claim packets with typed evidence and explicit limitations.
The verifier is adversarial: it can downgrade a high-risk claim to unverified
when there's no test or AST evidence, or contradict it outright when a test
fails. And every final answer carries a provenance trace of which agent made
which claim and how it was resolved. I shipped the contracts and the challenge
logic as pure, tested functions first, then wired them into the graph — so the
risky graph change rode on top of already-verified logic."
