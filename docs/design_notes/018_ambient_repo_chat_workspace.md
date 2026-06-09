# 018 — Ambient Repo Chat Workspace

## Problem

Commit 21 made Wayfinder conversational, but the interaction is still too much
like a form-driven analysis product. The user still has to think in terms of:

1. create a repo thread;
2. paste a repo URL;
3. write an initial question;
4. wait for a structured answer;
5. then continue inside that thread.

That is better than a one-shot report, but it is not yet the product shape the
user wants. The target is closer to Codex or ChatGPT: open a workspace, talk
naturally, and let the system carry the relevant repo context through every
turn.

Commit 22 changes the product from "repo link plus question" to "ambient
repo-aware chat." The repo becomes the active environment, not a field the user
re-enters.

## Product Decision

Wayfinder should behave like a repo-aware chat workspace:

- the main screen is a persistent chat composer;
- the workspace has an active repo context;
- the user can attach or switch repos once, preferably through natural chat or a
  small repo switcher, not a large form;
- every later message inherits the active repo context;
- Wayfinder chooses whether to answer conversationally, run grounded repo
  analysis, ask a clarification question, or render a structured report;
- evidence, runs, files, and settings stay visible as supporting panels, not as
  the primary workflow.

The product should still preserve Wayfinder's differentiator: new code facts
must be grounded in repo structure, AST evidence, or test/sandbox observations.
Natural chat is a better interface, not a license to hallucinate.

## Framing Correction

Project 5 MCP servers are not agents. They are deterministic tool/fact sources:

- `mcp-repo-mapper`: repository structure facts;
- `mcp-ast-explorer`: symbol, definition, call, and AST facts;
- `mcp-test-runner`: executable test and verification facts.

They do not need to call an LLM to be valuable, and Wayfinder should not claim
that the three MCPs are three agents. The honest stack is:

- Project 5: MCP-backed deterministic fact layer;
- Project 6: repo-aware grounded LLM copilot / agent workspace;
- Project 7: evaluation layer for the copilot and verification strategy.

Therefore Commit 22 should frame the product as:

> `wayfinder` is a grounded repo-aware copilot with multi-agent orchestration
> over deterministic MCP tools.

The multi-agent claim belongs to Project 6's LangGraph roles and workflow
coordination: supervisor routing, architecture mapping, entry explanation,
verification, final synthesis, memory, and clarification loops. The MCP tools
provide evidence; they are not themselves the reasoning agents.

## Multi-Agent Product Shape

Target title:

> `wayfinder` is a multi-agent repo onboarding copilot with MCP-grounded
> verification.

This is stronger and more honest than saying the MCP servers are agents. The
agents live in Project 6. The MCPs are the tools those agents use.

Agent roster:

- `conversation_memory_agent`
  - Job: resolve the user's workspace, active repo, selected thread,
    `active_focus`, recent summary memory, and whether the message needs a
    clarification before any repo work starts.
  - Inputs: authenticated user, raw chat message, optional pasted repo URL,
    current workspace context, recent thread summary.
  - Outputs: `ChatContextPacket` with repo/thread/focus, context confidence,
    missing-context flags, and safe memory summary.
- `supervisor_agent`
  - Job: decide the next route and worker plan.
  - Inputs: `ChatContextPacket`, user message, answer mode, latest repo packet,
    known limitations.
  - Outputs: route plan such as `chat_only`, `repo_orientation`,
    `architecture_map`, `symbol_investigation`, `verification_required`,
    `structured_report`, or `clarification`.
- `repo_cartographer_agent`
  - Job: explain repository structure, modules, entry points, and onboarding
    path.
  - Primary tools: `mcp-repo-mapper` and repo packet summaries.
  - Outputs: architecture claims, file/module evidence refs, limitations, and
    recommended next inspection path.
- `symbol_investigator_agent`
  - Job: inspect functions, classes, call paths, definitions, entry behavior, and
    code-level data flow.
  - Primary tools: `mcp-ast-explorer`.
  - Outputs: symbol claims, definition refs, caller/callee refs, path evidence,
    and unresolved symbol warnings.
- `verification_agent`
  - Job: challenge high-risk claims from the other agents.
  - Primary tools: `mcp-test-runner`, sandbox worker, and existing verifier
    policy.
  - Outputs: `verified`, `unverified`, or `contradicted` labels, test evidence,
    execution errors, and downgrade instructions.
