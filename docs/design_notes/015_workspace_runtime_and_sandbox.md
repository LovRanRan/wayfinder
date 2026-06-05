# Commit 18 Design Note: Workspace Runtime Settings And Sandbox Policy

## Problem

Wayfinder is now a grounded LLM copilot with per-user workspaces and saved run
history. The remaining product gap is runtime ownership: a public user should be
able to analyze any allowed public GitHub repo using their own model key, while
their previous runs stay private to their workspace.

Authentication solves identity and history. It does not make arbitrary test
execution safe. `mcp-test-runner` can execute repository code, so public deploys
must treat it as a separate sandbox boundary.

## Threat Model

Inputs controlled by users:

- GitHub repository URL.
- Natural-language query.
- Workspace OpenAI API key and model choice.
- Future test execution target or approval decision.

Risks:

- Leaking a user's API key through run JSON, trace metadata, logs, or dashboard
  output.
- Letting one workspace read another workspace's settings or runs.
- Running arbitrary repo code inside the API container.
- Treating unsupported or disabled test execution as verified evidence.
- Allowing the dashboard to silently fall back to the platform/global key when a
  workspace key is expected.

## User-Owned API Key Policy

The workspace settings API owns runtime provider configuration.

Stored fields:

- `openai_api_key_encrypted`: encrypted secret envelope, never returned by API.
- `openai_api_key_label`: masked label such as `sk-...abcd`.
- `openai_model`: model passed to OpenAI runtime.
- `llm_routing`: `off` or `openai`.
- `final_writer`: `deterministic` or `openai`.

The backend decrypts the key only while building the runtime env for a run. The
decrypted value is not written to `RunSummary`, graph input, trace metadata, or
dashboard responses.

Deployment must set `WAYFINDER_KEY_ENCRYPTION_SECRET` before accepting workspace
keys. Without that secret, settings can still update non-secret fields, but key
storage is rejected.

## Sandbox Boundary

Default public verifier mode remains:

```env
WAYFINDER_VERIFIER_RUNNER=placeholder
```

This disables executable test verification while preserving repository and AST
evidence. Runtime/behavior claims that require tests stay `unverified`.

`WAYFINDER_VERIFIER_RUNNER=sandboxed_mcp` is reserved for a separate sandbox
worker or local isolated runner. It must not run command execution in
`wayfinder-api`. The API may only treat the sandbox as enabled when:

- `WAYFINDER_TEST_SANDBOX_URL` is configured.
- A health gate reports ready through `WAYFINDER_TEST_SANDBOX_HEALTH=ok` or an
  equivalent live health check in a future worker implementation.
- Denied operations, timeouts, missing test coverage, and output limits are
  surfaced as limitations, not hidden failures.

Commit 18 implements the policy gate and status reporting. It keeps public test
execution disabled unless that explicit gate passes.

## Contracts

### `GET /workspace/settings`

Returns the current workspace runtime settings without secrets:

- workspace id and display name.
- whether a key is configured.
- masked key label.
- model, routing mode, final writer mode.
- verifier runner mode.
- sandbox status and message.

### `PUT /workspace/settings`

Accepts:

- optional `openai_api_key`.
- optional `clear_openai_api_key`.
- optional `openai_model`.
- optional `llm_routing`.
- optional `final_writer`.

The response is the same secret-free settings object.

## Failure Modes

- Missing encryption secret while saving a key: reject with a clear API error.
- Corrupt encrypted key: fail the affected run with a runtime settings error.
- Missing workspace key while OpenAI mode is selected: fail the run honestly
  rather than falling back to another user's or platform key.
- Sandbox disabled/unhealthy: verifier remains unavailable and executable claims
  remain unverified.
- Unsupported runtime mode: reject settings update or fail graph construction
  with a precise mode error.

## Tests

Backend tests cover:

- default settings response.
- settings are scoped per user.
- key storage requires `WAYFINDER_KEY_ENCRYPTION_SECRET`.
- settings responses never return the raw key.
- a run receives the decrypted workspace key in its runtime env.
- sandbox status remains disabled by default and only reports enabled behind the
  explicit gate.

Frontend checks cover:

- Settings tab renders workspace runtime state.
- saving model/key settings calls the dashboard proxy.
- configured key is shown only as a masked label.

## Railway And Local Deployment

API service variables:

```env
WAYFINDER_REQUIRE_AUTH=1
WAYFINDER_RUN_STORE=sqlite
WAYFINDER_RUN_STORE_PATH=/data/wayfinder/runs.sqlite
WAYFINDER_KEY_ENCRYPTION_SECRET=<long-random-secret>
WAYFINDER_VERIFIER_RUNNER=placeholder
WAYFINDER_ENABLE_GITHUB_INGESTION=1
WAYFINDER_GITHUB_REPO_ALLOWLIST=*
```

Mount a Railway volume at `/data` before relying on SQLite history. Keep
`WAYFINDER_VERIFIER_RUNNER=placeholder` in the public demo unless a separate
sandbox worker is deployed and health-gated.

## Interview Explanation

Commit 18 separates three responsibilities:

- Auth/database decides who owns runs and settings.
- Workspace runtime settings decide which model key and synthesis mode a user
  runs with.
- Sandbox policy decides whether untrusted repository code can execute.

That split is the important product/security point: BYOK and login make the
copilot usable for public users, but they do not weaken the verification policy.
