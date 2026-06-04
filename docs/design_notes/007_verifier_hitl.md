# 007 — Verifier + HITL Test Approval

## Status

Commit 5 verifier / HITL design completed on 2026-06-04 after reading the
project contract, official LangGraph interrupt/HITL docs, and Project 5
`mcp-test-runner` contracts. This design was completed directly by Codex at the
user's request. The original handoff point was a Haichuan-owned minimal
skeleton;the user then explicitly delegated the Commit 5 implementation to
Codex, so the verifier path was completed from this design in the same session.

## Source-Backed Constraints

- `verifier` is triggered only for high-risk claims:concrete function names,
  numeric values, runtime behavior, file paths, testable data transformations,
  or statements that can be checked with existing tests.
- Low-risk orientation text can skip verification, but skipped claims must not
  be counted as verified.
- Claim labels are `verified`, `unverified`, and `contradicted`. No test
  coverage, user-skipped execution, unsupported language, and unavailable
  coverage should become explicit `unverified` outcomes.
- `mcp-test-runner` can run bounded pytest/Jest commands, run one pytest node id
  or Jest test-name pattern, parse JSON test output, and return pytest coverage
  summary.
- Test execution returns raw command output first; verifier must normalize it
  through `parse_test_output` before turning results into claim labels.
- Pre-test HITL approval must show the proposed test command/filter, estimated
  runtime when available, claim ids being checked, and actions for approve,
  skip, or modify filter.
- LangGraph HITL should use interrupt/resume with a checkpointer and stable
  `thread_id`. The interrupt payload must be JSON-serializable.
- Code before an `interrupt()` may run again after resume. Verifier must avoid
  irreversible side effects before the pre-test approval interrupt, or make
  those steps idempotent.

## Commit 5 Boundary

In scope:

- Extract or consume high-risk code-understanding claims.
- Decide which claims need test execution.
- Build a minimal pytest/Jest test plan.
- Pause before test execution with a HITL approval payload.
- Resume with approve / skip / modify-filter decisions.
- Run selected tests through `mcp-test-runner`.
- Label claims as `verified`, `unverified`, or `contradicted`.
- Produce a compact final verification summary for `final_writer`.

Out of scope:

- Reflection rewrite loop;that belongs to Commit 6.
- Generated tests;`test_strategy="generate_test"` remains a future branch.
- Broad test discovery across arbitrary repos beyond simple existing pytest/Jest
  targets.
- Dashboard/UI rendering of the HITL card;Commit 5 only designs the backend
  payload shape.
- Changing `Claim` / `WayfinderState` schema unless implementation proves the
  current fields are insufficient.

## Problem

Commit 4 can produce grounded entry explanations from AST evidence, but it still
cannot prove runtime behavior. `entry_explainer` can say where a symbol is
defined, what signature evidence exists, and what static call-chain evidence was
returned;it should not be trusted to prove that a behavior actually passes tests.

Commit 5 adds the cross-cutting verification layer. The verifier takes concrete
high-risk statements, maps them to the smallest relevant existing test target,
asks the user before running tests, executes only approved targets, and labels
the result honestly. A useful answer can contain `unverified` claims;that is
better than pretending every plausible explanation was proven.

## Input

`verifier` consumes these fields from `WayfinderState`:

- `query`:used only for context in summaries and possible framework/test intent.
- `repo_handle`:required for local repo path;without it verifier cannot run
  `mcp-test-runner`.
- `pending_claims`:preferred input. If upstream already created claims,
  verifier should use them directly and avoid reparsing prose.
- `partial_summaries["entry_explainer"]`:fallback input for Commit 5 v1 claim
  extraction when `pending_claims` is empty.
- `ast_index`:context for symbol names, source locations, and limitations;AST
  facts themselves are not re-verified by tests unless the claim is runtime
  behavior.
- `test_results`:existing normalized results, used to avoid duplicating a test
  run when the same claim/test pair has already been checked in this run.
- HITL resume payload after `interrupt()`:the user decision for approve, skip,
  or modify filter.

The verifier does not parse GitHub URLs, clone repos, choose entry symbols, or
invent behavior. It starts from the local repo path and claim candidates already
created by previous graph steps.

## Output

`verifier` writes these fields back to `WayfinderState`:

