# wayfinder DESIGN v1.1

## 1. Product Contract

`wayfinder` is a verifier-backed codebase onboarding workflow. Given a repository and a question, it maps architecture, explains entry paths, labels high-risk claims with grounded evidence, and exposes the run through an inspectable API/dashboard surface.

The product promise is not "answer every code question confidently." The promise is:

- ground architecture facts in repository scans;
- ground symbol facts in AST evidence;
- verify static code facts with repository/AST evidence and keep runtime claims unverified unless a trusted/sandboxed runner can execute focused tests;
- label uncertainty explicitly;
- make each run resumable and observable.

Primary demo target: a pinned commit of `langchain-ai/langchain`.

## 2. Agent Architecture

| Agent | Tooling | Responsibility |
|---|---|---|
| `supervisor` | LangGraph routing policy | Classify intent, choose the next agent, and accept user route corrections. |
| `architect_mapper` | `mcp-repo-mapper` | Map repo structure, language breakdown, frameworks, dependency graph, and entry points. |
| `entry_explainer` | `mcp-ast-explorer` | Explain definitions, signatures, references, call chains, class relationships, and AST-backed symbol evidence. |
| `verifier` | AST evidence + sandbox-gated `mcp-test-runner` | Produce `verified` / `unverified` / `contradicted` labels;public executable tests run only through the separate sandbox worker. |
| `final_writer` | OpenAI Responses API + local resilience layer | Synthesize a grounded answer from bounded MCP/verifier evidence and repair unsafe prose based on verifier labels and errors. |

Project 5 MCP servers are the deterministic fact layer:

- `mcp-repo-mapper`: structure and architecture primitives.
- `mcp-ast-explorer`: Python AST symbol truth.
- `mcp-test-runner`: bounded pytest/Jest execution and parser output for trusted local mode or the Commit 20 sandbox worker.

Community MCPs are supporting context only. They do not replace Project 5 as the primary evidence path.

Commit 16 makes this boundary explicit in runtime: Tavily/GitHub MCP results can
enter final synthesis as external context, but they cannot create verified code
claims or override repository/AST/test evidence.

## 3. State Schema

`WayfinderState` contains:

- `query`
- `repo_url`
- `repo_handle`
- `thread_id`
- `intent`
- `route_decision`
- `next_agent`
- `repo_metadata`
- `module_dep_graph`
- `entry_points`
- `ast_index`
- `pending_claims`
- `verified_claims`
- `unverified_claims`
- `contradicted_claims`
- `test_results`
- `community_context`
- `partial_summaries`
- `user_corrections`
- `errors`
- `final_output`
- `messages`

`Claim` contains:

- `text`
- `source_agent`
- `risk_level`
- `test_strategy`
- `test_id`
- `status`

## 4. Routing Model

Routing starts deterministic:

- architecture / structure / module / overview -> `architect_mapper`
- runtime / run / start / entrypoint -> `entry_explainer`
- behavior / logic / flow / function -> `entry_explainer`
- bug / error / traceback / failing -> `entry_explainer`
- unclear mixed query -> safe default architecture path

User corrections are state-level inputs:

```text
user_corrections=["intent=behavioral"]
```

The supervisor reads the latest correction and resumes with the corrected intent.

## 5. Verification Strategy

Verifier acts only on high-risk claims.

High-risk examples:

- concrete runtime behavior;
- data transformation;
- state mutation;
- numeric counts;
- error-path behavior;
- test/command claims;
- file/path behavior that can be executed.

Labels:

- `verified`: relevant test/tool evidence supports the claim.
- `unverified`: no safe test, no coverage, timeout, malformed output, unsupported framework/language, user skip, or unrelated suite failure.
- `contradicted`: selected relevant test directly conflicts with the claim.

Verifier uses HITL only when there is an executable test plan. If no safe test exists, it marks claims unverified without interrupting.

## 6. HITL Checkpoints

Current implemented checkpoint:

- pre-test verifier approval via LangGraph `interrupt()` and `Command(resume=...)`.

Public deploy policy:

- `WAYFINDER_VERIFIER_RUNNER=sandboxed_mcp` auto-approves verifier execution by
  default because tests run in the separate sandbox worker. This avoids public
  API jobs waiting forever for a dashboard approval path that does not exist yet.