- `final_synthesizer_agent`
  - Job: write the user-facing answer in the selected mode.
  - Primary tools: bounded worker outputs, evidence refs, verifier labels, and
    conversation memory.
  - Outputs: natural answer, structured grounded report, evidence summary,
    limitations, and follow-up suggestions.
- `external_context_scout` (optional/supporting)
  - Job: gather external context from community MCPs such as Tavily or GitHub
    search.
  - Outputs: external context snippets only. These can support onboarding but
    cannot override Project 5 repo facts.

Minimum agent output contract:

```json
{
  "agent_name": "symbol_investigator_agent",
  "task": "Inspect wayfinder.graph.app.build_graph",
  "claims": ["..."],
  "evidence_refs": ["..."],
  "limitations": ["..."],
  "needs_verification": true,
  "handoff_summary": "...",
  "next_questions": ["..."]
}
```

Collaboration loop:

1. User sends a natural chat message.
2. `conversation_memory_agent` resolves repo/thread/focus.
3. `supervisor_agent` chooses one or more worker agents.
4. Worker agents collect grounded partial outputs from MCP evidence.
5. `verification_agent` reviews high-risk claims before they become final.
6. `final_synthesizer_agent` writes the answer or report.
7. The UI records an agent trace: who contributed, which tools were used, what
   was verified, and what stayed uncertain.

Commit boundary:

- Commit 22 should expose the multi-agent workspace shape: chat surface, active
  context, message history, agent trace attachments, and route metadata.
- Commit 22 does not need to fully rewrite every existing graph node into a new
  prompt/schema implementation.
- Commit 23 should deepen the agent implementation: distinct prompts/contracts,
  supervisor worker planning, multi-worker routing, verification challenge loop,
  and agent contribution tests.

## Target Interaction

First-use flow:

1. The user logs in.
2. The user lands in a Codex-like workspace: left repo/thread rail, center chat,
   right evidence/context rail.
3. The composer is focused by default.
4. The user can type something like:
   - `Open https://github.com/pallets/click`
   - `Use LovRanRan/wayfinder`
   - `Help me understand this repo`
5. Wayfinder detects the repo reference, attaches it as the active repo context,
   creates or selects the default repo thread, and replies with a short
   orientation or starts grounded analysis if needed.
6. The user continues with normal messages:
   - `Where should I start?`
   - `Explain the command execution path.`
   - `What files should I inspect first?`
   - `Show me the evidence behind that.`
   - `Give me the structured report version.`
7. The user does not re-enter the repo URL or choose a separate question field.

Returning-user flow:

1. The dashboard restores the last active repo context and selected thread.
2. The top context bar shows the active repo and status.
3. The user can immediately ask a follow-up.
4. If the user switches repos, Wayfinder clearly changes the active context and
   prevents memory/evidence from repo A leaking into repo B.

## What Changes From Commit 21

Commit 21 introduced repo-scoped `ConversationThread` and `ThreadMessage`.
Commit 22 keeps those objects but changes what they mean in the UI:

- Commit 21: user creates a thread from `repo_url` plus `initial_query`.
- Commit 22: user sends chat messages; the server resolves the active repo
  context and routes the message into the right thread/run behavior.

Commit 22 should not delete `/threads` or `/explain`. It should add a higher
level product facade over them.

## Non-goals

Commit 22 v1 is not:

- a full IDE or file editor;
- autonomous code modification;
- private GitHub OAuth;
- multi-branch local working tree management;
- arbitrary shell execution;
- a clone of any specific product's branding or exact UI;
- ungrounded chat over code facts.

The goal is to copy the useful interaction pattern: persistent workspace,
active context, natural chat, side-panel evidence, and visible state.

## Core Concepts

### Workspace

A workspace belongs to one authenticated user. It owns:

- user profile;
- runtime settings and BYOK settings;
- repo contexts;
- conversation threads;
- grounded runs;
- recent activity and metrics.

### Active Repo Context

`ActiveRepoContext` is the missing product object. It is the current repo
environment for chat.

Proposed fields:

- `context_id`
- `user_id`
- `repo_url`
- `repo_name`
- `repo_ref`: optional branch, tag, or commit when known
- `default_thread_id`
- `last_run_id`
- `status`: `empty`, `resolving`, `ready`, `running`, or `failed`
- `summary_memory`
- `last_repo_packet`: bounded repo metadata, key files, AST evidence refs,
  verification counts, sandbox status, and limitations
