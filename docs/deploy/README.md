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
falls back to seeded demo data when there are no runs.

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
WAYFINDER_API_BASE_URL=https://<your-wayfinder-api>.up.railway.app
NEXT_PUBLIC_WAYFINDER_API_BASE_URL=https://<your-wayfinder-api>.up.railway.app
```

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
