# 008 — Reflection Loop + Resilience Layer

## Status

Commit 6 kickoff/design completed on 2026-06-04. The key decision is not to
reopen Commit 3. The items deferred from Commit 3 are folded into this Commit 6
resilience layer:

- oversized repo sampling and user confirmation;
- unsupported-language limitations and verifier-skipped behavior;
- AST parse/tool-failure propagation into final output.

No production code is changed by this note. The next implementation gate is a
minimal Haichuan-owned skeleton for reflection state shaping and fault-injection
tests.

## Source-Backed Constraints

- LangGraph node failures can be handled with retries, timeouts, and error
  handlers. Retries happen before error handlers;interrupts are not routed
  through retry or error handlers.
- Persistence/checkpointing is the recovery base. A graph needs a stable
  `thread_id` for resumable HITL and fault-tolerant restart.
- Loops must have explicit termination conditions. A reflection loop needs an
  internal cap, not only LangGraph's external recursion limit.
- Error handling should be typed by who can fix the problem:system retry,
  LLM-recoverable loop-back, user-fixable HITL, developer compensation, or
  unexpected bubble-up.
- Reflection should refine output from specific feedback. It must not become a
  broad second agent that invents new repo facts.
- Reflexion-style feedback is useful only when it is grounded in external or
  internally simulated failure signals. In Wayfinder, the trustworthy feedback
  signals are verifier labels, AST missing-symbol gates, routing review flags,
  ingestion guardrails, and normalized MCP/test errors.

## Commit 6 Boundary

In scope:

- Add a bounded reflection loop that rewrites final output when
  `contradicted_claims` exist or final prose conflicts with verifier labels.
- Preserve `verified`, `unverified`, and `contradicted` labels in the final
  answer after rewrite.
- Normalize the eight roadmap failure modes into deterministic state updates,
  summaries, and tests.
- Retry test timeout / sandbox-kill validation once with an upgraded timeout;
  if it still fails, mark affected claims `unverified(validation_timed_out)`.
- Add fault-injection tests for timeout, parse/tool error, routing
  hallucination, and reflection cap.
- Fold Commit 3 deferred items into Commit 6 resilience behavior without
  changing the accepted `architect_mapper` boundary.

Out of scope:

- New generated tests. `Claim.test_strategy="generate_test"` remains future
  work.
- New LLM provider/runtime prompt integration. Commit 6 can design the
  reflection input/output contract with deterministic helper functions.
- Dashboard rendering of resilience cards. API/dashboard polish belongs to
  Commit 7+.
- Changing Project 5 MCP servers.
- Broad graph topology rewrite unless implementation proves it is necessary.

## Problem

Commits 3-5 made Wayfinder grounded:architecture facts come from
`mcp-repo-mapper`, symbol facts come from `mcp-ast-explorer`, and runtime claims
can be checked through `mcp-test-runner`.

The remaining risk is not lack of evidence. It is inconsistent failure handling.
An answer can still become confusing if the final writer hides a verifier
contradiction, drops an unsupported-language limitation, treats AST parse
failure as empty evidence, or loops forever trying to repair itself.

Commit 6 adds the reliability layer that makes these outcomes deterministic and
testable. It turns failure signals into explicit state, bounded rewrites, and
visible final limitations.

## Input

The resilience layer consumes existing `WayfinderState` fields:

- `repo_handle.file_count`:detects oversized repo branches when the ingestion
  layer has counted files.
- `route_decision`:detects safe-default or human-review routing outcomes.
- `ast_index`:preserves AST evidence status such as found, missing,
  unsupported, or tool_error.
- `pending_claims`, `verified_claims`, `unverified_claims`,
  `contradicted_claims`:the verification labels that reflection must respect.
- `test_results`:test status and output summaries for timeout/malformed/failure
  analysis.
- `partial_summaries`:source summaries from `architect_mapper`,
  `entry_explainer`, and `verifier`.
- `errors`:normalized graph/tool/test failures.
- `final_output`:the draft text to be checked and possibly rewritten.
- `user_corrections`:HITL route corrections and other human feedback.

Commit 6 should avoid adding new durable state fields until tests prove they are
needed. Reflection metadata can first live in `partial_summaries["reflection"]`
and `errors`.

## Output

Commit 6 writes or updates:

- `final_output`:a rewritten answer that removes contradicted statements and
  surfaces limitations.
- `partial_summaries["reflection"]`:short summary of why a rewrite happened,
  what changed, and whether the reflection cap was reached.
- `errors`:structured errors for reflection cap, invalid route correction, AST
  parse/tool failure, validation timeout, unsupported language, and oversized
  repo sampling when relevant.
- `unverified_claims`:claims whose evidence is unavailable due to no tests,
  timeout, unsupported framework/language, skipped execution, or parse failure.