- `active_focus`: optional focused file, symbol, or run target from the latest
  grounded answer
- `selected_files`: optional user-selected file paths
- `selected_symbols`: optional user-selected symbols
- `created_at`
- `updated_at`

This can be persisted as a new table later. For a narrow first implementation,
it can be derived from the latest selected thread plus an explicit
`active_thread_id` / `active_repo_url` preference in the existing store. The
design should keep the boundary clear even if v1 storage is simple.

### Conversation Thread

Threads remain the human transcript for one repo context. A repo context may
have one default thread in v1. Later, a repo can have multiple named threads:
architecture, debugging, onboarding, test strategy, and so on.

### Run

Runs remain grounded graph executions. They are not the UI's primary object,
but every code-fact-heavy assistant answer can link to a run.

## Chat Request Contract

The product-level chat request should be higher level than `/threads`.

Proposed request:

```json
{
  "content": "Explain the command execution path.",
  "thread_id": "optional existing thread id",
  "repo_url": "optional repo reference if the user pasted one in chat",
  "answer_mode": "auto"
}
```

`answer_mode` values:

- `auto`: Wayfinder chooses the right response shape.
- `conversation`: short, natural answer.
- `report`: structured Wayfinder output.
- `evidence`: evidence-first deep dive.
- `clarify`: server asks a targeted question when context is missing.

Proposed response:

```json
{
  "thread": "...",
  "messages": ["..."],
  "active_context": "...",
  "active_run": "...",
  "route": {
    "intent": "repo_question",
    "answer_mode": "report",
    "reason": "question asks for code behavior"
  }
}
```

The route object is important for debugging and interview explanation. It shows
why the product chose chat-only, grounded run, report, or clarification.

## API Direction

Commit 22 should add a product-level facade while preserving current endpoints.

Preferred v1 API:

- `GET /workspace/context`
  - returns the active repo context, latest thread, and current limitations.
- `POST /workspace/context`
  - sets or switches the active repo context from `repo_url` or `thread_id`.
- `POST /chat`
  - accepts natural chat content and optional context hints;
  - resolves active repo context;
  - creates/selects a thread;
  - appends the user message;
  - decides route/answer mode;
  - starts a grounded run only when needed.

Current endpoints remain:

- `/threads`
- `/threads/{thread_id}`
- `/threads/{thread_id}/messages`
- `/explain`
- `/runs`
- `/status/{job_id}`
- `/workspace/settings`

The dashboard should call `/chat` for the main composer. Legacy thread routes
can still power details, refresh, and compatibility tests.

## Routing Rules

The chat router should be deterministic first, LLM fallback second.

Rules:

- If the message contains a GitHub URL or `owner/repo`, treat it as a repo
  attach/switch request.
- If no active repo exists and the message asks about code, ask for a repo
  instead of fabricating.
- If the message has an explicit symbol or file path, use that as the current
  active focus for routing and evidence collection.
- If the message is a follow-up without a new symbol or file, inherit
  `active_focus` when it is unambiguous, so "what about tests?" or "show the
  evidence" can still target the previous symbol.
- If an active repo exists and the message asks for files, functions, tests,
  behavior, architecture, entry points, or evidence, start the grounded graph.
- If the message asks to summarize prior discussion, answer from bounded memory
  and label it as memory-derived.
- If the message asks for a structured answer, use report mode.
- If the message is planning, clarification, or high-level workflow talk,
  answer conversationally without starting an expensive repo run.
- If the message asks Wayfinder to edit code, run arbitrary commands, or access
  private resources, explain the current limitation and suggest the grounded
  inspection path.

The router should produce a small structured decision:

```json
{
  "intent": "repo_question",
  "answer_mode": "report",
  "requires_grounded_run": true,
  "requires_context_switch": false,
  "clarification_question": null
}
```

## Answer Policy

Wayfinder can sound more human, but claims still need a policy.

Conversation-only answer:

- may use user preferences and thread memory;
- may explain workflow or next steps;
- must not invent new repo facts.

Grounded answer:

- starts or links a run;
- cites repo/AST/test evidence;
- shows verified, unverified, and contradicted counts;
- keeps limitations visible.

