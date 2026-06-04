# Deploy Notes

## Local Docker Compose

Run API and dashboard:

```bash
docker compose up --build api dashboard
```

Open:

- API health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`
- Dashboard: `http://localhost:3000`

The dashboard reads `WAYFINDER_API_BASE_URL=http://api:8000` inside Compose and
falls back to seeded demo data when there are no runs. Browser actions submit
through dashboard proxy routes, so the public UI does not need direct CORS
access to the API service.

## Optional MCP Profile

Project 5 MCP servers are stdio-first packages. Compose includes them as an
optional profile so the process topology is documented without pretending they
are HTTP sidecars.

```bash
docker compose --profile mcp up --build
```

For real tool execution in development, keep using the env-gated Project 5
integration path:

```bash
WAYFINDER_RUN_PROJECT5_MCP_INTEGRATION=1 uv run pytest tests/test_project5_mcp_integration.py -q -rs
```

## Railway

Current Railway project:

- Project: `wayfinder`
- Project URL: <https://railway.com/project/1bf2ff55-6588-4cd2-a144-d2ece69005a2>
- API: <https://wayfinder-api-production.up.railway.app>
- Dashboard: <https://wayfinder-dashboard-production-f8d7.up.railway.app>

Current deploy mode is GitHub-backed deploy from `LovRanRan/wayfinder` on
`main`. The first deploy was a CLI snapshot deploy from commit `c1c09c4`;
Railway UI GitHub connection was completed on 2026-06-04 and both services
redeployed successfully.

Create or link the project:

```bash
railway link
```

API service:

```bash
railway add --service wayfinder-api
railway variable set -s wayfinder-api --skip-deploys \
  WAYFINDER_START_PROJECT5_HTTP_MCP=1 \
  WAYFINDER_ARCHITECTURE_SCANNER=mcp_http \
  WAYFINDER_ENTRY_SCANNER=mcp_http \
  WAYFINDER_VERIFIER_RUNNER=placeholder \
  WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL=http://127.0.0.1:8101/mcp \
  WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL=http://127.0.0.1:8102/mcp \
  WAYFINDER_ENABLE_GITHUB_INGESTION=1 \
  WAYFINDER_GITHUB_REPO_ALLOWLIST=langchain-ai/langchain,LovRanRan/wayfinder \
  WAYFINDER_GITHUB_MAX_FILES=10000 \
  WAYFINDER_GITHUB_CACHE_ROOT=/tmp/wayfinder/repos
railway up --service wayfinder-api --detach --message c1c09c4-railway-runtime-fix
railway domain --service wayfinder-api --port 8000
```

`WAYFINDER_START_PROJECT5_HTTP_MCP=1` starts `mcp-repo-mapper` and
`mcp-ast-explorer` as stateless FastMCP HTTP sidecars inside the API container.
They intentionally use localhost URLs because they need access to the same
cloned repository paths as the API process. Do not split these reader MCPs into
separate Railway services until the tool input contract changes from local path
to repo URL or shared artifact.

`mcp-test-runner` should stay disabled for public HTTP deployment until remote
command execution has sandbox/auth controls. With `mcp-ast-explorer` enabled,
the verifier can still mark deterministic AST facts as verified, such as symbol
definition location and signature. Runtime/data-flow claims without a focused
test target remain unverified instead of being treated as test-backed.

Dashboard service:

```bash
railway add --service wayfinder-dashboard
railway variable set -s wayfinder-dashboard --skip-deploys \
  WAYFINDER_API_BASE_URL=https://wayfinder-api-production.up.railway.app \
  NEXT_PUBLIC_WAYFINDER_API_BASE_URL=https://wayfinder-api-production.up.railway.app
railway up --service wayfinder-dashboard --detach --path-as-root dashboard \
  --message c1c09c4-railway-dashboard-path-root
railway domain --service wayfinder-dashboard --port 3000
```

Do not deploy the dashboard from the repo root without `--path-as-root
dashboard`; otherwise Railway reads the root `railway.json` and builds
`Dockerfile.api`.

For GitHub-backed deploys, keep the dashboard service root directory set to
`/dashboard` in Railway Settings. Keep the API service root directory at the
repo root and set `RAILWAY_DOCKERFILE_PATH=Dockerfile.api`.

For a new Railway project, set:

```bash
WAYFINDER_API_BASE_URL=<internal-or-public-api-url-reachable-from-dashboard>
NEXT_PUBLIC_WAYFINDER_API_BASE_URL=https://<your-wayfinder-api>.up.railway.app
WAYFINDER_START_PROJECT5_HTTP_MCP=1
WAYFINDER_ARCHITECTURE_SCANNER=mcp_http
WAYFINDER_ENTRY_SCANNER=mcp_http
WAYFINDER_VERIFIER_RUNNER=placeholder
WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL=http://127.0.0.1:8101/mcp
WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL=http://127.0.0.1:8102/mcp
WAYFINDER_ENABLE_GITHUB_INGESTION=1
WAYFINDER_GITHUB_REPO_ALLOWLIST=langchain-ai/langchain,LovRanRan/wayfinder
WAYFINDER_GITHUB_MAX_FILES=10000
WAYFINDER_GITHUB_CACHE_ROOT=/tmp/wayfinder/repos
```

`WAYFINDER_VERIFIER_RUNNER=placeholder` disables test execution only. AST-backed
definition/signature verification still works when `WAYFINDER_ENTRY_SCANNER` is
`mcp_http` and the AST evidence tool returns a found symbol.

If Railway gives the dashboard an internal service DNS for the API, use that for
`WAYFINDER_API_BASE_URL` and keep the public API URL in
`NEXT_PUBLIC_WAYFINDER_API_BASE_URL` for browser links.

Keep `WAYFINDER_GITHUB_REPO_ALLOWLIST` narrow for a public portfolio demo. Use
`*` only for a private trusted deployment; otherwise any visitor can make the
API spend time cloning arbitrary GitHub repos.

Smoke checks:

```bash
curl -fsS https://wayfinder-api-production.up.railway.app/health
curl -fsS 'https://wayfinder-api-production.up.railway.app/runs?limit=3'
curl -fsSI https://wayfinder-dashboard-production-f8d7.up.railway.app
curl -fsS -X POST https://wayfinder-dashboard-production-f8d7.up.railway.app/api/wayfinder/explain \
  -H 'content-type: application/json' \
  --data '{"repo_url":"https://github.com/langchain-ai/langchain","query":"Where should a new contributor start?"}'
```

## Cloud Run

Build the API image:

```bash
gcloud builds submit --config cloudbuild.yaml
```

Deploy:

```bash
gcloud run deploy wayfinder-api \
  --image us-central1-docker.pkg.dev/$PROJECT_ID/wayfinder/wayfinder-api:$COMMIT_SHA \
  --region us-central1 \
  --allow-unauthenticated
```

For dashboard deployment, build `dashboard/Dockerfile` and set
`WAYFINDER_API_BASE_URL` to the Cloud Run API URL.
