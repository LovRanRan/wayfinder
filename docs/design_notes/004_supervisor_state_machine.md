# 004 — Supervisor Graph + State Machine

## Problem

Commit 2 solves the problem of defining one stable `WayfinderState` contract
before real agents start producing codebase explanations. When a user gives
Wayfinder a repo and a query, the workflow should standardize the input, store
shared run context in state, and decide which agent should act next.

The first priority is the state contract. Routing is a decision made from that
state, not a separate pile of temporary dictionaries. This should prevent field
drift between agents, lost context after failures, unrecoverable runs, and a
verifier that does not know which claims it should process.

## Input

The external API may receive:

- `repo_url` or local repo path.
- `query`.
- optional `user_corrections`.
- optional `thread_id` / checkpoint id for resuming an existing run.

Inside the graph, Commit 2 should consume the standardized `RepoHandle` from the
Commit 1 ingestion layer plus the user query. Clone, cache, cleanup, and repo
size guard behavior are not Commit 2 responsibilities.

## Output

Commit 2 does not produce the final codebase explanation. It produces an updated
`WayfinderState` and graph run status:

- standardized repo/query context.
- detected `intent`.
- selected `next_agent`.
- placeholder summaries and claims.
- whether HITL may be needed.
- checkpointable thread/run state that can be resumed later.

Real architecture summaries, entry explanations, and verification results will
be filled by later agent commits.

## Rules

- `WayfinderState` is the only data contract. Agents should not invent their own
  temporary fields.
- Routing uses deterministic rules first. LLM fallback is only for cases rules
  cannot classify.
- Commit 2 agent nodes are placeholders for `architect_mapper`,
  `entry_explainer`, and `verifier`; they should not call real MCP tools or
  generate real explanations yet.
- `Claim` only defines the schema and queues in this commit. Real verification
  belongs to later commits.
- The graph must support checkpoint/resume behavior, with at least `thread_id`
  separating runs.
- Invalid intent or bad LLM routing output should fall back to a safe default or
  HITL correction path.
- Repo clone, cache, cleanup, and size guard logic stay in Commit 1's ingestion
  layer.

## Failure Cases

- User query is too vague for routing.
- Deterministic routing picks the wrong intent and later needs HITL correction.
- LLM fallback returns invalid JSON or an unsupported intent.
- `WayfinderState` is missing a required field.
- Checkpointer write or resume fails.
- `next_agent` points to a node that does not exist.
- Placeholder agent raises an exception.
- User correction changes intent and requires rerouting.

## Tests

Initial Commit 2 tests should cover:

- State schema tests for `WayfinderState` and `Claim` fields/defaults.
- Deterministic routing tests for architectural, runtime, behavioral, debug, and
  mixed queries.
- LLM fallback tests with mocked legal JSON, invalid JSON, and unsupported
  intent.
- Graph compile/run tests proving placeholder nodes can run through `next_agent`.
- Checkpointer tests proving the same `thread_id` can resume state and different
  `thread_id` values do not share state.
- Error tests for missing field, bad `next_agent`, and placeholder exception
  paths.

HITL / user-correction tests should stay in the design for now and become fuller
API-flow tests in later commits.

## Interview Explanation

I built the multi-agent system as a state machine first, not as agents chatting
with each other, because the state contract is what makes routing,
verification, resume, and tests controllable. The Supervisor is not for showing
off multi-agent complexity; it turns repo onboarding into testable routing and
state transitions.

Commit 2 intentionally uses placeholder nodes so I can prove the workflow is
recoverable, state moves correctly, routing is testable, and checkpoints work
before I connect the real MCP-backed agents.
