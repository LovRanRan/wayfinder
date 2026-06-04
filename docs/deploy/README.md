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

This checkout is not linked to a Railway project yet.

```bash
railway link
railway up
```

After deploy, set:

```bash
WAYFINDER_API_BASE_URL=<internal-or-public-api-url-reachable-from-dashboard>
NEXT_PUBLIC_WAYFINDER_API_BASE_URL=https://<your-wayfinder-api>.up.railway.app
WAYFINDER_ENABLE_GITHUB_INGESTION=1
WAYFINDER_GITHUB_REPO_ALLOWLIST=langchain-ai/langchain,LovRanRan/wayfinder
WAYFINDER_GITHUB_MAX_FILES=10000
WAYFINDER_GITHUB_CACHE_ROOT=/tmp/wayfinder/repos
```

If Railway gives the dashboard an internal service DNS for the API, use that for
`WAYFINDER_API_BASE_URL` and keep the public API URL in
`NEXT_PUBLIC_WAYFINDER_API_BASE_URL` for browser links.

Keep `WAYFINDER_GITHUB_REPO_ALLOWLIST` narrow for a public portfolio demo. Use
`*` only for a private trusted deployment; otherwise any visitor can make the
API spend time cloning arbitrary GitHub repos.

Then update the live URL section in `README.md`.

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
