# wayfinder

Verifier-backed codebase onboarding copilot for engineers entering an unfamiliar repository.

`wayfinder` maps architecture, explains entry paths from AST evidence, verifies high-risk code understanding claims with tests, and shows uncertainty instead of hiding it.

## Status

- Local API/runtime: ready
- Dashboard: ready with live API fetch and seeded demo fallback
- Project 5 MCP integration: env-gated integration passing locally
- Docker/Compose: deploy-ready
- Public live URL: pending external Railway or Cloud Run project link
- Demo video: script ready, recording pending public URL

## Why This Exists

Most codebase explanation tools sound confident before they are grounded. They can summarize README text, name plausible modules, or explain functions that may not exist.

`wayfinder` treats onboarding as an evidence workflow:

1. Gather deterministic architecture and AST evidence through MCP tools.
2. Route the user's question through a LangGraph Supervisor.
3. Verify high-risk runtime claims with focused tests.
4. Label claims as `verified`, `unverified`, or `contradicted`.
5. Rewrite final output when verifier evidence contradicts earlier prose.

## Architecture

```text
User / Dashboard
      |
      v
FastAPI runtime
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
      +--> verifier          -> mcp-test-runner
      |
      v
final_writer + resilience/reflection layer
      |
      v
RunSummary + trace metadata + dashboard panels
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

### `POST /explain`

Starts a queued run.

```bash
curl -X POST http://localhost:8000/explain \
  -H "Content-Type: application/json" \
  -d '{"repo_url":".","query":"Map the architecture and entry points"}'
```

GitHub URLs are supported when `WAYFINDER_ENABLE_GITHUB_INGESTION=1` and the
repo is present in `WAYFINDER_GITHUB_REPO_ALLOWLIST`. The API shallow-clones the
repo into the Wayfinder cache and rejects repos over `WAYFINDER_GITHUB_MAX_FILES`
files.

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

The dashboard reads `GET /runs?limit=10` from `WAYFINDER_API_BASE_URL`.
The browser-facing launcher uses dashboard proxy routes:

- `POST /api/wayfinder/explain`
- `GET /api/wayfinder/status/{job_id}`
- `POST /api/wayfinder/refine/{job_id}`

For split-service deploys, set `WAYFINDER_API_BASE_URL` to the API address the
dashboard server can reach, and set `NEXT_PUBLIC_WAYFINDER_API_BASE_URL` to the
public API URL shown in browser links.

Panels:

- recent runs table with trace links;
- run launcher with submit, polling, refresh, and refine actions;
- per-agent P50/P95 latency;
- token usage and cost overview;
- routing decision flow;
- verification stats;
- failure mode frequency;
- current run summary.

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

Current local evidence from Commit 8:

- backend tests: 149 passed / 8 skipped after `/runs` addition
- API tests: lifecycle, recent runs, refine/resume, 409 conflict, error serialization, trace metadata hooks
- Project 5 MCP integration: repo mapper, AST explorer, and test runner all pass through real local MCP packages
- dashboard: typecheck/build/lint gates

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
railway up
```

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
pending: no Railway project is linked in this checkout yet
```

## Demo And Launch Assets

- Demo recording script: [`docs/demo/recursive_demo_script.md`](docs/demo/recursive_demo_script.md)
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
- `unverified` is a product state. It prevents missing coverage from becoming fake confidence.
- Graph resume needs the same `thread_id` in API state, LangGraph config, and trace metadata.
- Observability should start as a schema contract before dashboards and evals depend on it.
- Local deploy evidence should not pretend to be public deployment evidence.

## Interview Talking Points

- "Wayfinder is a codebase onboarding workflow, not a chatbot wrapper."
- "I used three self-authored MCP servers as the fact layer, then LangGraph as the orchestration layer."
- "The verifier only checks high-risk runtime claims and labels missing coverage as unverified."
- "The reflection loop repairs unsafe final prose without inventing new facts or changing verifier labels."
- "The dashboard reads the same run summary and trace metadata that Project 7 can use for evals."