- `contradicted_claims`:claims that must not appear as true in final output.
- `next_agent`:normally `final_writer` or `None`;never an unbounded loop target.

## Reflection Loop Policy

Reflection is output repair, not evidence generation.

Trigger reflection only when at least one of these is true:

- `contradicted_claims` is non-empty.
- `final_output` contains a claim text that appears in `contradicted_claims`.
- `final_output` states or implies verification success while
  `unverified_claims` or verifier timeout/malformed-output errors exist.
- `errors` contains a failure mode that the final output does not mention.

Do not trigger reflection for:

- low-risk claims intentionally skipped by verifier;
- purely stylistic improvements;
- broad "make the answer better" requests;
- missing evidence that is already clearly stated in the final output.

The loop is capped at 2 rewrites:

1. Generate draft final output from grounded summaries.
2. Check draft against verifier labels and errors.
3. If unsafe, rewrite only the unsafe sections.
4. Re-check once.
5. If still unsafe, stop and return a partial answer with
   `reflection_cap_reached`.

The reflection step may use LLM feedback later, but the feedback input must be
limited to:

- contradicted claim texts and test refs;
- unverified claim texts and reasons;
- missing-symbol / unsupported-language / parse-error summaries;
- routing correction notes;
- the current final draft.

It must not receive permission to invent new source facts, rerun tools, or
change verification labels.

## Reflection Rewrite Rules

- A contradicted claim must be removed or restated as contradicted. It cannot be
  softened into a likely true statement.
- An unverified claim may remain only if labeled as unverified and paired with
  the reason.
- A missing symbol must stay missing. The rewrite cannot choose a nearby symbol
  unless the user explicitly corrects it.
- Unsupported language must appear as a limitation, not as a successful AST
  explanation.
- AST parse/tool failure must appear as evidence unavailable, not as no
  references/no callers.
- Test timeout after retry must appear as validation timed out.
- If the route was corrected by HITL, the final output must mention the
  corrected interpretation when useful.

## Resilience Matrix

### Failure Mode 1 — Repo >10k Files

Current base:Commit 1 already has `RepoSizePolicy`, `RepoSamplingProposal`, and
`RepoSizeAssessment`.

Commit 6 behavior:

- If `repo_handle.file_count` exceeds the policy limit, produce a sampling /
  confirmation proposal before deep scanning.
- If user approval is unavailable in the current run, continue only with a
  degraded summary that says full-repo coverage is not proven.
- Architecture and entry summaries must say whether evidence is complete or
  sampled.
- Do not let `architect_mapper` silently imply full coverage.

Test:

- A fake oversized `RepoHandle(file_count=10001)` produces a sampling limitation
  and does not claim full coverage.

### Failure Mode 2 — Unsupported Language

Current base:Commit 4 can shape unsupported AST evidence into degraded output.

Commit 6 behavior:

- Preserve language/framework hints from `mcp-repo-mapper` when available.
- Skip AST-backed entry explanation and verifier execution when the language or
  test framework is unsupported.
- Mark affected claims `unverified(unsupported_language)` or
  `unverified(unsupported_test_framework)`.
- Final output must include what was still known from repo structure and what
  could not be proven.

Test:

- Unsupported-language AST evidence reaches final output as limitation and does
  not create verified claims.

### Failure Mode 3 — AST Parse Error

Current base:Commit 4 design expects parse failures to become degraded AST
evidence;some scanner failure normalization still needs hardening.

Commit 6 behavior:

- Convert parser/tool exceptions into `ast_index.status="tool_error"` or
  equivalent normalized evidence.
- Append `errors[node=entry_explainer,error_type=ast_parse_error]` or
  `mcp_tool_error`.
- Final output must say symbol-level evidence is unavailable.
- Do not treat parse error as empty references or empty call chain.

Test:

- Fake entry scanner parse error writes structured error and degraded summary.

### Failure Mode 4 — No Tests or All Tests Fail

Current base:Commit 5 marks no safe test target as `unverified(no_test_coverage)`.

Commit 6 behavior:

- Preserve no-test coverage as unverified, not failure.
- If all selected tests fail but failure is broad/unrelated, mark
  `unverified(test_suite_failed_unrelated)`.
- If the selected target directly fails for the claim, keep `contradicted`.
- Final output must separate "not verified" from "disproved".

Test:

- Fake runner broad failure does not contradict claim unless tied to the selected
  claim test ref.

### Failure Mode 5 — Supervisor Intent Misclassification

Current base:Commit 2 has safe defaults and `needs_human_review`.

Commit 6 behavior:

- If deterministic and LLM fallback disagree, or route decision uses
  `safe_default`, mark the route as review-worthy.
- HITL correction should update `route_decision.source="user_correction"` and
  route to the corrected agent.
