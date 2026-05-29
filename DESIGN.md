# wayfinder DESIGN v0

## 1. Product Contract

`wayfinder` is a codebase onboarding workflow for engineers entering an unfamiliar repository. Its job is to answer questions about architecture, entry points, call paths, and behavior while separating verified facts from assumptions.

The primary demo target is a pinned commit of `langchain-ai/langchain`. The demo should show `wayfinder` explaining part of the ecosystem it depends on.

## 2. Architecture

`wayfinder` uses a LangGraph Supervisor coordinating three sub-agents.

| Agent | Main Tooling | Responsibility |
|---|---|---|
| `architect_mapper` | `mcp-repo-mapper` | Map repo structure, frameworks, language breakdown, dependency graph, entry points, and architecture-level evidence. |
| `entry_explainer` | `mcp-ast-explorer` | Explain key symbols, definitions, references, signatures, call chains, class relationships, and data flow from AST-backed evidence. |
| `verifier` | `mcp-test-runner` | Verify high-risk claims with minimal relevant pytest or jest targets and label claims as `verified`, `unverified`, or `contradicted`. |

Two community MCP servers can add context when useful:

- `arxiv-mcp` for research-code repositories or paper-backed projects.
- `tavily-mcp` or GitHub search MCP for external discussion, issue context, or ecosystem context.

## 3. State Schema Sketch

`WayfinderState` should contain:

- `query`: original user question.
- `repo_url`: target repository URL or local path.
- `intent`: `architectural`, `runtime`, `behavioral`, `debug`, or `mixed`.
- `repo_metadata`: cloned path, language breakdown, framework evidence, file counts, selected sampling policy.
- `module_dep_graph`: dependency graph from `architect_mapper`.
- `entry_points`: candidate entry files and scripts.
- `ast_index`: symbol index or symbol evidence from `entry_explainer`.
- `pending_claims`: claims waiting for verification.
- `verified_claims`: claims verified by tests or hard evidence.
- `unverified_claims`: claims that could not be tested or lacked coverage.
- `contradicted_claims`: claims disproved by tests or tool evidence.
- `test_results`: normalized test output keyed by test id and claim id.
- `partial_summaries`: per-agent intermediate summaries.
- `next_agent`: supervisor routing target.
- `user_corrections`: HITL inputs and route corrections.
- `final_output`: final answer or report.
- `messages`: LangGraph message history.

`Claim` should contain:

- `text`: the claim text.
- `source_agent`: which agent produced the claim.
- `risk_level`: `low`, `medium`, or `high`.
- `test_strategy`: `existing_test`, `generate_test`, or `skip`.
- `test_id`: selected test id when applicable.

## 4. Routing Model

Routing uses deterministic rules first and LLM fallback second.

Deterministic examples:

- Architecture / overview questions route to `architect_mapper`, then optionally `entry_explainer`.
- Runtime / quickstart questions route to `entry_explainer`, then `verifier` for smoke-testable claims.
- Behavior questions route to `entry_explainer`, then `verifier` for concrete behavior assertions.
- Debug questions route to `entry_explainer` plus `verifier` to reproduce or isolate failing behavior.
- Mixed questions route through the supervisor in stages and preserve intermediate summaries.

Fallback LLM routing must return structured JSON. Invalid routing JSON is rejected and recovered with a default safe route plus HITL confirmation.

## 5. Verification Strategy

Verifier runs only for high-risk claims. High-risk means the claim includes concrete function names, numeric values, runtime behavior, file paths, testable data transformations, or statements that can be checked with existing tests.

Low-risk orientation text can skip verification. Skipped claims should not be counted as verified.

Verification labels:

- `verified`: relevant test or tool evidence supports the claim.
- `unverified`: no relevant test exists, coverage is unavailable, or the user skipped test execution.
- `contradicted`: test or tool evidence disproves the claim.

When `contradicted_claims` exist, the graph runs a bounded reflection loop:

1. Generate or rewrite the explanation.
2. Verify high-risk rewritten claims.
3. Stop after a maximum of two iterations.

If the contradiction remains, the final output must say so directly.

## 6. HITL Checkpoints

HITL should protect high-risk boundaries, not interrupt every step.

Required checkpoints:

- Intent confirmation after initial routing.
- Test execution approval before verifier runs commands.
- Final verification summary before producing the polished explanation.

Pre-test approval must show:

- proposed test command or filter;
- estimated runtime if available;
- claim ids being checked;
- available actions: approve, skip, modify filter.

## 7. Resilience Modes

The v1 system must cover these failure modes.

1. Repo too large: if repo has more than 10k files, propose a sampling plan and require user confirmation.
2. Unsupported language: fall back to filename/comment heuristics and skip verifier with an explicit label.
3. AST parse error: skip the broken file, flag it, and keep processing other files.
4. No tests or all tests fail: mark claims as `unverified (no test coverage)` instead of pretending success.
5. Supervisor misclassification: allow HITL correction and resume the graph.
6. Hallucinated function or class: reject via AST validation gate before final output.
7. Reflection loop infinite: hard cap at two iterations and abort with an explanation.
8. Test timeout or sandbox kill: retry once with upgraded timeout; if still failing, mark as `validation timed out`.

Fault injection tests should cover timeout, parse error, hallucinated symbol, supervisor misroute, no tests, and reflection cap.

## 8. Runtime Surface

FastAPI endpoints:

- `POST /explain`: start a run from repo URL and question.
- `GET /status/{job_id}`: return current node, status, partial summaries, verification counts, errors, and final output if done.
- `POST /refine/{job_id}`: accept user correction or follow-up and resume from checkpoint.

State should be persisted through SQLite checkpointing so interrupted runs can resume.

## 9. Observability

LangSmith tracing should wrap every node and tool call.

Required metadata:

- `agent_name`
- `tool_name`
- `mcp_server`
- `tokens`
- `latency`
- `cost_usd`
- `claim_id`

Dashboard panels should show recent runs, trace links, per-agent latency, token usage, cost overview, routing decisions, verification stats, and failure mode frequency.

## 10. Build And Deploy Surface

Commit 0 scaffold should prepare:

- Python package for API and graph code.
- FastAPI application shell.
- LangGraph module shell.
- Next.js + shadcn dashboard shell.
- `ruff`, strict `mypy`, `pytest`, frontend lint/typecheck placeholders.
- GitHub Actions for main app checks.

Ship target:

- Docker Compose with API, three MCP servers, dashboard, and SQLite volume.
- Railway or Cloud Run deployment.
- Live URL in README.
- Three-minute recursive demo video.
- Bilingual blog post.
