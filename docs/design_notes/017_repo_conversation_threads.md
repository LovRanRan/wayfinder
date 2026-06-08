# 017 — Repo Conversation Threads + Memory Layer

## Problem

Wayfinder currently feels like a one-shot grounded synthesis panel. A user can
paste a repo, ask one question, and inspect the resulting evidence, but the
product does not yet provide a repo-scoped place to continue the investigation.

Commit 21 changes the primary surface from "submit independent runs" to "open a
repo thread and keep asking grounded follow-up questions." The important product
shift is not more dashboard metrics. It is conversation continuity over a stable
repo context.

## Target Interaction

Primary user story:

1. The user logs in to a workspace.
2. The user creates a thread for one GitHub repo or local repo reference.
3. The user asks an initial onboarding question.
4. Wayfinder runs the existing grounded graph and stores the answer as a thread
   message linked to that run.
5. The user asks follow-ups without re-pasting the repo URL:
   - where should I change this behavior?
   - explain this file or symbol;
   - what tests cover this path?
   - summarize what we learned so far.
6. The dashboard reopens the same thread after refresh and shows prior messages,
   linked runs, verification labels, and evidence chips.

## Non-goals

Commit 21 v1 is not:

- an autonomous coding agent;
- a full IDE or file editor;
- arbitrary shell execution;
- private GitHub repository support;
- ungrounded ChatGPT over a repo;
- a replacement for Project 7 evals.

## Thread Lifecycle

A thread belongs to one workspace user and one repo reference.

Thread creation accepts `repo_url`, optional `title`, and optional
`initial_query`. If `initial_query` is present, the API creates the thread,
stores a user message, starts a normal Wayfinder run for that repo/query, and
later stores the assistant answer linked to the run.

Follow-up creation accepts only message content. The server reads the thread's
repo reference, builds a bounded memory packet, starts a normal Wayfinder run
with the repo reference plus follow-up question, and stores the resulting
assistant answer as a new message.

Runs and threads stay related but separate:

- runs are execution traces, graph state, verifier labels, and latency/cost
  metadata;
- threads are the human conversation surface, including message history and
  memory summary.

## Data Model

`ConversationThread` fields:

- `thread_id`
- `user_id`
- `repo_url`
- `repo_name`
- `title`
- `status`: `active`, `running`, `failed`, or `archived`
- `created_at`
- `updated_at`
- `last_run_id`
- `summary_memory`

`ThreadMessage` fields:

- `message_id`
- `thread_id`
- `role`: `user`, `assistant`, or `system`
- `content`
- `created_at`
- `source_run_id`
- `evidence_refs`
- `verified_count`
- `unverified_count`
- `contradicted_count`
- `trace_metadata`

The SQLite store owns thread and message persistence in the same database as
workspace users, sessions, settings, and runs. In-memory dev mode mirrors the
same method contract for tests and local usage.

## Memory Policy

The memory layer is bounded by design. It can include:

- a short rolling `summary_memory`;
- the last N messages from the thread;
- selected evidence refs from linked runs;
- the latest repo packet: repo metadata, architecture summary, AST evidence,
  verification counts, sandbox status, and limitations.

It must not pass unbounded full thread history or raw full repository contents to
OpenAI. Memory-derived context must be labeled separately from newly collected
repo evidence.

Follow-up behavior:

- If a follow-up can be answered from prior memory, the assistant may summarize
  prior discussion but cannot create new verified code claims.
- If a follow-up asks for new repo facts, the API starts the same grounded
  graph/evidence path used by `/explain`.
- If the graph cannot verify a requested fact, the answer marks the claim
  `unverified` and suggests a narrower follow-up instead of guessing.

## API Contract

New endpoints:

- `POST /threads`
  - input: `repo_url`, optional `title`, optional `initial_query`;
  - output: thread metadata, messages, and optional queued run;
  - auth: current workspace user.
- `GET /threads`
  - output: user's repo threads with latest message and status.
- `GET /threads/{thread_id}`
  - output: thread metadata, messages, and linked runs visible to the user.
- `POST /threads/{thread_id}/messages`
  - input: follow-up content;
  - output: updated thread with the user message and queued run metadata.

Existing `/explain`, `/runs`, `/status/{job_id}`, and `/refine/{job_id}` remain
for backward compatibility and for run-level inspection.

## Dashboard IA

The main workspace surface becomes a conversation workbench:

- left sidebar: repo thread list;
- main header: selected repo, thread status, latest run, verification chips;
- timeline: user and assistant messages;
- evidence drawer or compact chips: linked run, verified/unverified/contradicted
  counts, MCP tool hints, trace metadata;
- bottom composer: follow-up question input.

Metrics and Settings remain workspace tabs, but the daily-use path should be
"open a thread and ask" rather than "fill a one-shot Run form."

## Failure Cases

- Missing thread: return 404.
- Thread belongs to another user: return 404, not leaked metadata.
- Thread has a queued/running run: allow message append only if the product
  explicitly supports concurrent runs; v1 rejects with 409 to keep ordering
  clear.
- Empty follow-up: 422 validation error.
- Initial run fails: store the user message, store an assistant/system failure
  message, and keep the thread visible.
- SQLite unavailable: API fails fast the same way current run persistence fails.
- Memory packet too large: trim older messages and keep a summary plus latest
  evidence refs.
- LLM unavailable: existing deterministic final writer remains the fallback.

## Tests

Backend tests:

- authenticated user can create a thread with an initial query;
- thread creation starts a run and links the run to the thread;
- follow-up message reuses the thread repo without re-pasting `repo_url`;
- completed run creates an assistant thread message with verification counts;
- users cannot list, read, or append to another user's thread;
- SQLite persistence survives store re-instantiation;
- bounded memory packet includes summary plus last messages and excludes
  unbounded history.

Frontend checks:

- thread list renders;
- selecting a thread renders message history;
- follow-up submit calls the thread message proxy;
- refresh can reopen the selected thread from URL state or latest thread.

## Interview Explanation

I separated execution traces from conversation state. A Wayfinder run is still
the grounded graph execution: repo scan, AST evidence, verifier labels, traces,
and limitations. A thread is the human workspace around a repo. The memory layer
does not replace grounding; it only provides bounded continuity, so follow-up
questions can reuse prior context while new code facts still go through the same
MCP/verifier path.