- `pending_claims`:remaining claims that were not executed yet, normally empty
  after Commit 5 verifier finishes.
- `verified_claims`:claims supported by the approved test result.
- `unverified_claims`:claims that were skipped, lacked relevant tests, timed
  out, had malformed test output, used unsupported test framework, or could not
  be mapped safely to test evidence.
- `contradicted_claims`:claims where the selected relevant test target failed
  in a way that directly conflicts with the claim.
- `test_results`:normalized result records keyed by test ref, with
  `claim_ref` pointing to the claim index/reference that the test was meant to
  check.
- `partial_summaries["verifier"]`:short human-readable verification summary:
  counts, approved/skipped status, selected tests, and the reason for each
  unverified or contradicted claim.
- `errors`:structured errors for missing repo path, invalid modified filter,
  unsupported framework, timeout, malformed output, or test-runner failure.
- `next_agent`:normally `final_writer` after verification finishes.

## Claim Extraction Policy

Primary rule:prefer structured `pending_claims` over parsing prose. If
`pending_claims` already exists, verifier only normalizes missing fields and
applies risk policy.

Fallback rule for Commit 5 v1:if `pending_claims` is empty, extract claims only
from known `entry_explainer` summary lines that contain testable behavior. Do
not run a broad natural-language parser over arbitrary prose.

Statements that become `pending_claims`:

- Runtime behavior statements: "`function_x` returns / raises / mutates /
  validates / parses / rejects / routes / retries / times out ..."
- Data transformation statements: "input A becomes output B",
  "field X is copied into field Y", or "state key X is persisted after node Y".
- Error-path statements: "missing symbol returns degraded output",
  "unsupported language is labeled as a limitation", or "timeout becomes
  unverified".
- Test or command claims: "this path passes pytest", "test id X covers this
  behavior", or "the selected smoke test should fail/pass".
- Numeric runtime claims: counts, exit codes, status counts, retry counts, or
  timeout values when those numbers are intended to be proven by execution.
- Specific file/path behavior claims, for example "calling this API endpoint
  writes `ast_index` into state".

Statements that do not become `pending_claims`:

- Source locations, signatures, references, and direct call-chain evidence that
  already came from `mcp-ast-explorer`.
- General orientation text, architecture summaries, or interview-style prose.
- Explicit limitations such as "no references were returned" or "this cannot be
  proven from AST evidence".
- Hedges or assumptions that are not executable, such as "likely", "may",
  "appears", or "probably".
- Unsupported-language fallback descriptions unless there is an existing test
  for that fallback behavior.

Claim refs in Commit 5 v1 should be stable within a run:

```text
claim-0
claim-1
claim-2
```

The current `Claim` schema has no `id` field, so `claim_ref` lives in
`test_results` and HITL payloads for now. Do not expand the schema until the
implementation proves the ref needs to be persisted directly on `Claim`.

## Risk Policy

Verifier acts on high-risk claims only.

High risk:

- concrete runtime behavior;
- exact function/class/method behavior beyond existence;
- API/node/state mutation claims;
- numeric claims not already proven by deterministic tool output;
- command/test pass/fail claims;
- claims with an explicit `test_id`;
- claims whose wrongness would materially mislead a user trying to run or debug
  the repo.

Medium risk:

- specific but static claims already supported by AST or repo-map evidence;
- claims that are testable in theory but have no safe test target in v1.

Low risk:

- orientation text, summaries, caveats, and non-actionable explanation.

Commit 5 handling:

- `high` + safe existing test target -> propose a test and wait for HITL.
- `high` + no safe target -> move to `unverified_claims` with reason
  `no_test_coverage`.
- `medium` -> skip test execution in Commit 5 and leave out of
  `pending_claims` unless an explicit `test_id` promotes it.
- `low` -> do not create a claim;never count it as verified.

## Test Selection Rules

Use the smallest existing test target that can check the claim.

Framework selection:

- Use pytest when the repo has Python test indicators such as `pyproject.toml`,
  `pytest.ini`, `tox.ini`, `tests/`, or an explicit pytest node id.
- Use Jest when the repo has `package.json` plus Jest indicators or an explicit
  Jest test-name pattern.
