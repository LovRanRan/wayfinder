# Commit 17 — User Workspaces + Persistent Run History

## Problem

The public demo started with a deployment-level GitHub allowlist and an in-memory run store. That was acceptable for a controlled demo, but it does not match the product shape Haichuan wants:

- a user can paste a repo link locally or online,
- each user sees only their own previous analyses,
- public repo access is not limited to a fixed environment allowlist,
- LLM usage can later move to user-owned API keys,
- online test execution remains gated until sandboxing exists.

## Boundary

Commit 17 upgrades Wayfinder from a global demo console to a private workspace console. It does not try to ship every SaaS feature in one step.

In scope:

- username/password workspace registration and login,
- server-issued session tokens,
- dashboard HTTP-only session cookie,
- user-scoped `/runs`, `/status/{job_id}`, `/refine/{job_id}`, and `/explain`,
- SQLite-backed persistent run history selected by env,
- redesigned dashboard around login, account state, current run, and user history.

Out of scope for this commit:

- GitHub OAuth,
- private GitHub repo tokens,
- persisted user OpenAI keys,
- Postgres migration layer,
- sandboxed online test execution.

## Access Model

The API supports two modes:

1. **Local/dev mode**: auth is optional and requests are assigned to `local-dev`.
2. **Workspace mode**: `WAYFINDER_REQUIRE_AUTH=1` requires a valid bearer session for run endpoints.

The dashboard never exposes the session token to browser JavaScript. Login/register routes call the API, then store the token in an HTTP-only cookie. Dashboard proxy routes forward that cookie as an API bearer token.

## Persistence Model

`WAYFINDER_RUN_STORE=sqlite` or `WAYFINDER_RUN_STORE_PATH=/path/to/runs.sqlite` enables a SQLite store with:

- `users`
- `sessions`
- `runs`

The persisted run record includes the public `RunSummary` plus the minimal graph input needed for refine. Runtime execution is still single-process; a later commit can add cross-process job recovery if needed.

## Repo Access Policy

For the desired product behavior, the deployment can set:

```env
WAYFINDER_ENABLE_GITHUB_INGESTION=1
WAYFINDER_GITHUB_REPO_ALLOWLIST=*
WAYFINDER_GITHUB_MAX_FILES=10000
```

This opens public GitHub repo analysis while preserving size limits. Private repos require GitHub OAuth/token support in a future commit.

## Test Runner Policy

Auth does not make arbitrary test execution safe. `mcp-test-runner` should remain disabled in public deploy until test execution runs inside an isolated sandbox with no inherited deployment secrets, strict timeout, CPU/memory/disk limits, and network policy.

## Interview Explanation

This commit changes Wayfinder from a single shared demo board into a multi-user workspace. The important design decision is that identity and persistence are product boundaries, while code execution remains a separate sandbox boundary. Auth and DB let users keep their own history; they do not by themselves make untrusted repo code safe to execute.
