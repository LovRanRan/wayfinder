# Commit 20 Design Note: Sandboxed Test Runner Worker

## Problem

Wayfinder can already ground static code facts through read-only Project 5 MCP
servers. The remaining verification gap is executable evidence: runtime claims
should be testable without running untrusted repository code inside
`wayfinder-api`.

Authentication, BYOK, and private run history identify who owns a run. They do
not make public repository tests safe. Commit 20 moves executable verifier work
behind a separate sandbox worker boundary.

## Threat Model

User-controlled inputs:

- GitHub repo URL and cloned checkout contents.
- Natural-language query that can influence selected test targets.
- Test target strings attached to high-risk claims.
- Optional approve/skip/modify-filter decisions from the existing verifier HITL
  contract.

Main risks:

- Arbitrary shell execution through a crafted test target.
- Package install or network-fetch commands smuggled into the runner.
- Destructive filesystem operations inside the API container.
- App secrets inherited by the process that runs repository tests.
- Unbounded output, long-running tests, or leftover workspace state.
- Claiming executable verification when the sandbox is missing or unhealthy.

## Worker Topology

`wayfinder-api` keeps `WAYFINDER_VERIFIER_RUNNER=placeholder` as the safe default.
Executable verification is enabled only when:

```env
WAYFINDER_VERIFIER_RUNNER=sandboxed_mcp
WAYFINDER_TEST_SANDBOX_URL=http://sandbox-worker:8110
```

The API performs a live `GET /health` check against the worker. If the check
fails, the runtime reports `sandbox_status=unavailable` and returns no test
runner to the graph. Runtime claims remain `unverified`.

The sandbox worker runs as a separate FastAPI service. It receives no OpenAI
key, no session secret, no key-encryption secret, and no API database path. In
Docker Compose it mounts only the repo cache volume read-only, copies the
selected repo into an ephemeral workdir, executes a bounded test command, returns
a normalized observation, and deletes the workdir.

## Request Contract

`POST /run-test`

```json
{
  "test_ref": "test-0",
  "claim_refs": ["claim-0"],
  "framework": "pytest",
  "tool_name": "run_single_test",
  "path": "/repo-cache/repos/github.com__owner__repo",
  "test_filter": "tests/test_service.py::test_parse_user_invalid",
  "timeout_seconds": 10,
  "max_output_bytes": 12000,
  "job_id": "optional-wayfinder-job-id",
  "run_owner": "optional-user-id"
}
```

Allowed frameworks: `pytest`, `jest`.

Allowed tools:

- `run_single_test`
- `run_pytest`
- `run_jest`

`job_id` and `run_owner` are metadata for auditability. They are not used for
authorization by the worker.

## Response Contract

```json
{
  "test_ref": "test-0",
  "status": "passed",
  "output": "1 passed in 0.03s",
  "passed": 1,
  "failed": 0,
  "skipped": 0,
  "failures": [],
  "cleanup_done": true,
  "denied_reason": null
}
```

Statuses map back to Wayfinder verifier labels:

- `passed` -> claim `verified`
- `failed` -> claim `contradicted` when the failing test matches the selected
  target, otherwise `unverified`
- `timed_out` -> `unverified(validation_timed_out)`
- `tool_error` / `malformed` -> `unverified(sandbox_tool_error)`

## Command Policy

The worker denies a request before execution when:

- `path` is not under an allowed repo-cache root.
- `path` does not exist or is not a directory.
- `test_filter` contains shell metacharacters, newlines, null bytes, or path
  traversal.
- `test_filter` includes package install, fetch, shell, or destructive command
  tokens such as `pip install`, `npm install`, `uv add`, `curl`, `wget`, `bash`,
  `sh`, or `rm -rf`.
- tool/framework pairing is inconsistent.
- timeout or output limits exceed configured caps.

Execution uses `subprocess.run(..., shell=False)` with a fixed command template:

- pytest: `python -m pytest <target> -q`
- jest: `npm test -- --runInBand <target>`

The worker never executes arbitrary shell strings.

## Isolation Limits

This is a bounded worker, not a perfect security sandbox. It provides process
separation from the API, secret separation, command allowlisting, timeout,
output cap, and deterministic cleanup. Production hardening can later add
container CPU/memory limits, read-only root filesystem, seccomp/AppArmor, and
network isolation at the platform layer.

## Failure Cases

- Worker not configured: Settings and Run briefing show `disabled`.
- Worker URL missing or unhealthy: show `unavailable`; runtime claims stay
  unverified.
- Unsafe request: worker returns `tool_error` with a denied reason.
- Test timeout: worker kills the process and returns `timed_out`.
- Huge output: worker truncates output and marks the observation bounded.
- Cleanup failure: response keeps `cleanup_done=false`, and the API treats the
  observation as untrusted evidence.

## Tests

Backend tests cover:

- health endpoint.
- successful pytest observation on a tiny fixture repo.
- failing pytest observation.
- timeout handling.
- denied shell/package-install filters.
- path outside allowed roots.
- output truncation and cleanup.
- runtime policy: `sandboxed_mcp` only returns a remote runner when URL health
  succeeds.
- API settings surface: sandbox status changes from unavailable to enabled.

## Railway And Local Deployment

Local Compose adds a separate `sandbox-worker` service using the same package
image but a different command:

```bash
uvicorn wayfinder.sandbox.worker:app --host 0.0.0.0 --port 8110
```

The API and worker share only a repo-cache volume. The API owns SQLite history
under `/data`; the worker does not mount `/data`.

Railway should deploy the worker as a separate service with:

```env
RAILWAY_DOCKERFILE_PATH=Dockerfile.sandbox
WAYFINDER_SANDBOX_ALLOWED_ROOTS=/repo-cache/repos
WAYFINDER_SANDBOX_TOKEN=<optional-shared-token>
```

The API service should add:

```env
WAYFINDER_VERIFIER_RUNNER=sandboxed_mcp
WAYFINDER_TEST_SANDBOX_URL=<sandbox-worker-url>
WAYFINDER_TEST_SANDBOX_TOKEN=<same-optional-token>
WAYFINDER_GITHUB_CACHE_ROOT=/repo-cache/repos
```

Do not set `WAYFINDER_VERIFIER_RUNNER=sandboxed_mcp` until the worker service is
healthy.

## Interview Explanation

Commit 20 is the line between "grounded static evidence" and "safe executable
evidence." I kept the public API from running repository code, added a separate
worker with a narrow request schema and command allowlist, and made the UI report
whether executable verification is truly enabled. If the worker is missing,
Wayfinder still works as a grounded LLM copilot, but runtime claims remain
unverified instead of being overstated.
