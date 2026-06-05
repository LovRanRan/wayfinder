# Commit 19 Public Smoke Evidence

Date: 2026-06-05

Environment:

- Dashboard: https://wayfinder-dashboard-production-f8d7.up.railway.app
- API: https://wayfinder-api-production.up.railway.app
- Auth mode: `WAYFINDER_REQUIRE_AUTH=1`
- Run store: `WAYFINDER_RUN_STORE=sqlite`, `WAYFINDER_RUN_STORE_PATH=/data/wayfinder/runs.sqlite`
- Public repo ingestion: `WAYFINDER_ENABLE_GITHUB_INGESTION=1`, `WAYFINDER_GITHUB_REPO_ALLOWLIST=*`
- Reader MCPs: `mcp-repo-mapper` and `mcp-ast-explorer` over localhost HTTP sidecars
- Verifier runner: `placeholder`; public executable test execution remains disabled until a separate sandbox worker exists
- Shared `OPENAI_API_KEY`: intentionally empty in authenticated workspace mode; successful LLM-mode runs use the workspace-owned key

## Smoke Matrix

| Repo | Prompt | Route / Tool | Result | Evidence and limitation |
|---|---|---|---|---|
| `LovRanRan/wayfinder` | `Explain the behavior and data flow through wayfinder.graph.app.build_graph` | `entry_explainer` / `find_references` / `ast_explorer` | Completed, 23.1s, 3 verified / 1 unverified / 0 contradicted | Verified AST facts include `src/wayfinder/graph/app.py:48`, signature evidence, and graph construction. Data-flow/runtime behavior remains unverified without executable test evidence. |
| `pallets/click` | `Explain the behavior and data flow through click.core.Command.main` | `entry_explainer` / `find_references` / `ast_explorer` | Completed, 48.0s, 3 verified / 1 unverified / 0 contradicted | Verified definition/signature evidence for `src/click/core.py`; answer correctly preserved the overload-declaration limitation instead of inventing the implementation body. |
| `psf/requests` | `Explain the architecture and where a new contributor should begin.` | `architect_mapper` / `repo_structure` / `repo_mapper` | Completed, 8.3s, 0 verified / 0 unverified / 0 contradicted | Architecture summary came from repository structure and import graph. It did not claim behavioral/test-verified facts. |
| `langchain-ai/langchain` | `Explain the architecture and where a new contributor should begin.` | `architect_mapper` / `repo_structure` / `repo_mapper` | Completed after degradation fix | A UTF-8 repository scan failure was preserved as an explicit limitation; Wayfinder did not fabricate an architecture map from unavailable evidence. |

## Product Checks

- Login/workspace shell is live on the public dashboard.
- Recent runs are user-scoped in the authenticated API surface.
- Page reload preserves visible run history.
- Answer tab deep links preserve the selected job with `?job=<job_id>&tab=answer`.
- Run tab is scoped to submission, selected-job status, runtime boundary, and recent answer links; full answer rendering stays in the dedicated Answer tab.
- Active run UI shows elapsed time and animated evidence/synthesis stages while polling.
- After an active run completes, the dashboard refreshes the server-backed stats/history surface once so P95 latency, active-run count, and recent runs do not require manual reload.

## Not Claimed Yet

- Demo video is not recorded yet.
- API restart persistence with the Railway `/data` volume is not independently smoke-tested yet, though page reload persistence is observed.
- Public test execution through `mcp-test-runner` is intentionally not enabled. Auth and BYOK do not make arbitrary public repo code safe to run inside the API container.