- `WAYFINDER_VERIFIER_APPROVAL_MODE=interrupt` restores the original HITL
  interrupt behavior for local/manual flows.
- `WAYFINDER_VERIFIER_APPROVAL_MODE=auto_skip` keeps executable claims
  unverified without running sandbox tests.

Supported decisions:

- approve;
- skip;
- modify filter.

The graph requires a checkpointer and stable `thread_id` for HITL resume.

Commit 7/8 API exposes a user correction path through `/refine/{job_id}`, which reuses the same `thread_id`.

## 7. Resilience Modes

| Failure Mode | Current Mitigation |
|---|---|
| Repo too large | Sampling/user-confirmation requirement is surfaced as a final limitation. |
| Unsupported language | Degraded output keeps the unsupported-language limitation and verifier leaves related claims unverified. |
| AST parse error | Entry explanation skips symbol certainty, preserves parse/tool error in state, and final output names the limitation. |
| No tests or all tests fail | No coverage and unrelated suite failures become `unverified`, not `verified` or `contradicted`. |
| Supervisor misclassification | `user_corrections` can override intent; `/refine` persists correction and re-enters the graph. |
| Hallucinated function/class | AST validation returns missing-symbol evidence; final output cannot invent nearby symbols. |
| Reflection loop infinite | Reflection cap is two rewrites; cap reached is surfaced instead of looping. |
| Test timeout or sandbox kill | Verifier retries once with larger timeout; repeated timeout becomes `validation_timed_out`. |

## 8. Runtime Surface

FastAPI endpoints:

- `GET /health`
- `GET /runs?limit=10`
- `POST /explain`
- `GET /status/{job_id}`
- `POST /refine/{job_id}`

`POST /explain` creates a queued job and schedules graph execution with FastAPI `BackgroundTasks`.

The API stores:

- public `RunSummary`;
- internal graph input by `job_id`;
- process-local checkpointer;
- trace metadata.

`job_id` is the graph `thread_id`.

Production caveat: current runtime is process-local. Multi-worker deployment needs a durable run store and checkpointer.

## 9. Observability

Required metadata:

- `agent_name`
- `tool_name`
- `mcp_server`
- `tokens`
- `latency`
- `cost_usd`
- `claim_id`

Additional runtime metadata:

- `job_id`
- `thread_id`
- `phase`
- `status`
- `langsmith_tracing`
- `langsmith_project`

Graph runs receive metadata/tags through `RunnableConfig`. MCP tool calls are optionally wrapped at the adapter boundary when `LANGSMITH_TRACING=true`.

The dashboard consumes the same metadata for latency, cost, token, route, and failure-mode panels.

## 10. Dashboard

Next.js dashboard behavior:

- server-side fetch from `GET /runs?limit=10`;
- fallback to seeded demo data when API is unavailable;
- recent runs table with trace links;
- current run summary;
- per-agent P50/P95 latency;
- route decision flow;
- verification stats;
- token/cost overview;
- failure mode frequency.

## 11. Build And Deploy Surface

Local backend:

```bash
uv run uvicorn wayfinder.api.main:app --reload
```

Local dashboard:

```bash
cd dashboard
WAYFINDER_API_BASE_URL=http://localhost:8000 npm run dev
```

Docker Compose:

```bash
docker compose up --build api dashboard
```

Optional Project 5 MCP process topology:

```bash
docker compose --profile mcp up --build
```

Railway config: `railway.json`.

Cloud Build config: `cloudbuild.yaml`.

GitHub Actions:

- backend ruff/mypy/pytest;
- env-gated Project 5 integration after checking out the three MCP repos;
- dashboard lint/typecheck/build.

## 12. Ship Evidence

Artifacts:

- README terminal pass;
- dashboard surface;
- Docker/Compose files;
- GitHub Actions CI;
- deploy notes;
- demo recording script;
- bilingual launch draft;
- design notes 001-010.

External evidence status:

- public Railway API and dashboard URLs are live and public-smoked;
- actual recorded 3-minute demo video or GIF remains a user-owned handoff;
- published blog URL if posted externally.

## 13. Grounded LLM Synthesis

Wayfinder's answer layer is a grounded LLM copilot, not a deterministic fact
panel. The final writer can use OpenAI Responses API when explicitly enabled:

