# Recursive Demo Script

Target length: 3 minutes.

Status: ready to record after a public API/dashboard URL is available. Do not
publish a fake video link before recording.

## Setup

Demo target:

```text
langchain-ai/langchain pinned commit
```

Local run:

```bash
uv run uvicorn wayfinder.api.main:app --reload
cd dashboard
WAYFINDER_API_BASE_URL=http://localhost:8000 npm run dev
```

## Script

### 0:00-0:20 — Product Frame

"This is Wayfinder, a verifier-backed codebase onboarding copilot. The problem
is that codebase explanation tools often sound confident before they are
grounded. Wayfinder separates verified facts, unverified claims, and
contradicted claims."

Show dashboard top metrics: verification rate, active runs, P95 latency, cost.

### 0:20-0:55 — Architecture Run

Start a run:

```bash
curl -X POST http://localhost:8000/explain \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"<local-langchain-path>","query":"Map the architecture and entry points"}'
```

Poll:

```bash
curl http://localhost:8000/status/<job_id>
```

Show that the run passes through Supervisor -> `architect_mapper` and uses
`mcp-repo-mapper` evidence.

### 0:55-1:35 — Recursive Entry Explanation

Ask Wayfinder about its own `wayfinder.api.main:explain` path.

Show the dashboard run row and trace link. Explain that `entry_explainer` uses
AST evidence from `mcp-ast-explorer` rather than inventing symbols.

### 1:35-2:10 — Verification And Reflection

Show a run with verifier evidence. Call out:

- `verified`
- `unverified`
- `contradicted`

Explain that contradicted claims trigger a bounded reflection rewrite rather
than silently shipping unsafe prose.

### 2:10-2:40 — Refine/Resume

Send:

```bash
curl -X POST http://localhost:8000/refine/<job_id> \
  -H "Content-Type: application/json" \
  -d '{"correction":"intent=behavioral"}'
```

Show same `thread_id` in trace metadata and the updated dashboard row.

### 2:40-3:00 — Why It Matters

"The point is not another chatbot UI. The point is an evidence workflow:
deterministic MCP tools gather facts, LangGraph coordinates the path, verifier
labels risky claims, and the dashboard makes the run inspectable."

End on the dashboard failure-mode panel and README architecture diagram.