- If both are plausible, prefer the framework implied by `claim.test_id`;if
  still ambiguous, mark unverified with reason `ambiguous_test_framework`.
- If neither is plausible, mark unverified with reason `no_supported_test_runner`.

Tool selection:

- `run_single_test` when `claim.test_id` is present. This is preferred because
  it limits blast radius and maps cleanly to one claim.
- `run_pytest` or `run_jest` with a narrow `test_filter` when the claim maps to
  a symbol/test-name filter but not a full test id.
- Do not run a full suite by default in Commit 5. Full-suite execution is too
  expensive and too likely to fail for unrelated reasons.
- After raw execution, call `parse_test_output(stdout, framework)` before
  labeling claims.

Default execution bounds:

- single test:timeout 10 seconds;
- filtered test:timeout 20 seconds;
- CPU/memory limits:use `mcp-test-runner` defaults unless a later resilience
  commit owns stricter sandbox policy.

Estimated runtime in HITL:

- single test:10 seconds;
- filtered test:20 seconds;
- unknown framework or missing target:do not propose execution.

## HITL Approval Shape

Pre-test approval payload must be JSON-serializable:

```python
{
    "type": "test_approval",
    "request_id": "verifier-test-approval-0",
    "summary": "Verifier wants to run 2 focused tests for 2 high-risk claims.",
    "claims": [
        {
            "claim_ref": "claim-0",
            "text": "parse_user raises ValueError for invalid input.",
            "risk_level": "high",
            "source_agent": "entry_explainer",
            "test_strategy": "existing_test",
            "test_id": "tests/test_parser.py::test_invalid_input",
        }
    ],
    "proposed_tests": [
        {
            "test_ref": "test-0",
            "claim_refs": ["claim-0"],
            "framework": "pytest",
            "tool_name": "run_single_test",
            "path": "/absolute/local/repo/path",
            "test_filter": "tests/test_parser.py::test_invalid_input",
            "timeout_seconds": 10.0,
            "estimated_runtime_seconds": 10,
        }
    ],
    "allowed_actions": ["approve", "skip", "modify_filter"],
}
```

Resume payload:

```python
{"action": "approve"}
```

```python
{"action": "skip", "reason": "I do not want to run tests now."}
```

```python
{
    "action": "modify_filter",
    "modifications": [
        {
            "test_ref": "test-0",
            "test_filter": "tests/test_parser.py::test_invalid_input_edge_case",
            "timeout_seconds": 10.0,
        }
    ],
}
```

Implementation rule:the verifier may build the test plan before `interrupt()`,
but it must not execute tests before approval. Because LangGraph resumes by
re-running the node from the interrupt point, plan construction must be
deterministic and side-effect-free.

## Verification Label Rules

`verified`:

- approved test executed successfully;
- parsed output is valid;
- the selected target passed;
- no failure was tied to the claim's test target.

`contradicted`:

- approved single/filtered test target failed;
- the failure is directly tied to the claim's selected test id/filter;
- the claim asserted behavior that the failure disproves.

`unverified`:

- user skipped execution;
- no relevant existing test target was found;
- framework was unsupported or ambiguous;
- test runner was unavailable;
- execution timed out;
- parser returned malformed or unusable output;
- broad/filtered tests failed for reasons that cannot be confidently tied to
  the claim;
- modified filter was invalid;
- claim was medium/low risk and intentionally not executed in Commit 5.

Do not silently drop a high-risk claim. If it cannot be tested, it must appear
in `unverified_claims` with a reason in the verifier summary.

## Failure Cases

- No local repo path:write `errors[node=verifier,error_type=missing_repo_path]`;
  move high-risk claims to `unverified_claims`;route to `final_writer`.
- No pending high-risk claims:write summary "no high-risk claims selected";
  route to `final_writer` with no test execution.
- No relevant tests found:move each affected claim to `unverified_claims`
  with reason `no_test_coverage`.
- Unsupported framework:mark affected claims `unverified`;write an
  `unsupported_test_framework` error if the repo clearly needs a non-pytest/Jest
  runner.
- Ambiguous pytest/Jest selection:mark affected claims `unverified`;do not guess
  a runner.
- Test command timeout:mark affected claims `unverified` with
  `validation_timed_out`. Retry policy belongs to Commit 6.
