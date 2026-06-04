# 009 — FastAPI Runtime + Observability

## Status

Commit 7 runtime/observability design completed on 2026-06-04 after reading the
FastAPI runtime docs, LangGraph persistence/thread docs, LangSmith tracing
docs, and the current Project 6 API shell.

This commit is intentionally narrow:turn the existing synchronous FastAPI shell
into a resumable in-process job runtime with deterministic observability
metadata. It does not introduce a distributed queue, dashboard UI, or production
trace backend configuration.

## Source-Backed Constraints

- FastAPI `BackgroundTasks` can be injected into a path operation and scheduled
  with `add_task()`. The response can return before the task finishes.
- FastAPI background tasks run in the same application process. That is enough
  for Commit 7, but not a replacement for a multi-worker production queue.
- LangGraph persistence is keyed by `RunnableConfig.configurable.thread_id`.
  Storing a `thread_id` in state is useful, but not sufficient for checkpoint
  reads/writes.
- Checkpointers save state at graph super-step boundaries and can preserve
  successful writes when a later node fails.
- LangSmith tracing can use runnable config metadata/tags and Python SDK
  instrumentation. Commit 7 should make metadata deterministic even when
  `LANGSMITH_TRACING` is disabled.
- LangSmith thread grouping expects a `thread_id`, `session_id`, or
  `conversation_id` metadata key on parent and child runs if token/cost
  aggregation should work by thread.

## Commit 7 Boundary

In scope:

- `/explain` creates a queued job and schedules graph execution in a FastAPI
  background task.
- `/status/{job_id}` returns the current run record, including status,
  current node, partial summaries, graph errors, counts, trace metadata, and
  final output.
- `/refine/{job_id}` persists a user correction, reuses the same `thread_id`,
  and re-enters the graph with `user_corrections` in state.
- The API compiles graph runs with an in-memory checkpointer for local resume
  semantics.
- Every graph invocation receives a `RunnableConfig` with stable trace metadata
  and tags.
- Every MCP tool call is wrapped at the `MCPAdapter.call_tool` boundary with an
  optional LangSmith tool span when `LANGSMITH_TRACING=true`.
- API tests cover lifecycle polling, refine/resume config, error
  serialization, scanner/env wiring, and trace metadata hooks.

Out of scope:

- Real distributed task queue, workers, broker, or multi-process safety.
- Persistent run store across server restarts. SQLite/Postgres runtime storage
  belongs to deploy hardening.
- Dashboard rendering. Commit 8 consumes the status and trace metadata shape.
- Real LangSmith credential provisioning or trace URL generation. Commit 7
  passes deterministic metadata; live trace links are a deploy/demo concern.
- New graph topology or node-level behavior changes.

## Problem

Before Commit 7, the API layer invoked the graph synchronously inside
`/explain`, returned the final output immediately, and stored only a minimal
`RunSummary`. `/refine` only appended text to the query;it did not re-enter the
graph, reuse a checkpointer thread, or persist corrections in state.

That made the API unsuitable for a real dashboard or demo. There was no reliable
polling lifecycle, no serialized partial/error state, and no stable
observability contract for Project 7 evals.

Commit 7 adds the runtime boundary needed before dashboard/deploy work.

## API Contract

### POST `/explain`

Input:

- `repo_url`:remote URL or local path.
- `query`:user request.

Behavior:

1. Build initial `WayfinderState` from the request.
2. Resolve a local repo handle if `repo_url` points to an existing local path.
3. Create `job_id = thread_id`.
4. Store a `queued` run.
5. Schedule background execution.
6. Return the queued `RunSummary` with HTTP 202.

The POST response is not the final answer. Clients must poll
`/status/{job_id}`.

### GET `/status/{job_id}`

Returns the stored `RunSummary`.

Important fields:

- `status`:queued, running, completed, or failed.
- `current_node`:best known runtime phase while queued/running.
- `partial_summaries`:latest graph summaries that are safe to show.
- `errors`:structured graph/API errors.
- `final_output`:final answer when completed.
- `trace_metadata`:deterministic keys for dashboard/eval.

### POST `/refine/{job_id}`

Input:

- `correction`:plain-language correction. Routing corrections such as
  `intent=behavioral` are accepted because Commit 6 already taught the
  supervisor to read `user_corrections`.