```env
WAYFINDER_FINAL_WRITER=openai
WAYFINDER_LLM_ROUTING=openai
```

For local development without auth, `OPENAI_API_KEY` may still come from the
process env or `.env`. In authenticated workspace mode, the model key is owned
by the workspace settings API instead of a shared deployment variable. The API
stores only an encrypted key envelope and a masked label, then injects the
decrypted key into the runtime env for that user's run.

The default remains deterministic for tests and low-cost smoke runs. When LLM
mode is enabled, the model receives a bounded synthesis packet:

- query and repo reference;
- route decision;
- Project 5 architecture and AST evidence;
- verifier labels;
- graph errors and limitations;
- optional community context.

The LLM is not allowed to invent files, symbols, tests, or behavior. It may only
compose the evidence into a readable onboarding answer and must preserve
`verified`, `unverified`, and `contradicted` labels.

## 14. User Workspaces and Persistent History

Wayfinder now supports a workspace-auth mode for public repo analysis. When
`WAYFINDER_REQUIRE_AUTH=1`, `/explain`, `/runs`, `/status/{job_id}`, and
`/refine/{job_id}` require a session token and only return runs owned by that
user. The dashboard stores the session in an HTTP-only cookie and forwards it to
the API as a bearer token through its proxy routes.

Persistent history is enabled with:

```env
WAYFINDER_RUN_STORE=sqlite
WAYFINDER_RUN_STORE_PATH=/data/wayfinder/runs.sqlite
WAYFINDER_KEY_ENCRYPTION_SECRET=<long-random-secret>
```

This commit deliberately keeps online test execution separate from auth. Public
GitHub repo analysis can use `WAYFINDER_GITHUB_REPO_ALLOWLIST=*`, but
`mcp-test-runner` remains sandbox-gated because it executes untrusted repo code.
Commit 20 adds a separate FastAPI sandbox worker with a narrow `POST /run-test`
contract, live `GET /health` gate, command allowlist, timeout, output cap, and
ephemeral repo copy/cleanup.

Public Railway runs also keep external reader tools on short budgets. HTTP MCP
sidecars default to an 8 second tool timeout and one attempt, configurable with
`WAYFINDER_MCP_TOOL_TIMEOUT_SECONDS` and `WAYFINDER_MCP_MAX_ATTEMPTS`. OpenAI
Responses calls use `WAYFINDER_OPENAI_TIMEOUT_SECONDS` and fall back to the
deterministic writer/router path when unavailable. The API-level job timeout is
only a final guard, not the primary failure-handling mechanism.

The graph builder also wraps non-interrupt nodes in a watchdog controlled by
`WAYFINDER_GRAPH_NODE_TIMEOUT_SECONDS` (default `30`): `supervisor`,
`architect_mapper`, `entry_explainer`, and `final_writer`. A timed-out node
returns structured `graph_node_timeout` evidence and a degraded summary so the
graph can still reach `final_writer`. `verifier` is deliberately not wrapped
because LangGraph `interrupt()` requires runnable context; verifier execution is
bounded by sandbox/test timeouts instead. The job-level timeout remains a
last-resort guard for leaked threads or process-level failures.

## 15. Workspace Runtime And Sandbox Policy

`GET /workspace/settings` returns the active workspace runtime settings without
secrets:configured key status, masked key label, model, LLM routing mode, final
writer mode, verifier runner mode, and sandbox status. `PUT /workspace/settings`
updates model/routing/writer fields and can store or clear the workspace OpenAI
key.

Runtime env construction is now:

```text
base env
  -> remove shared OPENAI_API_KEY when auth is required
  -> load encrypted workspace key for the run owner
  -> apply workspace model/routing/final-writer overrides
  -> build graph dependencies
```

The verifier boundary is intentionally separate:

```env
WAYFINDER_VERIFIER_RUNNER=placeholder
WAYFINDER_TEST_SANDBOX_URL=
WAYFINDER_TEST_SANDBOX_TOKEN=
```

`placeholder` keeps public executable test verification disabled while
repository/AST evidence can still verify code facts. `sandboxed_mcp` performs a
live sandbox worker health check before returning a remote verifier adapter. If
the worker is missing or unhealthy, executable claims remain unverified.