Structured report:

- reuses the current output format: architecture, key paths, evidence,
  verification labels, limitations, and next steps;
- can be expanded from a conversational answer.

Evidence mode:

- prioritizes file paths, symbols, run id, tool observations, and trace
  metadata;
- is useful for interviews and debugging.

## Dashboard Information Architecture

The UI should feel like a workspace, not a dashboard with a chat widget.

Layout:

- left rail: repo switcher, thread list, recent repos, small "new repo" action;
- center: chat transcript and composer;
- right rail: active context, evidence, run timeline, selected files/symbols,
  settings shortcut;
- top bar: workspace name, active repo, repo status, auth/settings state;
- metrics/history: secondary navigation, not the first daily-use surface.

Legacy surface migration:

- Threads becomes the primary workspace, not one tab among `Run`, `Answer`,
  `History`, and `Metrics`.
- Old `Run` form becomes chat routing plus run progress attached to assistant
  messages and the right rail. A run inspector may remain for debugging, but it
  is opened from a linked run, not from a primary tab.
- Old `Answer` tab becomes the assistant message body. The structured grounded
  report can expand inline or in the right rail from the message attachment.
- History should be redesigned from a raw run table into a repo/thread-scoped
  activity timeline. Its primary rows are repo attach/switch events, user
  messages, assistant messages, linked grounded runs, evidence views, inherited
  focus events, clarification states, failures, and attention items. Runs remain
  expandable child events, not the main history object.
- Global History, if kept, should summarize recent repo conversations and active
  threads, not recent standalone runs.
- The four metric cards must be replaced, not merely restyled:
  - `Threads`: active repo threads, message volume, latest activity;
  - `Grounding`: evidenced answers, verified/unverified/contradicted counts,
    report coverage;
  - `Context`: active repo, packet freshness, inherited focus health, repo
    switch state;
  - `Attention`: clarifications, failed runs, stale packets, contradictions,
    auth/sandbox issues.
- Old `Latency` and `Cost` move into a run inspector or diagnostics drawer. They
  are useful for engineering debug, but they are not the primary user-facing
  product metrics for repo-aware conversation.

Main composer:

- single input at the bottom;
- supports pasted repo URLs naturally;
- supports optional lightweight controls for answer mode;
- shows "active repo: owner/repo" near the input;
- when no repo is active, placeholder should invite natural repo attachment,
  not present a form.
- draft state for a pasted repo URL, unsent message, selected answer mode, and
  attachments must be owned by the persistent workspace shell, not by a
  tab-local child component that resets when the user switches views.
- the transcript area must have a bounded scroll region and the composer must
  stay in a stable bottom interaction area. Long assistant outputs should not
  push the composer out of the usable workspace.
- disabled send states must explain the reason, for example "run in progress",
  "select a repo", or "message is empty".

Assistant message rendering:

- natural answer body first;
- compact attachments under the message:
  - linked run;
  - verified/unverified/contradicted chips;
  - evidence refs;
  - "open report" / "show evidence" actions;
- right rail can show the expanded report/evidence for the selected message.

## State And Persistence

Minimum persistent state:

- active repo context per user;
- default thread for the active repo;
- thread messages;
- linked runs;
- summary memory;
- latest repo packet and limitations.

Context safety rules:

- every thread and repo context must be user-scoped;
- switching repos must clear selected files/symbols unless they belong to the
  new repo;
- switching repos must clear `active_focus`;
- a follow-up may inherit `active_focus` only inside the same repo context;
- route decisions must include `repo_url` / `context_id` to avoid accidental
  cross-repo execution;
- memory packet builders must never mix messages from different repo contexts.

## Failure Cases

- No active repo and code question: ask for repo context.
- Repo URL pasted but not allowed by deploy allowlist: return a clear
  permission error.
- Repo switch while a run is active: keep old run linked to old thread; new
  context should not inherit active run state.
- Ambiguous "this file" with no selected file: ask which file.
- Ambiguous follow-up with multiple possible focused symbols: ask which symbol
  or file to inspect.
- Chat-only route tries to answer a new code fact: downgrade to unverified or
  trigger a grounded run.
- Memory packet too large: trim old messages, preserve summary and latest
  evidence refs.
- Existing thread missing: recover to latest active repo context or ask user to
  select a repo.