Behavior:

1. Reject missing jobs with 404.
2. Reject queued/running jobs with 409.
3. Append correction to `RunSummary.user_corrections`.
4. Append visible correction text to `RunSummary.query`.
5. Update stored graph input with the same `thread_id`.
6. Schedule a new background graph invocation with the same checkpointer
   thread.
7. Return queued `RunSummary` with HTTP 202.

## Runtime State

The API keeps two in-memory records:

- Public `RunSummary` keyed by `job_id`.
- Internal graph input keyed by `job_id`.

The internal graph input is necessary because a response model should not be
the only source of truth for resuming a graph. `/refine` needs the original
repo handle, `thread_id`, query, and all corrections.

The public `RunSummary` stays intentionally dashboard-friendly:

- status and current node for polling;
- final output and count fields for user display;
- partial summaries for progressive UI;
- structured errors for failure cards;
- corrections for auditability;
- trace metadata for LangSmith/dashboard/eval joins.

## Checkpointer Policy

Commit 7 uses a process-local `InMemorySaver`.

Reason:

- Existing tests already prove checkpointer isolation and SQLite persistence in
  the graph layer.
- Commit 7 only needs the API to pass the same `thread_id` through runtime
  config on initial and refine invocations.
- In-memory is deterministic, fast, and does not change deploy requirements
  before Commit 8.

Production note:

- A multi-worker deployment must replace this with SQLite/Postgres or a hosted
  LangGraph runtime. Otherwise a job may disappear if the process restarts or a
  request lands on a different worker.

## Observability Contract

Every runtime invocation creates trace metadata with these required keys:

```text
agent_name
tool_name
mcp_server
tokens
latency
cost_usd
claim_id
```

Additional stable keys:

```text
job_id
thread_id
phase
status
langsmith_tracing
langsmith_project
```

Policy:

- `thread_id` is the API `job_id`.
- `phase` is `explain` or `refine`.
- `agent_name`, `tool_name`, and `mcp_server` are inferred from the latest
  state when available;otherwise they default to the supervisor-level runtime.
- `tokens` and `cost_usd` are zero for local deterministic runs until an LLM
  provider is attached.
- `latency` is measured at the API graph invocation boundary.
- `claim_id` points to the first claim/test id when verifier state exists.

The API passes this metadata in the LangChain/LangGraph `RunnableConfig`, plus
tags:

```text
wayfinder
phase:<explain|refine>
```

With `LANGSMITH_TRACING=true`, LangSmith can consume these as trace metadata.
Without LangSmith credentials, tests still prove the metadata shape.

MCP tools are traced at the adapter boundary with a `tool` run named
`mcp:<tool_name>`. The wrapper is deliberately optional and no-op by default,
so local tests and offline runs do not require live LangSmith credentials.

## Error Serialization

Graph/API exceptions become:

```json
{
  "node": "supervisor",
  "error_type": "RuntimeError",
  "message": "...",
  "retryable": false
}
```

Existing graph-level `errors` are passed through when the graph completes. A
top-level exception marks the run `failed`, clears `current_node`, preserves
the error string in `RunSummary.error`, and sets
`trace_metadata.status = "failed"`.

## Test Matrix

- Health endpoint remains stable.
- `/explain` returns queued HTTP 202, then `/status` returns completed.
- `/refine` returns queued HTTP 202, reuses the same `thread_id`, and passes
  `user_corrections` into graph state.
- Missing job returns 404.
- Refine during queued/running state returns 409.
- Env scanner factories still inject architecture and entry scanners into
  `build_graph`.
- Local behavioral query still uses `EntryScanner` evidence through the API.
- Fake graph exception serializes to failed run with structured error payload.
- Trace metadata/config includes `thread_id`, LangSmith env flags, tags, and
  the required dashboard/eval keys.

## Interview Explanation

"Commit 7 is where Wayfinder becomes a product runtime instead of a direct
function call. The API creates a queued run, executes the LangGraph workflow in
a background task, persists status/error/output state for polling, and reuses
the same thread id when the user sends a refinement. Observability is treated
as a schema contract first:every run emits stable metadata keys even without
live LangSmith credentials, so the dashboard and Project 7 eval harness can
join by job id, thread id, agent, tool, MCP server, latency, tokens, cost, and
claim id."
