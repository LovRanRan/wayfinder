# Commit 21 Repo Threads Public Smoke Evidence

Date: 2026-06-09

Environment:

- Dashboard: https://wayfinder-dashboard-production-f8d7.up.railway.app
- API: https://wayfinder-api-production.up.railway.app
- Deployed commit: `532a87eff999`
- Auth mode: `WAYFINDER_REQUIRE_AUTH=1`
- Workspace mode: self-registered smoke workspace; password intentionally not recorded
- Runtime settings for smoke: `llm_routing=off`, `final_writer=deterministic`
- Verifier runner: `sandboxed_mcp`

## Deploy Checks

| Check | Result | Evidence |
|---|---|---|
| GitHub push | Passed | `main` advanced from `d477a8f` to `532a87e` |
| API health | Passed | `/health` returned `status=ok` and `commit=532a87eff999` |
| API thread auth boundary | Passed | unauthenticated `GET /threads` returned `401 login required` |
| Dashboard proxy thread route | Passed | unauthenticated `GET /api/wayfinder/threads` returned `401 login required` after dashboard redeploy |

## Conversation Smoke

| Step | Result | Evidence |
|---|---|---|
| Register smoke workspace through dashboard proxy | Passed | workspace `codex-smoke-20260609004619` created |
| Set deterministic runtime | Passed | settings returned `llm_routing=off`, `final_writer=deterministic` |
| Create repo thread | Passed | repo `https://github.com/pallets/click`, thread `2bb0e2be-dee8-4bf7-9358-8339eadbb91c`, initial run `447cdabb-65dd-4191-aaba-00547163d25b` |
| Initial answer persisted | Passed | thread returned `messages=2`, `runs=1`, assistant message linked to the initial run |
| Follow-up 1 | Passed | question `Which files should I inspect first?`, run `ee9d617f-abc3-45bf-9398-6342cb99f0d8`, thread returned `messages=4`, `runs=2` |
| Follow-up 2 | Passed | question `What limitation should I keep in mind from the evidence?`, run `997900d5-545d-457f-8668-870e65dfb8c6`, thread returned `messages=6`, `runs=3` |
| Memory layer | Passed | `summary_memory` included initial question, first follow-up, second follow-up, and truncated assistant context |

## Not Claimed

- This smoke used dashboard API routes plus prior local Browser UI smoke; it did not claim a new public visual screenshot of the authenticated Threads tab.
- The smoke workspace password is not preserved, so the listed thread is audit evidence rather than a reusable demo account.
- Deterministic public smoke does not prove OpenAI BYOK answer quality; it proves repo-thread persistence, follow-up routing, and memory continuity without relying on user credentials.
