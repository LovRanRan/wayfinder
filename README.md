# wayfinder

Verifier-backed codebase onboarding copilot for engineers entering an unfamiliar repository.

`wayfinder` maps architecture, explains entry paths from AST evidence, labels high-risk code understanding claims with grounded evidence, and shows uncertainty instead of hiding it.

## Status

- Local API/runtime: ready
- Dashboard: ready with live API fetch and seeded demo fallback
- Project 5 MCP integration: stdio passing locally; reader HTTP deploy path added
- Docker/Compose: deploy-ready and Railway-smoked
- Public live URL: deployed on Railway
- Public smoke evidence: recorded in docs
- Demo video: script ready; recording is a user-owned handoff

## Why This Exists

Most codebase explanation tools sound confident before they are grounded. They can summarize README text, name plausible modules, or explain functions that may not exist.

`wayfinder` treats onboarding as an evidence workflow:

1. Gather deterministic architecture and AST evidence through MCP tools.
2. Route the user's question through a LangGraph Supervisor.
3. Verify static code facts with repository/AST evidence, and keep runtime claims unverified unless a trusted/sandboxed test runner is available.
4. Label claims as `verified`, `unverified`, or `contradicted`.
5. Rewrite final output when verifier evidence contradicts earlier prose.

## Architecture

```text
User / Dashboard
      |
      v
FastAPI runtime
  POST /threads
  GET  /threads
  POST /threads/{thread_id}/messages
  POST /explain
  GET  /runs
  GET  /status/{job_id}
  POST /refine/{job_id}
      |
      v
LangGraph Supervisor
      |
      +--> architect_mapper  -> mcp-repo-mapper
      |
      +--> entry_explainer   -> mcp-ast-explorer
      |
      +--> verifier          -> AST labels + sandbox-gated mcp-test-runner
      |
      v
final_writer + resilience/reflection layer
      |
      v
RunSummary + trace metadata + dashboard panels
ConversationThread + bounded memory + message history
```

## Tech Stack

- Python 3.11+
- FastAPI
- LangGraph
- LangChain MCP adapters
- Project 5 self-authored MCP servers:
  - `mcp-repo-mapper`
  - `mcp-ast-explorer`
  - `mcp-test-runner`
- LangSmith-compatible trace metadata
- Next.js 15 dashboard
- Tailwind CSS + shadcn-style local components
- Docker Compose
- GitHub Actions

## Quickstart

Install backend dependencies:

```bash
uv sync --extra dev
```

Run backend:

```bash
uv run uvicorn wayfinder.api.main:app --reload
```

Optional trusted GitHub URL ingestion for demos:

```bash
export WAYFINDER_ENABLE_GITHUB_INGESTION=1
export WAYFINDER_GITHUB_REPO_ALLOWLIST=langchain-ai/langchain,LovRanRan/wayfinder
export WAYFINDER_GITHUB_MAX_FILES=10000
```

Private workspace mode:

```bash
export WAYFINDER_REQUIRE_AUTH=1
export WAYFINDER_RUN_STORE=sqlite
export WAYFINDER_RUN_STORE_PATH=.wayfinder/runs.sqlite
```

Run dashboard:

```bash
cd dashboard
npm ci
WAYFINDER_API_BASE_URL=http://localhost:8000 npm run dev
```

Open:

- API docs: `http://localhost:8000/docs`
- Dashboard: `http://localhost:3000`

## Docker Compose

```bash
docker compose up --build api dashboard
```

Optional MCP process topology:

```bash
docker compose --profile mcp up --build
```

Project 5 MCP servers are stdio-first packages in v1, so Compose keeps them in
an explicit profile. Real MCP integration is validated through the env-gated
test path.

## API

### `POST /chat`

Primary product facade for the ambient repo workspace. It accepts natural chat,
optional `thread_id`, optional `repo_url`, and an `answer_mode` of `auto`,
`conversation`, `report`, or `evidence`.

The server resolves the active repo context, creates or selects the default repo
thread, records the user message, routes the turn, and starts a grounded run
only when the message asks for new repo facts.

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"content":"Open https://github.com/pallets/click and help me understand this repo"}'
```

### `GET /workspace/context`

Returns the current user's active repo context: repo, default thread, active
focus, latest run, summary memory, selected files/symbols, and limitations.

### `POST /workspace/context`

Sets or switches active repo context from a `thread_id` or `repo_url`.

### `POST /threads`

Creates a repo-scoped conversation thread. If `initial_query` is provided, the
API stores the first user message and starts a normal grounded Wayfinder run.

```bash
curl -X POST http://localhost:8000/threads \
  -H "Content-Type: application/json" \
  -d '{"repo_url":".","initial_query":"Map the architecture and entry points"}'