- Unsaved repo/message draft is lost on tab switch: keep composer draft in the
  workspace shell or a small persisted client store.
- Long assistant output pushes the composer to the bottom of the document:
  constrain transcript height and keep the composer persistent inside the chat
  viewport.
- Send button disabled without explanation: show the blocking reason near the
  composer.
- LLM unavailable: deterministic routing and final writer remain the fallback.

## Minimal Skeleton Boundary

Commit 22 should start with the smallest skeleton that proves the ambient chat
boundary without rewriting the existing graph.

### Backend Skeleton

New or extended API schemas should live in `src/wayfinder/api/schemas.py`:

- `ActiveRepoContext`: user-scoped active repo state derived from or persisted
  alongside the default repo thread.
- `ChatRequest`: natural message content, optional `thread_id`, optional
  `repo_url`, and `answer_mode`.
- `ChatRouteDecision`: deterministic decision record with intent, answer mode,
  whether a grounded run is required, whether context switches, clarification,
  active focus, and reason.
- `AgentTraceAttachment`: UI-facing trace summary that names Project 6 agents,
  route, tool/evidence refs, verifier labels, limitations, and final handoff.
- `ChatResponse`: selected thread, appended messages, active context, optional
  active run, route decision, and trace attachment.

Store changes should stay close to the existing run/thread persistence layer in
`src/wayfinder/api/run_store.py`:

- v1 may derive active context from the latest selected thread and update it
  with explicit `set_active_context` / `active_context_for_user` helpers.
- If SQLite needs a table, it should be one small user-scoped
  `active_repo_contexts` table keyed by `user_id`, not a broad workspace
  redesign.
- Switching repos must clear `active_focus`, selected files, and selected
  symbols.
- Memory builders must keep using thread-scoped messages and must not mix repo
  contexts.

Routing should be a small deterministic helper before any LLM fallback:

- preferred file: `src/wayfinder/api/chat_routing.py`;
- input: `ChatRequest`, current `ActiveRepoContext`, optional selected thread;
- output: `ChatRouteDecision`;
- no graph invocation inside the router;
- no direct MCP calls inside the router;
- no Project 5 MCP server should be represented as an agent.

The `/chat` facade should live in `src/wayfinder/api/main.py` and reuse existing
thread/run paths:

1. authenticate the workspace user;
2. resolve or update active repo context;
3. create/select the default thread when needed;
4. append the user message;
5. call the router;
6. for `chat_only` / `clarification`, append a lightweight assistant message
   without starting a run;
7. for grounded repo questions, call the same graph execution path currently
   used by `/threads/{thread_id}/messages`;
8. return the thread, active context, route metadata, active run, and agent trace
   attachment.

### Frontend Skeleton

Dashboard skeleton should avoid a second large form.

Preferred component boundary:

- keep `dashboard/components/repo-conversation-workspace.tsx` as a compatibility
  detail view only if needed;
- add or reshape a workspace shell component that owns the persistent composer
  draft, selected answer mode, active repo context, selected thread, and selected
  right-rail attachment;
- add a `dashboard/lib/chat.ts` client helper for `/api/wayfinder/chat`;
- add Next proxy route `dashboard/app/api/wayfinder/chat/route.ts`;
- keep run diagnostics, metrics, and settings reachable but secondary.

First UI skeleton should render:

- left rail with repo/thread list;
- central bounded transcript with stable bottom composer;
- right rail with active context, latest run, evidence/agent trace, and
  limitations;
- send-disabled reason text near the composer.

### Test Skeleton

Backend tests should land before implementation:

- no active repo + code question returns a clarification response and starts no
  run;
- pasted repo URL creates/switches active context and a default thread;
- follow-up without `repo_url` reuses active context;
- repo switch clears active focus and does not leak memory;
- structured report request selects report mode;
- explicit symbol creates or updates active focus;
- chat-only message does not create verified code claims.

Frontend gates should prove only the skeleton behavior first:

- chat-first workspace is the first viewport;
- composer draft survives switching secondary surfaces;
- long assistant content scrolls in the transcript without moving the composer;
- disabled send state names the blocker;
- agent trace attachment is visible for grounded messages.

### Out Of Commit 22

These belong to Commit 23, not this skeleton:

- distinct LLM prompts for each named Project 6 agent;
- supervisor plans that run multiple worker agents in one graph pass;
- verifier challenge loop over worker claim packets;
- final answer provenance tests across multiple worker agents;
- any Project 5 MCP code changes.