- Malformed test output:mark affected claims `unverified`;write
  `malformed_test_output` error.
- All tests fail for unrelated reasons:mark affected claims `unverified`;
  summary must say the verifier could not isolate claim-level contradiction.
- User skips execution:mark proposed claims `unverified` with
  `skipped_by_user`;no test command is run.
- User modifies filter into an invalid target:mark affected claims
  `unverified`;write `invalid_test_filter`;do not fall back to full-suite run.
- pytest/Jest dependency missing:mark affected claims `unverified` with
  `test_runner_unavailable`.

## Tests

Design the tests before implementation. Use fake runner objects by default;
real `mcp-test-runner` integration should remain env-gated.

Required unit tests:

- `extract_pending_claims_from_entry_summary` creates claims for runtime
  behavior, data transformation, error-path, command/test, numeric runtime, and
  file/path behavior statements.
- Extractor does not create claims for AST source locations, signatures,
  references, call-chain facts, limitations, or hedged assumptions.
- Risk policy routes high-risk claims to a proposed test plan.
- High-risk claim with no test target becomes `unverified(no_test_coverage)`.
- Low-risk claim does not trigger verifier and is not counted as verified.
- Existing `claim.test_id` uses `run_single_test`.
- Pytest filter claim uses `run_pytest`;Jest filter claim uses `run_jest`.
- Ambiguous or unsupported framework becomes `unverified`.
- HITL payload contains claim refs, proposed tests, estimated runtime, and
  allowed actions.
- Resume `approve` executes proposed tests and parses output.
- Resume `skip` does not execute tests and marks claims `unverified`.
- Resume `modify_filter` uses the edited filter and preserves claim refs.
- Passed test result marks claim `verified`.
- Relevant failed single/filtered test marks claim `contradicted`.
- Timeout marks claim `unverified(validation_timed_out)`.
- Malformed parser output marks claim `unverified(malformed_test_output)`.
- Missing local repo path writes a structured verifier error.

Required graph/API-facing tests for Commit 5:

- `verifier_node` routes to `final_writer` after verification state is written.
- `/explain` or graph-level behavioral path can carry `pending_claims` through
  verifier to final output when a fake verifier runner is injected.
- Checkpointer/HITL behavior is covered with a small graph test if the
  implementation uses `interrupt()` directly in the node.

Env-gated integration test:

- With `WAYFINDER_RUN_PROJECT5_MCP_INTEGRATION=1`, prove a fixture claim can
  call real `mcp-test-runner` through the adapter, run one pytest target, parse
  output, and label the claim `verified`.

## Skeleton Handoff

Suggested new module:

```text
src/wayfinder/graph/verifier.py
```

Suggested helper boundaries:

- `claim_refs_for_pending_claims(claims) -> dict[str, Claim]`
- `extract_pending_claims_from_state(state) -> list[Claim]`
- `risk_policy_for_claim(claim) -> RiskDecision`
- `build_test_plan(repo_path, claims, ast_index) -> TestPlan`
- `build_test_approval_payload(test_plan) -> dict[str, object]`
- `apply_test_approval_decision(test_plan, decision) -> TestPlan | SkipResult`
- `verification_state_from_test_results(claims, results) -> WayfinderState`

Suggested scanner/runner boundary:

```python
class TestRunner(Protocol):
    def run_test(self, request: TestRunRequest) -> TestRunObservation: ...
```

`nodes.py` should eventually expose `build_verifier_node(test_runner=None)`.
The graph node should remain thin:read state, call verifier helpers, pause for
HITL if needed, execute approved tests through the runner, return state updates.

## Interview Explanation

I designed the verifier as a cross-cutting safety layer rather than another
narrator. `architect_mapper` and `entry_explainer` collect deterministic repo
and AST facts, but runtime behavior claims are still risky, so verifier extracts
only concrete high-risk claims and maps them to the smallest existing pytest or
Jest target. Before any test command runs, the graph pauses with a HITL approval
payload showing the claims, proposed tests, and estimated runtime. Approved
tests can mark claims `verified` or `contradicted`;missing coverage, skipped
execution, timeouts, unsupported frameworks, or ambiguous failures become
`unverified`. That label is intentional:it keeps the final explanation honest
instead of treating unproven code understanding as fact.