```

### `GET /threads`

Returns the current user's repo threads, messages, and linked runs.

```bash
curl "http://localhost:8000/threads?limit=20"
```

### `POST /threads/{thread_id}/messages`

Adds a follow-up question to an existing repo thread. The follow-up reuses the
thread repo URL and a bounded memory packet, then starts the same grounded graph
path as a normal run.

```bash
curl -X POST http://localhost:8000/threads/<thread_id>/messages \
  -H "Content-Type: application/json" \
  -d '{"content":"Where should I change the CLI entry behavior?"}'
```

### `POST /explain`

Starts a queued one-shot run. This remains available for backward compatibility
and run-level debugging; the dashboard primary path is repo conversation
threads.

```bash
curl -X POST http://localhost:8000/explain \
  -H "Content-Type: application/json" \
  -d '{"repo_url":".","query":"Map the architecture and entry points"}'
```

GitHub URLs are supported when `WAYFINDER_ENABLE_GITHUB_INGESTION=1`. The API
shallow-clones the repo into the Wayfinder cache and rejects repos over
`WAYFINDER_GITHUB_MAX_FILES` files. Set
`WAYFINDER_GITHUB_REPO_ALLOWLIST=*` for authenticated public-repo workspace mode;
keep a narrow list for anonymous public demos.

### `GET /status/{job_id}`

Polls a run.

```bash
curl http://localhost:8000/status/<job_id>
```

### `POST /refine/{job_id}`

Applies user correction and resumes on the same graph thread.

```bash
curl -X POST http://localhost:8000/refine/<job_id> \
  -H "Content-Type: application/json" \
  -d '{"correction":"intent=behavioral"}'