## Tests

Backend tests:

- user can set active repo context once and send chat without repeating
  `repo_url`;
- pasted GitHub URL in chat creates or switches active context;
- chat with no active repo and code question returns clarification;
- repo-grounded question starts a run linked to the default thread;
- conversation-only question does not start a run;
- structured report request selects report mode;
- explicit symbol in a new thread, such as `wayfinder.graph.app.build_graph`,
  still routes to entry evidence and produces AST-backed claim counts;
- follow-up after that symbol question can inherit active focus when no new
  symbol is provided;
- repo switch does not leak repo A memory/evidence into repo B;
- auth isolation prevents reading or using another user's active context.

Frontend checks:

- first viewport is chat-first, with composer focused;
- no large repo URL + question form is shown as the primary daily path;
- active repo context is visible near the composer;
- sending a message without a repo shows a clarification state;
- attaching a repo through chat updates the left rail and context bar;
- follow-up messages preserve context after refresh;
- typed repo URL or unsent chat draft survives switching away from the chat
  surface and back;
- long assistant output scrolls inside the transcript and leaves the composer
  usable without page-level hunting;
- disabled send state names the blocker, including active run-in-progress state;
- evidence/report details open from assistant-message attachments or right rail;
- old Run and Answer surfaces are reachable from linked message/run details,
  not as primary peer tabs;
- History shows a repo/thread activity timeline, not only a global run table;
- metrics are renamed and reshaped to `Threads`, `Grounding`, `Context`, and
  `Attention`; old `Success`, `Runs`, `Latency`, and `Cost` do not remain as the
  top-level metric set;
- metrics/history/settings remain reachable but secondary.

## Implementation Slice

Recommended sequence:

1. Add the design note and update tracker/LEARNINGS.
2. Define the minimal active context schema and tests.
3. Add a `/chat` facade that initially reuses current thread/run store methods.
4. Add router tests before UI work.
5. Replace the primary dashboard body with the Codex-like chat shell while
   keeping current thread details available.
6. Migrate the old `Run`, `Answer`, `History`, and four-card metrics surfaces
   into message attachments, right rail details, activity history, and compact
   diagnostics.
7. Run local API/dashboard gates and one public smoke with:
   - attach repo through chat;
   - ask two follow-ups without repo URL;
   - request structured report;
   - switch repo and verify memory isolation.

## Observed Commit 21 Baseline

User smoke on 2026-06-09 clarified the current behavior:

- A new thread with repo `https://github.com/LovRanRan/wayfinder` and the exact
  question `Explain the behavior and data flow through
  wayfinder.graph.app.build_graph` correctly routed to `entry_explainer` /
  `ast_explorer` and produced `verified=3`, `unverified=1`, `contradicted=0`.
- Therefore, Commit 21 thread execution does not inherently drop verification
  counts. The initial thread path can preserve the exact symbol query.
- The real Commit 22 gap is follow-up and context continuity: when a later
  message does not repeat the symbol or asks a broad architecture question, the
  current router only sees the latest message and may fall back to
  `architect_mapper`, losing the user's intended focus.
- Current Commit 21 Threads UI keeps `repoUrl`, `initialQuery`, and `followup`
  as component-local state. User smoke showed that typing a repo link in the
  Threads tab and switching tabs resets the draft. Commit 22 should move draft
  ownership to the persistent workspace shell/composer.
- A long assistant output can push the current follow-up composer to the bottom
  of the page because the thread surface is a card with a minimum height, not a
  stable chat viewport. The Send button can also be disabled when the thread is
  still `running` without explaining that reason to the user.

Commit 22 should preserve the working explicit-symbol behavior while adding
active focus inheritance for natural follow-ups and persistent composer drafts.

## Interview Explanation

Commit 21 gave Wayfinder conversation memory. Commit 22 makes that memory
ambient. The product no longer asks the user to submit a repo and prompt every
time. Instead, it maintains an active repo context like Codex maintains a
current worktree.

The important design boundary is that active context is not evidence. It tells
the agent what repo the user is talking about. New claims about code still go
through the same repo mapper, AST explorer, verifier, and evidence labels. That
is how Wayfinder can feel like ChatGPT while still behaving like a grounded
codebase copilot.