- Final output must not pretend the original route was confident.

Test:

- Fake route correction from architectural to behavioral resumes into
  `entry_explainer`.

### Failure Mode 6 — LLM Hallucinated Symbol

Current base:Commit 4 has the AST hard gate.

Commit 6 behavior:

- Missing symbol remains a hard stop for semantic explanation.
- Reflection cannot rewrite a missing symbol into a found one.
- If user supplies a corrected symbol, that becomes a new user correction path,
  not automatic guesswork.

Test:

- Final draft containing a missing symbol is rewritten to a missing-symbol
  limitation.

### Failure Mode 7 — Reflection Loop Infinite

Commit 6 behavior:

- Store or pass a reflection iteration count with a max of 2.
- Use explicit route conditions rather than relying only on recursion limit.
- On cap, return the best safe partial output and an error:
  `errors[node=reflection,error_type=reflection_cap_reached,retryable=False]`.

Test:

- A fake reflection checker that always rejects stops after 2 rewrites and
  returns a cap error.

### Failure Mode 8 — Test Timeout / Sandbox Kill

Current base:Commit 5 marks timeout as
`unverified(validation_timed_out)` and deferred retry policy here.

Commit 6 behavior:

- Retry a timed-out selected test once with an upgraded timeout.
- Do not retry skipped tests, unsupported frameworks, invalid modified filters,
  or malformed parser output.
- If retry passes, mark verified.
- If retry fails with direct failure, mark contradicted.
- If retry times out or sandbox-kills again, mark
  `unverified(validation_timed_out)`.

Test:

- Fake runner sequence `timed_out -> passed` becomes verified.
- Fake runner sequence `timed_out -> timed_out` becomes unverified timeout.

## Suggested Helper Boundaries

Suggested new module:

```text
src/wayfinder/graph/resilience.py
```

Suggested helper functions:

- `reflection_needed(state) -> bool`
- `build_reflection_context(state) -> dict[str, object]`
- `rewrite_final_output_with_reflection(state, max_iterations=2) -> WayfinderState`
- `apply_resilience_limitations(state) -> WayfinderState`
- `classify_failure_mode(error_or_state) -> str`
- `retry_timed_out_tests_once(state, test_runner) -> WayfinderState`

Suggested test fixtures:

- fake oversized repo handle;
- fake entry scanner parse error;
- fake unsupported-language AST result;
- fake verifier runner timeout sequence;
- fake route decision correction;
- fake reflection checker that always rejects.

## Graph Placement

Keep the production graph change small.

Preferred v1 shape:

```text
supervisor -> architect_mapper -> final_writer -> reflection_guard -> END
supervisor -> entry_explainer -> verifier -> final_writer -> reflection_guard -> END
```

If this creates too much churn, the first implementation can wrap the
`final_writer_node` with a reflection/resilience helper and leave topology
unchanged. The acceptance requirement is behavior, not a new node name.

Do not put resilience logic inside `architect_mapper`, `entry_explainer`, or
`verifier` beyond their local error normalization. Commit 6 owns cross-node
consistency after those agents produce evidence.

## Test Matrix

Required tests before closing Commit 6:

- Reflection rewrites a final draft that states a contradicted claim as true.
- Reflection preserves verified claims and labels unverified claims with reasons.
- Reflection cap stops after 2 failed repair attempts.
- Oversized repo state produces sampling limitation in final output.
- Unsupported language produces degraded output and verifier skipped behavior.
- AST parse/tool error becomes structured error and final limitation.
- No tests/no coverage stays unverified, not contradicted.
- Broad unrelated test-suite failure stays unverified.
- Direct selected test failure stays contradicted.
- Supervisor safe-default route can be corrected through HITL/user correction.
- Missing-symbol draft cannot be rewritten into a confident found-symbol answer.
- Timeout retry once can recover to verified.
- Timeout retry still timing out becomes `validation_timed_out`.

Run gates:

- focused resilience tests;
- `uv run ruff check .`;
- `uv run mypy src tests`;
- `uv run pytest -q`;
- env-gated Project 5 MCP integration only if test-runner behavior changes.

## Interview Explanation

Commit 6 is where Wayfinder turns "we have evidence" into "we fail safely."
The reflection loop is bounded and evidence-driven:it only repairs final prose
when verifier labels or normalized errors show that the draft is unsafe. It
does not invent new facts or rerun tools.

The resilience layer also closes the deferred reliability cases:oversized repos
become sampled/confirmed, unsupported languages and AST parse failures become
visible limitations, no tests become unverified rather than silently accepted,
misroutes can be corrected by HITL, hallucinated symbols stay blocked by AST
validation, reflection has a hard cap, and test timeouts retry once before
becoming `validation_timed_out`.