```

### `GET /runs`

Returns recent run summaries for the dashboard.

```bash
curl "http://localhost:8000/runs?limit=10"
```

## Dashboard

The dashboard reads `GET /threads?limit=20` and `GET /runs?limit=10` from
`WAYFINDER_API_BASE_URL`.
The browser-facing launcher uses dashboard proxy routes:

- `POST /api/wayfinder/chat`
- `POST /api/wayfinder/threads`
- `GET /api/wayfinder/threads/{thread_id}`
- `POST /api/wayfinder/threads/{thread_id}/messages`
- `POST /api/wayfinder/explain`
- `GET /api/wayfinder/status/{job_id}`
- `POST /api/wayfinder/refine/{job_id}`

For split-service deploys, set `WAYFINDER_API_BASE_URL` to the API address the
dashboard server can reach, and set `NEXT_PUBLIC_WAYFINDER_API_BASE_URL` to the
public API URL shown in browser links.

Panels:

- Codex-like repo workspace with left repo/thread rail, central bounded chat,
  stable bottom composer, and right context/evidence/agent-trace rail;
- active repo context indicator and natural chat route through `/chat`;
- assistant-message attachments for linked runs, evidence chips, and verifier labels;
- repo/thread activity timeline for History, with raw run diagnostics folded into an expandable section;
- thread-native metrics: `Threads`, `Grounding`, `Context`, and `Attention`;
- legacy run launcher and answer inspector remain reachable for diagnostics;
- per-agent P50/P95 latency;
- token usage and cost overview;
- routing decision flow;
- verification stats;
- failure mode frequency;

If the API is unavailable or has no runs, the dashboard shows seeded demo data with the same schema. This keeps CI and Docker builds inspectable without requiring a live backend.

## Verification Evidence

Local gates:

```bash
uv run ruff check .
uv run mypy src tests
uv run pytest -q
WAYFINDER_RUN_PROJECT5_MCP_INTEGRATION=1 uv run pytest tests/test_project5_mcp_integration.py -q -rs
cd dashboard && npm run lint && npm run typecheck && npm run build
```

Current local and deploy evidence:

- backend gates cover API lifecycle, auth, recent runs, refine/resume, error serialization, trace metadata, workspace settings, sandbox policy, and the sandbox worker request boundary;
- thread gates cover repo-thread creation, follow-up messages, auth isolation, SQLite persistence, linked runs, and bounded memory packets;
- Project 5 MCP integration covers repo mapper, AST explorer, and test runner through real local MCP packages when the env-gated integration test is enabled;
- dashboard gates cover lint, typecheck, and production build;
- public Railway smoke evidence is tracked in [`docs/evidence/commit19_public_smoke.md`](docs/evidence/commit19_public_smoke.md) and [`docs/evidence/commit21_repo_threads_public_smoke.md`](docs/evidence/commit21_repo_threads_public_smoke.md).

## Failure Modes

| Failure Mode | Mitigation |
|---|---|
| Repo over 10k files | Sampling/user-confirmation limitation surfaces in final output. |
| Unsupported language | Degraded limitation and verifier-skipped/unverified behavior. |
| AST parse error | Symbol certainty is skipped and parse limitation is shown. |
| No tests or unrelated failing suite | Claims become `unverified`, not accepted or contradicted. |
| Supervisor misclassification | `/refine` persists `user_corrections` and resumes same thread. |
| Hallucinated symbol | AST validation gate rejects missing functions/classes. |
| Reflection loop infinite | Rewrite cap is 2, then final output states the cap. |
| Test timeout or sandbox kill | Retry once with larger timeout, then mark validation timed out. |

## Observability

Every run carries trace metadata:

```text
agent_name
tool_name
mcp_server
tokens
latency
cost_usd
claim_id
job_id
thread_id
phase
status
```

LangSmith can consume this metadata when `LANGSMITH_TRACING=true`. The dashboard and Project 7 eval harness can use the same schema even when LangSmith credentials are not configured.

## Deploy

Railway:

```bash
railway link
railway up --service wayfinder-api
railway up --service wayfinder-dashboard --path-as-root dashboard
```

The Railway services are connected to `LovRanRan/wayfinder` on `main` for
GitHub-backed deploys. The first deploy was a CLI snapshot deploy from commit
`c1c09c4`; the GitHub-connected redeploys succeeded from the Railway UI on
2026-06-04.

Reader MCP services can be started as localhost HTTP sidecars inside the API
container:

```text
mcp-repo-mapper     -> http://127.0.0.1:8101/mcp
mcp-ast-explorer    -> http://127.0.0.1:8102/mcp
```

Set the API service to:

```env
WAYFINDER_REQUIRE_AUTH=1
WAYFINDER_RUN_STORE=sqlite
WAYFINDER_RUN_STORE_PATH=/data/wayfinder/runs.sqlite
WAYFINDER_KEY_ENCRYPTION_SECRET=<long-random-secret>
WAYFINDER_START_PROJECT5_HTTP_MCP=1
WAYFINDER_ARCHITECTURE_SCANNER=mcp_http
WAYFINDER_ENTRY_SCANNER=mcp_http
WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL=http://127.0.0.1:8101/mcp
WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL=http://127.0.0.1:8102/mcp
WAYFINDER_MCP_TOOL_TIMEOUT_SECONDS=8
WAYFINDER_MCP_MAX_ATTEMPTS=1
WAYFINDER_RUNTIME_BUILD_TIMEOUT_SECONDS=15
WAYFINDER_GRAPH_NODE_TIMEOUT_SECONDS=30
WAYFINDER_VERIFIER_RUNNER=placeholder
WAYFINDER_ENABLE_GITHUB_INGESTION=1
WAYFINDER_GITHUB_REPO_ALLOWLIST=*
WAYFINDER_GITHUB_MAX_FILES=10000
WAYFINDER_GITHUB_CACHE_ROOT=/tmp/wayfinder/repos
```

For Railway, mount a persistent volume at `/data` before relying on
`/data/wayfinder/runs.sqlite`;otherwise the SQLite database is container-local
and can be lost on rebuild.

Optional grounded LLM synthesis:

```env
WAYFINDER_LLM_ROUTING=openai
WAYFINDER_FINAL_WRITER=openai
WAYFINDER_OPENAI_MODEL=gpt-5.5
WAYFINDER_OPENAI_TIMEOUT_SECONDS=20
```

In authenticated workspace mode, users add their own OpenAI key in the dashboard
Settings tab. The API stores only an encrypted key envelope plus a masked label;
the raw key is not returned in `/workspace/settings`, run history, or trace
metadata. `WAYFINDER_KEY_ENCRYPTION_SECRET` is required before the API accepts a
workspace key.

Optional community context:

```env
WAYFINDER_COMMUNITY_CONTEXT=mcp
TAVILY_API_KEY=...
GITHUB_PERSONAL_ACCESS_TOKEN=...
```

Project 5 MCP output remains the code fact layer. Tavily/GitHub search results
are external supporting context only;they do not create verified code claims and
cannot override repository/AST/test evidence.

`mcp-test-runner` is sandbox-gated in public HTTP mode. The reader MCPs run in
the API container because they are read-only and need access to the same cloned
repository path as the API. Executable test claims must go through the separate
sandbox worker.

Sandbox gate:

```env
WAYFINDER_VERIFIER_RUNNER=placeholder
WAYFINDER_TEST_SANDBOX_URL=
WAYFINDER_TEST_SANDBOX_TOKEN=
```

`WAYFINDER_VERIFIER_RUNNER=sandboxed_mcp` performs a live health check against
`WAYFINDER_TEST_SANDBOX_URL`. When the worker is healthy, high-risk executable
claims are sent to `POST /run-test`; otherwise runtime claims stay
`unverified`. The API never runs arbitrary public repo tests inside
`wayfinder-api`.

`WAYFINDER_GRAPH_NODE_TIMEOUT_SECONDS` protects slow graph boundaries,
including pre-approved public verifier runs. Manual LangGraph verifier HITL
remains unwrapped so `interrupt()` / `Command(resume=...)` can keep its runnable
context.

In `sandboxed_mcp` mode, verifier test requests are auto-approved by default
because execution is already isolated in the sandbox worker. Set
`WAYFINDER_VERIFIER_APPROVAL_MODE=interrupt` to restore LangGraph pre-test HITL
for local/manual runs, or `auto_skip` to keep executable claims unverified.

Local sandbox worker:

```bash
docker compose up --build api sandbox-worker dashboard
WAYFINDER_VERIFIER_RUNNER=sandboxed_mcp docker compose up --build api sandbox-worker dashboard
```

The Compose topology keeps `/data` for API SQLite history and shares only the
repo cache volume with the worker. On separate Railway services, the worker may
not see the API repo cache, so the request also carries the GitHub repo URL and
the worker shallow-clones that public repo into an ephemeral directory. In both
modes it denies unsafe filters such as shell metacharacters or package-install
tokens, runs a bounded pytest/Jest command with `shell=False`, truncates output,
and cleans up the workdir.

For a separate Railway sandbox service, use `Dockerfile.sandbox` and wire the
API with `WAYFINDER_TEST_SANDBOX_URL=<sandbox-worker-url>` only after the worker
health endpoint is reachable.

Cloud Run:

```bash
gcloud builds submit --config cloudbuild.yaml
gcloud run deploy wayfinder-api \
  --image us-central1-docker.pkg.dev/$PROJECT_ID/wayfinder/wayfinder-api:$COMMIT_SHA \
  --region us-central1 \
  --allow-unauthenticated
