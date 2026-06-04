# 010 — Dashboard, Deploy, And Ship Evidence

## Status

Commit 8 design completed on 2026-06-04. The implementation goal is a local
ship-evidence pass:dashboard, deploy configuration, CI, README, design v1,
demo script, and bilingual launch draft.

External deploy status is honest:Railway CLI reported that this checkout has no
linked project, so Commit 8 cannot claim a verified public URL. The repo is
deploy-ready through Docker, Railway config, and Cloud Build config;the live URL
must be filled after `railway link && railway up` or Cloud Run deploy in an
account-owned project.

## Source-Backed Constraints

- Next.js can read environment variables at runtime in server components and
  can produce a standalone server bundle with `output: "standalone"`.
- FastAPI exposes OpenAPI docs at `/docs` and the existing API already exposes
  `/health`, `/explain`, `/status/{job_id}`, `/refine/{job_id}`, and `/runs`.
- Docker Compose can coordinate API and dashboard services with healthcheck
  based `depends_on`. The Project 5 MCP servers remain stdio-first, so they are
  included as optional `mcp` profile services rather than falsely wired as HTTP
  sidecars.
- GitHub Actions can checkout multiple repositories into sibling paths. That
  matches Project 6's local editable dependency contract:
  `../project5/mcp-repo-mapper`, `../project5/mcp-ast-explorer`, and
  `../project5/mcp-test-runner`.

## Commit 8 Boundary

In scope:

- Dashboard reads `/runs?limit=10` from the API and falls back to seeded demo
  runs when API is unavailable.
- Dashboard panels cover recent runs, trace links, per-agent P50/P95 latency,
  token/cost totals, routing flow, verification stats, and failure mode
  frequency.
- API exposes `/runs` for recent job polling.
- Dockerfile and Compose configuration run the API and dashboard locally.
- Project 5 MCP service definitions are present in Compose under an explicit
  `mcp` profile.
- CI checks backend, dashboard lint/type/build, and Project 5 integration after
  checking out the three Project 5 MCP repos as siblings.
- README documents architecture, quickstart, API spec, curl examples, eval
  evidence, failure modes, lessons learned, deploy path, and interview
  soundbites.
- `DESIGN.md` is promoted from v0 to v1.0 with the current state of the graph,
  API runtime, observability, and failure-mode mitigations.
- Demo script and bilingual launch post are ready for recording/posting.

Out of scope:

- Claiming an unverified public URL.
- Rewriting Project 5 servers from stdio to HTTP.
- Production multi-worker queue or persistent run DB.
- New Project 7 eval benchmark numbers.
- Creating a fake demo GIF/video artifact without recording the app.

## Dashboard Data Contract

The dashboard server component calls:

```text
GET {WAYFINDER_API_BASE_URL}/runs?limit=10
```

If the API is down or returns no runs, the dashboard displays seeded demo data
with the same shape. This keeps `npm run build` and Docker image creation
stable in CI while still making the first screen useful during live API runs.

The dashboard transforms snake_case API fields into a UI model:

- `job_id` -> `jobId`
- `repo_url` -> `repoName` / `repoUrl`
- `status`, `current_node`, `final_output`, `error`
- `partial_summaries`
- `errors`
- `user_corrections`
- claim counts
- `trace_url`
- `trace_metadata`

Dashboard metrics are derived only from API state:

- P50/P95 latency from `trace_metadata.latency`
- token and cost totals from `trace_metadata.tokens` and `cost_usd`
- agent/tool/MCP labels from `trace_metadata`
- failure modes from structured errors plus contradicted claims
- routing flow from query-derived intent until API persists route decisions

## Deploy Contract

Local:

```bash
docker compose up --build api dashboard
```

Optional Project 5 MCP profile:

```bash
docker compose --profile mcp up --build
```

The default Compose stack runs with placeholder MCP modes because Project 5
servers are stdio-first packages. Local developer mode still supports real MCP
execution through editable Project 5 dependencies and the env-gated integration
test.

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

## Test Matrix

- `uv run pytest -q`
- `uv run ruff check .`
- `uv run mypy src tests`
- `WAYFINDER_RUN_PROJECT5_MCP_INTEGRATION=1 uv run pytest tests/test_project5_mcp_integration.py -q -rs`
- `npm run lint`
- `npm run typecheck`
- `npm run build`
- `docker build -f Dockerfile.api .`
- `docker build -f dashboard/Dockerfile dashboard`
- `git diff --check`

## Interview Explanation

"Commit 8 is the local ship pass. I turned the runtime state into a dashboard
surface, made the dashboard read real API run records with a demo fallback,
added deploy files and CI that checks both the main app and the three MCP
server integrations, and promoted the project docs from prototype to
portfolio-ready. I also kept the external deploy line honest:the repo is
deploy-ready, but the live URL is not marked complete until an account-owned
Railway or Cloud Run project is linked and verified."