```

Live URL:

```text
Dashboard: https://wayfinder-dashboard-production-f8d7.up.railway.app
API docs: https://wayfinder-api-production.up.railway.app/docs
API health: https://wayfinder-api-production.up.railway.app/health
```

## Demo And Launch Assets

- Demo recording script: [`docs/demo/recursive_demo_script.md`](docs/demo/recursive_demo_script.md)
- Public smoke evidence: [`docs/evidence/commit19_public_smoke.md`](docs/evidence/commit19_public_smoke.md), [`docs/evidence/commit21_repo_threads_public_smoke.md`](docs/evidence/commit21_repo_threads_public_smoke.md)
- Bilingual launch draft: [`docs/blog/wayfinder_launch_post.md`](docs/blog/wayfinder_launch_post.md)
- Deploy notes: [`docs/deploy/README.md`](docs/deploy/README.md)

## Enterprise Workflow Case Study

To show that Wayfinder's agent architecture generalizes beyond codebase
onboarding, the repo includes a permission-gated recruiting CRM workflow demo.

The demo simulates an enterprise agent that parses synthetic candidate profiles,
matches roles, drafts referral outreach, routes high-risk actions through human
approval, writes audit logs, and blocks unsafe actions. It uses only local mock
data and does not connect to Gmail, Salesforce, a real CRM, login, or external
accounts.

Run it locally:

```bash
uv run python examples/enterprise_workflow/recruiting_crm_demo.py
```

Case-study docs:

- [`docs/case_studies/enterprise_workflow_agent.md`](docs/case_studies/enterprise_workflow_agent.md)
- [`docs/case_studies/enterprise_eval_report.md`](docs/case_studies/enterprise_eval_report.md)

## Lessons Learned

- Deterministic tools should own source truth;LLMs should not invent structure or symbols.
- LLMs are the synthesis layer:use them to turn bounded MCP/verifier evidence into a readable answer, not to create new facts.
- Repo threads are the user workspace; runs are execution traces linked to messages.
- `unverified` is a product state. It prevents missing coverage from becoming fake confidence.
- Graph resume needs the same `thread_id` in API state, LangGraph config, and trace metadata.
- Observability should start as a schema contract before dashboards and evals depend on it.
- Local deploy evidence should not pretend to be public deployment evidence.

## Interview Talking Points

- "Wayfinder is a codebase onboarding workflow, not a chatbot wrapper."
- "I used three self-authored MCP servers as the fact layer, then LangGraph as the orchestration layer."
- "Conversation memory gives continuity, but new code facts still go through repo/AST/test evidence."
- "The verifier only checks high-risk runtime claims and labels missing coverage as unverified."
- "The reflection loop repairs unsafe final prose without inventing new facts or changing verifier labels."
- "The dashboard reads the same run summary and trace metadata that Project 7 can use for evals."
