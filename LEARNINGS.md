# Project 6 · `wayfinder` — LEARNINGS

> Append-only learning record for Project 6. Sources read before a commit go here immediately; mid-commit questions and debug notes go to `progress.md` Logs first, then get distilled here at commit close.

---

## Pre-build / Commit 0 — Supervisor Scope + Graph Contract

### 📚 Sources

- [x] [LangChain Academy Intro to LangGraph modules 4-6](https://academy.langchain.com/courses/intro-to-langgraph) — HITL / Memory / Subgraphs / Streaming ✅ 2026-05-26
- [x] [LangGraph Supervisor tutorial](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/) ✅ 2026-05-26
- [x] Confirm B2 TypeScript / Next.js status before dashboard implementation — compressed P6 dashboard scope reviewed with Cowork ✅ 2026-05-26

### 🧠 Concepts Internalized

- LangGraph Supervisor is useful here because P6 has multiple specialized workers, but the real design value is the routing contract and shared state, not "more agents".
- `WayfinderState` should be treated as the workflow contract:repo metadata, architecture evidence, AST evidence, claim queues, test results, HITL corrections, and final output all need typed slots.
- `Claim` is the core anti-hallucination unit. P6 should reason about claims as first-class records with source agent, risk level, test strategy, status, and optional test id.
- HITL should sit at risk boundaries:intent confirmation, pre-test approval, and final verification review. More interruption would make the tool annoying instead of safer.
- The dashboard can start from typed API responses and operational panels;P6 does not need deep frontend architecture before real run data exists.
- A `src/` layout needs package-build verification, not only pytest `pythonpath`;a scaffold is incomplete until `uv run python -c "import wayfinder"` works.

### ⚠️ Gotchas Debugged

- Pylance "FastAPI not installed" can be an interpreter mismatch even when the project venv is correct. Local `.vscode/settings.json` and `pyrightconfig.json` should point at `.venv` and `src`.
- `pytest` passing can hide packaging mistakes when `pythonpath = ["src"]` is set. Hatchling still needs `[tool.hatch.build.targets.wheel] packages = ["src/wayfinder"]`.
- Next.js can infer the wrong workspace root if an unrelated `package-lock.json` exists above the project. `outputFileTracingRoot` should be pinned in `next.config.ts`.
- ESLint should ignore `.next/**`;otherwise generated Next.js output gets linted and produces irrelevant errors.
- `npm audit fix --force` is not a safe default during scaffold because it may introduce breaking dependency churn before the product surface is stable.

### 💼 Interview Soundbites

- "I designed `wayfinder` around claim verification rather than confident code narration:high-risk statements become typed claims and can be marked verified, unverified, or contradicted."
- "The Supervisor graph coordinates specialized workers, but the deterministic MCP tools own the facts;the agents only compose and verify explanations."
- "I added HITL at the boundaries that matter:route correction, test execution approval, and final verification review."
- "Even in Commit 0 I tested packaging, API contracts, graph compilation, frontend typecheck, and dashboard build, because scaffold quality determines whether later agent work is trustworthy."

---

## Commit 1 — Repo Ingestion + 5-MCP Adapter Foundation

### 📚 Sources

- [x] [langchain-mcp-adapters PyPI package](https://pypi.org/project/langchain-mcp-adapters/) — adapter dependency and `MultiServerMCPClient` integration boundary ✅ 2026-05-28
- [x] [GitHub MCP Server](https://github.com/github/github-mcp-server) — official GitHub search MCP command/source choice ✅ 2026-05-29
- [x] [Tavily MCP Server](https://www.npmjs.com/package/tavily-mcp) — community web-search MCP package/source choice ✅ 2026-05-29
- [x] [Tenacity retrying docs](https://tenacity.readthedocs.io/) — retry/backoff implementation for MCP tool calls ✅ 2026-05-29
- [x] Project-local design notes: `docs/design_notes/001_mcp_tool_call_reliability.md`, `002_project5_mcp_integration.md`, `003_community_mcp_integration.md` ✅ 2026-05-29

### 🧠 Concepts Internalized

- Repo ingestion is an execution boundary, not just path parsing:GitHub URL normalization, pinned refs, shallow clone, cache keys, file-count guards, and cleanup planning must be explicit before agents read the repo.
- Fake adapter tests and real MCP integration tests answer different questions. Fake tests prove Wayfinder's retry/error policy in isolation;real integration tests prove server startup, tool discovery, package wiring, and payload contracts.
- `MCPServerConfig` is a runtime instruction sheet for starting or connecting to a server. It is not the server, not the tool, and not the execution logic.
- MCP tool-call reliability belongs in the adapter layer. Graph nodes should receive either a successful `MCPToolCallResult` or a structured `MCPToolCallError`, not raw subprocess/network/library exceptions.
- Adapter-owned timeout is stronger than tool-raised timeout. `asyncio.wait_for()` protects Wayfinder even when an MCP server hangs without raising its own `TimeoutError`.
- Community MCPs should support onboarding context, but they cannot override Project 5 deterministic repo facts.

### ⚠️ Gotchas Debugged

- Real MCP tests exposed packaging/source-path problems that fake tests could not catch:editable installs can fail if the source path is skipped or hidden by the interpreter environment.
- `mcp-test-runner`'s `parse_test_output` happy path expects pytest-json-report style JSON, not plain human pytest output.
- External MCP tool names can drift from guessed docs or Python identifier assumptions. Tavily's real `list_tools()` output was the source of truth.
- MCP subprocess env vars must be forwarded deliberately. Loading local `.env` in the parent process is not enough if the child server never receives the key.
- `npx` and Docker introduce real local-environment edges:npm cache location, Docker daemon availability, and GitHub token forwarding need skip-safe integration tests instead of ordinary unit-test assumptions.
- Retry policy should stay small in v1:unknown tools do not retry;timeouts and connection failures retry;generic runtime errors do not retry.

### 💼 Interview Soundbites

- "I split MCP validation into fake adapter tests and real integration tests:the first proves Wayfinder's policy, the second proves the process boundary actually works."
- "The adapter owns retry, timeout, and error normalization because MCP calls are external execution boundaries;graph nodes should not handle raw tool exceptions."
- "Project 5 MCP servers are the grounding layer for repo facts, while Tavily and GitHub MCP provide supporting external context."
- "I kept real external-service tests env-gated and skip-safe so normal development stays fast, but the project can still prove real Tavily, GitHub, and Project 5 MCP calls when credentials and commands are available."

---

## Commit 2 — Supervisor Graph + State Machine

### 📚 Sources

- [x] [LangGraph Graph API overview](https://docs.langchain.com/oss/python/langgraph/graph-api) — `StateGraph`, state schema, reducers, nodes, conditional edges, compile ✅ 2026-05-29
- [x] [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) — checkpointer, thread id, resume, state history ✅ 2026-05-29
- [x] [LangGraph Checkpointer integrations](https://docs.langchain.com/oss/python/integrations/checkpointers) — SQLite / in-memory checkpointer options ✅ 2026-05-29
- [x] [LangChain multi-agent overview](https://docs.langchain.com/oss/python/langchain/multi-agent) — multi-agent workflow and router boundary ✅ 2026-05-29
- [x] [Subagents supervisor example](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents-personal-assistant) — supervisor/subagent coordination pattern ✅ 2026-05-29
- [x] Project-local contract files: `DESIGN.md` and `progress.md` Commit 2 roadmap ✅ 2026-05-29

### 🧠 Concepts Internalized

- `WayfinderState` is the shared contract that makes the Supervisor graph coherent. Routing, partial summaries, claims, checkpoint state, and final output should all attach to this state instead of being passed around as ad hoc node-local data.
- The Supervisor node should decide the next agent from normalized state, not from scattered conditionals inside each worker. In Commit 2, `route_decision` stores the intent, source, reason, next agent, and human-review flag.
- Deterministic routing and LLM fallback are separate layers. Commit 2 owns keyword-rule routing plus a mocked LLM-output parser/validator;the real LLM call is intentionally deferred until prompt/model/runtime boundaries exist.
- Safe defaults are part of the routing contract. Ambiguous, missing, invalid, or unsupported routing output should degrade to `architect_mapper` plus `needs_human_review`, not invent a confident specialized route.
- `thread_id` is the key LangGraph uses to select a saved graph run. The checkpointer stores state;the `thread_id` tells it which run to read or write.
- SQLite checkpointing proves resumability when a fresh graph/checkpointer instance can recover state from the same SQLite file and same `thread_id`.
- `yield` inside a `@contextmanager` helper means "lend this resource to the `with` block, then resume cleanup afterward." It is useful for SQLite because the connection must always be closed.

### ⚠️ Gotchas Debugged

- `TypedDict(total=False)` keeps state fields optional, but Pylance needs key-existence assertions like `"intent" in result` before direct indexing in tests.
- A `RouteDecision` should use required keys. If it is `total=False`, Pylance correctly warns that `route_decision["intent"]` may be unsafe.
- LangGraph's builder and checkpoint types expose incomplete static typing. Keep `Any` / `cast` at the graph-builder or test-helper boundary rather than leaking Unknown types through project-owned code.
- `json.loads()` returns an untyped value to static checkers. Assign it to `object`, validate with `isinstance`, then cast to `dict[str, object]` before calling `.get()`.
- `langgraph-checkpoint-sqlite` is a separate dependency from `langgraph`;having `langgraph` installed does not provide `langgraph.checkpoint.sqlite`.
- `SqliteSaver` works at runtime but has incomplete Pylance typing. A small `_sqlite_checkpointer()` helper can hide the untyped factory and return `BaseCheckpointSaver[Any]` to the test body.
- Checkpoint tests must pass `config={"configurable": {"thread_id": ...}}`;without a thread id, persistence semantics are not being tested.
- `tmp_path / "checkpoints.sqlite"` is `pathlib.Path` path joining, not division. It gives each pytest run an isolated temporary SQLite file.

### 💼 Interview Soundbites

- "I treated the graph state as the system contract first, then made routing a state-attached decision rather than a loose control-flow branch."
- "The Supervisor graph initially uses placeholder agents, but the state, routing, and persistence contracts are already testable before real MCP-backed agent work begins."
- "For LLM fallback, I first validated the boundary:LLM output must parse into a typed route decision, and invalid output goes to a safe default with human review."
- "I tested checkpointing at two levels:in-memory isolation by `thread_id`, and SQLite persistence across fresh graph/checkpointer instances."
- "I isolated third-party LangGraph typing gaps at narrow boundaries so project-owned state, nodes, and tests remain strict under mypy and Pylance."

---

## Commit 3 — Architecture Path End-to-End (`architect_mapper`)

### 📚 Sources

- [x] [LangChain MCP docs](https://docs.langchain.com/oss/python/langchain/mcp) — `MultiServerMCPClient`, stdio transport, tool loading, and structured MCP response boundary ✅ 2026-05-30
- [x] [langchain-mcp-adapters README](https://github.com/langchain-ai/langchain-mcp-adapters) — MCP tools inside LangGraph / API-server boundary ✅ 2026-05-30
- [x] Project-local contract files: `progress.md` Commit 3 roadmap and `docs/design_notes/004_supervisor_state_machine.md` ✅ 2026-05-30
- [x] Project 5 `mcp-repo-mapper` files: `README.md`, `src/mcp_repo_mapper/models.py`, and `src/mcp_repo_mapper/server.py` ✅ 2026-05-30

### 🧠 Concepts Internalized

- `architect_mapper` should orchestrate architecture evidence, not know how MCP stdio, async calls, or Project 5 server construction works.
- `ArchitectureScanner` is the narrow seam:the graph node only needs `scan_repo(repo_path) -> dict[str, object]`, so placeholder, fake test scanners, and real MCP scanners share one contract.
- Scanner injection belongs at graph/runtime wiring time. `build_graph(architecture_scanner=...)` chooses the scanner once, then the node uses the scanner closed over by `build_architect_mapper_node()`.
- The real MCP scanner is env-gated. Default mode returns `None`, which preserves the placeholder scanner;`WAYFINDER_ARCHITECTURE_SCANNER=mcp` builds the real Project 5 `repo_mapper` scanner.
- `WayfinderState` should only persist Commit 3-owned facts:`repo_metadata`, `module_dep_graph`, `entry_points`, `partial_summaries["architect_mapper"]`, plus `errors` only when a boundary fails.

### ⚠️ Gotchas Debugged

- Pylance treats unchecked `dict` values as partially unknown. Narrowing `object` with `isinstance` before `.get()` or indexing keeps strict typing honest.
- Importing a private scanner class in tests creates `reportPrivateUsage` noise. The public production test surface is `MCPArchitectureScanner` plus the `ArchitectureScanner` protocol.
- A sync graph node cannot safely call an async MCP adapter inside an already-running event loop. The scanner owns that guard and raises a clear runtime error instead of leaking async bridge details into graph nodes.
- Runtime factory tests should prove scanner construction and graph injection without invoking a real MCP subprocess by default.
- The old roadmap line mixed Commit 3 architecture scanning with later failure-mode work. Oversized repo handling stays in ingestion/resilience, while AST parse flags belong to `entry_explainer`.

### 💼 Interview Soundbites

- "I kept the architecture node as an orchestration boundary:it reads a local repo path, asks a scanner for repo evidence, writes typed state fields, and routes forward."
- "The MCP-specific work is isolated behind `MCPArchitectureScanner`, so tests can inject fakes and production can select the real Project 5 repo mapper with an env flag."
- "The default runtime stays safe and deterministic because real MCP mode is opt-in;normal tests use placeholder or fake scanners, while integration tests are env-gated."
- "Commit 3 deliberately does not claim runtime behavior or AST-level facts. The architecture summary states what it can prove from repo structure and what it cannot prove yet."

---

## Commit 4 — Entry Explanation + AST Anti-Hallucination (`entry_explainer`)

### 📚 Sources

- [x] Project-local tracker: `progress.md` Dashboard and Commit 4 roadmap — entry explanation scope, AST evidence persistence, missing-symbol gate, parse-error flag, unsupported-language degraded answer ✅ 2026-06-02
- [x] Project 6 four-step method: `planning/codebase_onboarding_theme/project6_four_step_method.md` — Haichuan-owned design/skeleton/test boundary before production code ✅ 2026-06-02
- [x] Project 5 `mcp-ast-explorer` README: `Final_checklist_phase_projects/project5/mcp-ast-explorer/README.md` — tool contract, anti-hallucination guarantee, v1 limitations ✅ 2026-06-02
- [x] Project 5 `mcp-ast-explorer` server contract: `src/mcp_ast_explorer/server.py` — `find_definition`, `function_signature`, `find_references`, `call_chain`, `class_hierarchy` input/output/failure behavior ✅ 2026-06-02
- [x] Project 5 `mcp-ast-explorer` models: `src/mcp_ast_explorer/models.py` — definition, reference, call-chain, hierarchy, and structured not-found result shapes ✅ 2026-06-02

### 🧠 Concepts Internalized

- `entry_explainer` is a symbol-grounded explanation layer, not a naming guesser. It must validate a function/class/method through AST evidence before explaining an entry path.
- `find_definition` is the hard existence gate. If definition evidence is missing, unsupported, parse-failed, or tool-failed, Wayfinder should return degraded evidence rather than invent references or call chains.
- Empty `references` or `call_chain` means "no evidence returned by the AST tool", not "unused code". The summary must preserve that uncertainty.
- Scanner injection keeps graph nodes stable. `nodes.py` only sees `EntryScanner.explain_symbol(repo_path, symbol)`; MCP async bridge, env selection, and tool parameter details stay outside the node.
- Class hierarchy is class-gated in v1. `class_hierarchy` is useful for class relationship questions, but it should not be a default tool call for every function explanation.

### ⚠️ Gotchas Debugged

- Sync LangGraph nodes cannot safely nest an async MCP call inside an already-running event loop. The scanner owns the `asyncio.run(...)` bridge and raises clearly when an active loop exists.
- Tool failures and parse errors need a normalized AST evidence shape (`status=tool_error`) so the graph can still write errors/limitations and continue to `final_writer`.
- Query symbol extraction must reject ambiguity. If a user names two symbols, falling back to `entry_points[0]` would be another form of hallucination.
- API `/explain` needed local path ingestion for fixture runs;otherwise behavioral queries routed to `entry_explainer` but had no `repo_handle`.
- Project 5 console scripts can exist in the venv even when the backing packages are not importable. Integration tests need to skip on both missing command and missing module.
- Real Project 5 MCP calls exposed transport details that fake adapters cannot show:FastMCP responses arrive through LangChain as text JSON content wrappers, and editable `.pth` imports can be unstable under macOS hidden flags. The fix belongs in adapter/config boundaries, not graph nodes.

### 💼 Interview Soundbites

- "For entry explanations, I made `find_definition` the anti-hallucination gate:if the AST tool cannot prove the symbol exists, the agent returns a missing-symbol degraded answer instead of explaining a fake call chain."
- "The scanner collects deterministic evidence:definition, signature, references, call chain, and class hierarchy only when the symbol type calls for it. The LLM layer would only organize that evidence into prose."
- "I explicitly distinguish empty evidence from negative evidence:an empty call-chain result is not proof a function is unused."
- "The graph node stays simple because fake scanners, placeholder scanners, and real Project 5 MCP scanners all implement the same `EntryScanner` protocol."

---

## Commit 5 — Verifier + HITL Test Approval

### 📚 Sources

- [x] [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) — dynamic `interrupt()` pause/resume, `Command(resume=...)`, checkpointer/thread id requirement, JSON-serializable payload rule, and resume re-execution caveat ✅ 2026-06-04
- [x] [LangChain Human-in-the-loop middleware](https://docs.langchain.com/oss/python/langchain/human-in-the-loop) — approval policy shape, decision types (`approve` / `edit` / `reject` / `respond`), ordered decisions, and tool-call review lifecycle ✅ 2026-06-04
- [x] Project-local tracker: [`progress.md`](progress.md) Commit 5 roadmap — claim extraction, verifier risk policy, pre-test approval, final verification summary, and required test paths ✅ 2026-06-04
- [x] Project-local contract: [`DESIGN.md`](DESIGN.md) §§5-6 — verification labels, high-risk claim definition, HITL checkpoints, and pre-test approval payload requirements ✅ 2026-06-04
- [x] Project 6 four-step method: [`project6_four_step_method.md`](../../planning/codebase_onboarding_theme/project6_four_step_method.md) — Haichuan-owned Claim / verification logic and test case design boundary ✅ 2026-06-04
- [x] Project 5 `mcp-test-runner` README: [`README.md`](../project5/mcp-test-runner/README.md) — tool list, pytest/Jest execution scope, normalized result purpose, and v1 limitations ✅ 2026-06-04
- [x] Project 5 `mcp-test-runner` server contract: [`server.py`](../project5/mcp-test-runner/src/mcp_test_runner/server.py) — `run_pytest`, `run_jest`, `run_single_test`, `parse_test_output`, and `get_coverage_summary` tool signatures ✅ 2026-06-04
- [x] Project 5 `mcp-test-runner` schemas: [`schemas.py`](../project5/mcp-test-runner/src/mcp_test_runner/schemas.py) — normalized `TestRunResult`, `TestFailure`, and `CoverageSummary` shapes ✅ 2026-06-04

### 🧠 Concepts Internalized

- `verifier` is a cross-cutting safety layer, not another narrator. AST-backed source locations, signatures, references, and call-chain facts stay with `entry_explainer`;runtime behavior and testable state/API claims move into `pending_claims`.
- `unverified` is a product feature. No coverage, skipped execution, unsupported frameworks, timeouts, malformed output, and unrelated test failures should be visible to the user instead of hidden behind confident prose.
- HITL should fire only when there is an executable test plan. If no safe pytest/Jest target exists, the claim becomes `unverified(no_test_coverage)` without interrupting the user.
- LangGraph `interrupt()` belongs inside graph runtime, not direct helper calls. The verifier can build deterministic plans before the interrupt, but test execution must happen only after approve / skip / modify-filter input.
- The current `Claim` schema can stay small for Commit 5. Stable `claim-0` refs live in HITL payloads and `test_results.claim_ref`;a persistent `Claim.id` can wait until a later schema revision proves it is needed.
- Real Project 5 MCP integration is now reproducible through Project 6 dev path sources instead of relying on manually installed console scripts in `.venv`.

### ⚠️ Gotchas Debugged

- LangGraph `partial_summaries` is not deep-merged by default. The verifier must preserve existing `entry_explainer` summaries when it adds `partial_summaries["verifier"]`, or `final_writer` loses the explanation text.
- Calling a node that reaches `interrupt()` outside a LangGraph runnable context raises `RuntimeError: Called get_config outside of a runnable context`. Direct unit tests should pass an explicit approval decision or use a no-test-plan path;interrupt/resume belongs in a compiled graph test with a checkpointer.
- `uv sync --extra dev` removes manually installed Project 5 console scripts unless they are declared as dependencies. Project 6 now declares local editable Project 5 MCP packages under `[tool.uv.sources]`.
- `mcp-test-runner` v1 runs pytest with `--json-report`;Project 6's dev environment must include `pytest-json-report`, or real test execution fails before verifier logic sees a usable result.
- Real `mcp-test-runner` execution can return raw pytest stdout while normalized counts remain zero. Wayfinder treats successful exit status as enough smoke evidence for `status=passed`, while malformed/nonzero output stays unverified.
- The first Commit 5 implementation should not run a full suite by default. A claim without explicit `test_id` or safe filter becomes unverified rather than launching broad tests with unrelated failure risk.

### 💼 Interview Soundbites

- "I made verification claim-first:only concrete runtime behavior, state mutation, command/test, numeric, or error-path statements become verifier claims."
- "The verifier uses HITL as an execution gate. It shows the proposed pytest/Jest target, claim refs, and estimated runtime, then resumes with approve, skip, or modify-filter."
- "I intentionally mark missing coverage and skipped tests as `unverified` instead of treating them as failures or silently accepting the claim."
- "The real Project 5 `mcp-test-runner` is isolated behind a `TestRunner` protocol, so unit tests use fakes while env-gated integration proves the published MCP command path."

---

## Commit 6 — Reflection Loop + Resilience Layer

### 📚 Sources

- [x] [LangGraph Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance) — retry policy, timeout policy, error handlers, resume-safe failures, and `interrupt()` bypassing retry/error handlers ✅ 2026-06-04
- [x] [Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph) — error categories, retry vs loop-back vs interrupt strategy, and state-first node design ✅ 2026-06-04
- [x] [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) — checkpointer/thread semantics, pending writes, and fault-tolerant resume from super-step boundaries ✅ 2026-06-04
- [x] [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/use-graph-api) — loop termination, recursion limits, and explicit conditional edges for bounded loops ✅ 2026-06-04
- [x] [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651) — generate feedback then refine output iteratively at test time without training ✅ 2026-06-04
- [x] [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366) — turn failure feedback into verbal reflection memory for later attempts, especially coding-agent tasks ✅ 2026-06-04
- [x] Project-local tracker: [`progress.md`](progress.md) Commit 6 roadmap — reflection cap, eight failure modes, and fault-injection requirements ✅ 2026-06-04
- [x] Commit 3 deferred boundary: [`005_architect_mapper.md`](docs/design_notes/005_architect_mapper.md) — oversized repo sampling stays ingestion/resilience;AST parse warnings belong downstream, not in architecture mapping ✅ 2026-06-04
- [x] Commit 4 degraded evidence contract: [`006_entry_explainer.md`](docs/design_notes/006_entry_explainer.md) — unsupported language, parse error, missing symbol, and tool-error degraded output rules ✅ 2026-06-04
- [x] Commit 5 verifier contract: [`007_verifier_hitl.md`](docs/design_notes/007_verifier_hitl.md) — contradicted/unverified claim labels, timeout/malformed-output handling, and retry policy deferred to Commit 6 ✅ 2026-06-04

### 🧠 Concepts Internalized

- Reflection is output repair, not fact generation. It can relabel/remove contradicted prose and surface limitations, but it must not create new repo facts or change verifier labels.
- Resilience belongs at the cross-node boundary. `architect_mapper`, `entry_explainer`, and `verifier` keep local normalization;`resilience.py` checks the final draft against evidence labels and failure signals.
- "Unverified" and "contradicted" are different product states. Missing tests, unsupported language, parse errors, unrelated suite failures, and timeouts remain unverified;direct selected-test failure is contradicted.
- Timeout retry policy should be narrow. Commit 6 retries only validation timeouts once with an upgraded timeout;it does not retry invalid filters, skipped tests, unsupported frameworks, or malformed parser output.
- Route correction can start as a state contract. `user_corrections=["intent=behavioral"]` is enough to prove the Supervisor can accept HITL intent correction before the Commit 7 API/runtime UI exists.

### ⚠️ Gotchas Debugged

- The first reflection reviewer was too broad:it treated old `missing_repo_path` placeholder errors as Commit 6 resilience errors and broke existing graph-output tests. The reviewer now only enforces the explicit Commit 6 failure-mode set.
- `TypedDict` state copied through `dict(state)` needs a boundary cast when returned as `WayfinderState`;otherwise strict mypy sees `dict[str, object]`.
- Broad failing test suites should not automatically contradict a claim. A failed observation contradicts only when its failure id matches the selected test target;unrelated failures become `unverified(test_suite_failed_unrelated)`.
- The env-gated Project 5 integration failed once because `.venv` had a corrupt `beartype` install, not because of Commit 6 logic. Reinstalling `beartype` restored FastMCP server imports.

### 💼 Interview Soundbites

- "I made the reflection loop bounded and evidence-driven:it only repairs final prose when verifier labels or normalized errors show the draft is unsafe."
- "The resilience layer keeps failure modes visible to the user:oversized repos, unsupported language, AST parse errors, no tests, unrelated suite failures, misroutes, hallucinated symbols, and validation timeouts all produce explicit limitations."
- "I separated failed tests from contradictions. A direct selected-test failure can contradict a claim, but a broad unrelated suite failure only means the claim is unverified."
- "The timeout policy is conservative:retry once with a larger timeout, then mark validation timed out rather than hiding the uncertainty."

---

## Commit 7 — FastAPI Runtime + Observability

### 📚 Sources

- [x] [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) — `BackgroundTasks` as path-operation parameter, `add_task()`, response-first execution, and same-process caveat ✅ 2026-06-04
- [x] [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) — checkpointer/thread semantics, `thread_id` requirement, super-step checkpoints, pending writes, and in-memory/SQLite checkpointer boundary ✅ 2026-06-04
- [x] [LangSmith Custom instrumentation](https://docs.langchain.com/langsmith/annotate-code) — `LANGSMITH_TRACING`, `traceable`, `trace` context manager, nested trace hierarchy, and custom run id hooks ✅ 2026-06-04
- [x] [LangSmith Trace LangChain applications](https://docs.langchain.com/langsmith/trace-with-langchain) — LangChain/LangGraph tracing behavior, metadata/tags in runnable config, and tracing SDK interoperability ✅ 2026-06-04
- [x] [LangSmith Add metadata and tags to traces](https://docs.langchain.com/langsmith/add-metadata-tags) — static, invocation-time, context, and trace-level metadata patterns ✅ 2026-06-04
- [x] [LangSmith Configure threads](https://docs.langchain.com/langsmith/threads) — `thread_id` / `session_id` metadata for grouping traces and aggregating token/cost across a thread ✅ 2026-06-04
- [x] Project-local tracker: [`progress.md`](progress.md) Commit 7 roadmap — API lifecycle, `/status`, `/refine`, checkpointer resume, trace metadata, and API test requirements ✅ 2026-06-04
- [x] Current API shell: [`main.py`](src/wayfinder/api/main.py) / [`schemas.py`](src/wayfinder/api/schemas.py) — pre-Commit-7 sync API and minimal run summary contract ✅ 2026-06-04

### 🧠 Concepts Internalized

- API runtime is a job lifecycle boundary, not a graph rewrite. `/explain` creates a durable run record, queues graph work, and `/status/{job_id}` becomes the polling source of truth.
- `thread_id` has to be the same id used by API job state and LangGraph config. That keeps status, refine/resume, checkpoints, and trace grouping aligned.
- `/refine` should not only mutate visible query text. It must persist `user_corrections`, reuse the same checkpointer thread, and re-enter the graph with those corrections in state.
- Trace metadata is a product contract even when LangSmith is disabled locally. Every run still emits `agent_name`, `tool_name`, `mcp_server`, `tokens`, `latency`, `cost_usd`, and `claim_id` keys so dashboard/eval work has stable columns.
- Tool-call tracing belongs at the MCP adapter boundary. Wrapping `MCPAdapter.call_tool()` gives Project 5 and community MCP calls the same optional LangSmith tool-span path without changing individual scanner/verifier nodes.
- BackgroundTasks are acceptable for Commit 7's in-process runtime, but they are not a distributed queue. Commit 8/deploy still needs honest docs about this boundary.

### ⚠️ Gotchas Debugged

- FastAPI background responses are rendered before the task mutates state. Tests should assert POST returns `queued`, then poll `/status/{job_id}` for completed/failed state.
- `model_copy(update=...)` does not make graph state persistence automatic. The API needs a separate internal graph input store so `/refine` can reuse original repo/query state plus corrections.
- LangGraph checkpointer resume depends on `RunnableConfig.configurable.thread_id`; storing `thread_id` only inside `WayfinderState` is not enough.
- Trace metadata should be deterministic in unit tests and not require live LangSmith credentials. The API passes metadata/tags in `RunnableConfig`; LangSmith can consume it when env vars are enabled.
- The MCP tracing wrapper must be no-op unless `LANGSMITH_TRACING` is enabled. Tool failures should still flow through the existing `MCPToolCallError` normalization path.

### 💼 Interview Soundbites

- "I turned the FastAPI layer into a real job runtime:POST creates a queued run, background execution updates status, and `/status` serializes partial summaries, errors, counts, and final output."
- "Refine reuses the same `thread_id` across API state, LangGraph config, and trace metadata, so user corrections become resumable state instead of a string-only patch."
- "Observability starts as schema discipline:even local fake runs emit the same trace metadata keys the dashboard and eval harness will need later."
- "I traced MCP tools at the adapter boundary, so all Project 5 server calls share one instrumentation policy instead of duplicating tracing code inside every node."
- "I kept Commit 7 intentionally in-process with FastAPI BackgroundTasks;the production queue/deploy tradeoff is visible instead of hidden."

---

## Commit 8 — Dashboard, Deploy, And Core Ship Evidence

### 📚 Sources

- [x] [Next.js Environment Variables](https://nextjs.org/docs/app/guides/environment-variables) — runtime API base URL contract for dashboard server-side fetches ✅ 2026-06-04
- [x] [Next.js `output: "standalone"`](https://nextjs.org/docs/app/api-reference/config/next-config-js/output) — standalone dashboard Docker image packaging ✅ 2026-06-04
- [x] [Docker Compose file reference](https://docs.docker.com/reference/compose-file/) — service definitions, healthchecks, profiles, volumes, and dependency wiring ✅ 2026-06-04
- [x] [GitHub Actions workflow syntax](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions) — multi-job CI structure, defaults, and checkout paths ✅ 2026-06-04
- [x] [Google Cloud Run deploy containers](https://cloud.google.com/run/docs/deploying) — container image deploy path and public service URL workflow ✅ 2026-06-04
- [x] [Railway Dockerfile deploys](https://docs.railway.com/guides/dockerfiles) — Railway Dockerfile build contract and project-link requirement ✅ 2026-06-04
- [x] Project-local runtime note: [`009_runtime_observability.md`](docs/design_notes/009_runtime_observability.md) — `/runs`, trace metadata, and dashboard/eval schema requirements ✅ 2026-06-04
- [x] Project-local roadmap: [`progress.md`](progress.md) Commit 8 — dashboard, deploy, README, DESIGN v1, demo, blog, and ship-evidence requirements ✅ 2026-06-04

### 🧠 Concepts Internalized

- A dashboard should consume the same run contract as the API, not a parallel mock-only schema. Commit 8 added `/runs` and transformed snake_case API payloads into a dashboard model.
- Demo fallback data is useful only if it has the same shape as live API data. It keeps Docker/CI/demo inspectable while still making live API data the preferred path.
- Deploy-ready is different from deployed. Dockerfiles, Compose, Railway config, and Cloud Build config make the repo deployable;without a linked Railway or Cloud Run project, a public URL cannot be honestly marked complete.
- Project 5 MCP servers are stdio-first. Compose can document them under an explicit `mcp` profile, but API production wiring should not pretend they are HTTP sidecars.
- CI has to recreate the local sibling Project 5 layout before running `uv sync --extra dev`, because Project 6's dev dependencies point to `../project5/...`.

### ⚠️ Gotchas Debugged

- Existing dashboard `node_modules` was corrupt and npm's default cache had root-owned files. Re-running `npm ci --cache /private/tmp/wayfinder-npm-cache` rebuilt dependencies without changing global cache ownership.
- Next.js build should not require a live API. The page uses server-side fetch with no-store and falls back to seeded runs when `/runs` is unavailable or empty.
- Railway CLI reported `No linked project found`;this is an external deploy state blocker, not a repo code failure.
- GitHub Actions originally checked out only the Project 6 repo, which would break local editable Project 5 path dependencies. CI now checks out the three MCP repos into sibling paths first.
- Next dev server hit local `EMFILE` watcher limits, but production `npm run build` passed and HTTP rendering returned 200.
- Docker image builds hung at base image metadata pull and were canceled. `docker compose config` still validates the Compose contract;image build needs a working Docker registry pull path.

### 💼 Interview Soundbites

- "Commit 8 turned the project from backend-only evidence into a dashboarded product surface:recent runs, trace links, latency, cost, routing, verification stats, and failure modes."
- "I added `/runs` because a dashboard should read a real API contract, not scrape internal state or rely only on mocks."
- "I kept deploy evidence honest:the repo is Docker/Railway/Cloud Run ready, but I did not fabricate a public URL when Railway was not linked."
- "The CI job recreates the actual Project 5/6 sibling layout, so integration tests exercise the same local editable MCP boundary as development."

---

## Commit 9 — Enterprise Workflow Case Study Design

### 📚 Sources

- [x] Project-local case-study plan: [`project6_enterprise_workflow_case_study_plan.md`](project6_enterprise_workflow_case_study_plan.md) — enterprise workflow gap, permission-gated recruiting CRM scenario, policy/approval/audit/eval scope, and no-Project-11 boundary ✅ 2026-06-04
- [x] Project-local four-step workflow: [`project6_four_step_method.md`](../../planning/codebase_onboarding_theme/project6_four_step_method.md) — design-first and skeleton-before-code ownership rule for Project 6 modules ✅ 2026-06-04
- [x] Project-local architecture baseline: [`DESIGN.md`](DESIGN.md) — current Wayfinder product contract, HITL, resilience, runtime, observability, and dashboard boundaries ✅ 2026-06-04
- [x] Project-local tracker: [`progress.md`](progress.md) Commit 9 roadmap — design note, state fields, policy table, approval/audit schema, and eval contract ✅ 2026-06-04

### 🧠 Concepts Internalized

- The enterprise case study should extend Wayfinder's story, not become a separate recruiting product. It exists to prove permissioned business workflow design on top of the same agent architecture.
- Tool policy must be separated from model generation. The model can propose actions, but a deterministic policy layer decides allow / low-risk-only / approval-required / deny.
- Audit logs are the evidence layer for enterprise agents. The final report should point to audit event ids and approval task ids instead of making unsupported workflow claims.
- Synthetic eval data is acceptable only if the benchmark is repeatable and the numbers are generated from committed inputs. Commit 9 defines the eval contract but does not publish fake results.
- Existing `src/wayfinder` package conventions should override the draft plan's `app/` path. Future implementation belongs under `src/wayfinder/enterprise`.

### ⚠️ Gotchas Debugged

- The source plan included implementation tasks A-G, but Commit 9 is intentionally only a design/skeleton contract. Creating graph/tool/schema/example/test files now would violate the post-mainline ownership boundary.
- A recruiting CRM demo can easily look like a separate product. The design note keeps it as a case study inside Wayfinder and bans real Gmail, Salesforce, login, external CRM, or a new dashboard.
- `allow_if_low_risk` needs a prior risk check. It is not equivalent to `allow`, and high-risk CRM updates must become approval tasks rather than quiet mutations.
- Resume wording should not add a new project title. The case study becomes one Wayfinder bullet about permission-gated workflow execution, approval queues, audit logs, blocking, and evals.

### 💼 Interview Soundbites

- "I added an enterprise workflow case study to show Wayfinder's architecture generalizes beyond codebase onboarding without turning it into a separate product."
- "The model proposes actions, but policy controls execution:read and draft actions can be automatic, while email sends, referral requests, and risky CRM mutations require approval or are blocked."
- "Every node/tool decision writes an audit event, so the final report is backed by operational evidence instead of free-form narration."
- "The eval contract measures workflow safety:approval-routing accuracy, unsafe-action blocking, cost per candidate, latency, and human intervention rate."

---

## Commit 10 — Enterprise Workflow Case Study MVP + Docs

### 📚 Sources

- [x] Project-local design note: [`011_enterprise_workflow_case_study.md`](docs/design_notes/011_enterprise_workflow_case_study.md) — implementation boundary, state schema, policy table, approval/audit schemas, failure handling, eval contract, and no-real-CRM constraints ✅ 2026-06-04
- [x] Project-local tracker: [`progress.md`](progress.md) Commit 10 roadmap — mock CRM/email/policy store, approval queue, audit log, example runner, tests, case-study docs, and README/resume integration scope ✅ 2026-06-04
- [x] Project-local architecture baseline: [`DESIGN.md`](DESIGN.md) — Wayfinder's HITL, verifier, observability, dashboard, and failure-mode principles to reuse in the enterprise case study ✅ 2026-06-04
- [x] Project-local case-study plan: [`project6_enterprise_workflow_case_study_plan.md`](project6_enterprise_workflow_case_study_plan.md) — original enterprise workflow gap analysis and Permission-Gated Recruiting CRM Agent demo shape ✅ 2026-06-04

### 🧠 Concepts Internalized

- Enterprise workflow realism can be proven without real external integrations. The MVP uses synthetic local data, deterministic mock tools, approval tasks, and audit events to show the safety boundary.
- Policy should be deterministic and separate from graph narration. `allow_if_low_risk` depends on a prior risk check; `requires_approval` creates a task; `deny` blocks and writes an audit event.
- Audit events are not optional logs. They are the evidence artifact that lets a final report explain why an action executed, waited for approval, or was blocked.
- A reproducible demo needs fixed inputs and fixed sample timestamps. The example runner now generates stable sample audit / approval / report artifacts from committed JSON.
- Eval docs should distinguish smoke evidence from aggregate benchmark numbers. Commit 10 documents pending metrics instead of inventing results.

### ⚠️ Gotchas Debugged

- Running `uv run python examples/enterprise_workflow/recruiting_crm_demo.py` initially could not import `wayfinder` because scripts run with the example directory on `sys.path`;the runner now inserts repo `src/` explicitly for local demo use.
- The first sample artifacts used wall-clock timestamps, which made outputs non-reproducible. `run_enterprise_workflow()` now accepts `created_at` so the committed demo uses a fixed timestamp.
- The workflow must not treat `send_email` as just another high-risk action. It always creates an approval task and never executes in the mock CRM step.
- The `invent_contact` path is deliberately denied. Missing contacts should be blocked, not silently converted into fake CRM data.

### 💼 Interview Soundbites

- "I extended Wayfinder with a local enterprise workflow case study:50 synthetic candidates,20 jobs,20 contacts,policy-gated mock tools,approval tasks,and audit logs."
- "The model can draft and propose actions, but deterministic policy decides whether an action runs, waits for approval, or is blocked."
- "Every node/tool decision writes an audit event, so the final report is backed by operational evidence rather than free-form agent narration."
- "I documented eval metrics separately from results;the MVP has smoke evidence and focused tests, but no fake benchmark numbers."

---

## Commit 11 — Frontend Launch Hardening

### 📚 Sources

- [x] Project-local dashboard page: [`dashboard/app/page.tsx`](dashboard/app/page.tsx) — existing server-rendered dashboard, stale header badge, trace buttons, current-run card, and live/demo data badges ✅ 2026-06-04
- [x] Project-local API client: [`dashboard/lib/api.ts`](dashboard/lib/api.ts) — dashboard server fetch path, demo fallback behavior, and API URL environment boundary ✅ 2026-06-04
- [x] Project-local table component: [`dashboard/components/run-status-table.tsx`](dashboard/components/run-status-table.tsx) — trace link rendering and demo-mode sample state ✅ 2026-06-04
- [x] FastAPI runtime contract: [`src/wayfinder/api/main.py`](src/wayfinder/api/main.py) / [`src/wayfinder/api/schemas.py`](src/wayfinder/api/schemas.py) — `/explain`, `/status/{job_id}`, `/refine/{job_id}`, and `RunSummary` response shape ✅ 2026-06-04
- [x] Deploy notes: [`docs/deploy/README.md`](docs/deploy/README.md) — Railway dashboard/API env setup and public/internal URL split ✅ 2026-06-04
- [x] Project-local README: [`README.md`](README.md) — dashboard/API quickstart, dashboard panels, and launch evidence wording ✅ 2026-06-04

### 🧠 Concepts Internalized

- A launch dashboard needs an action path, not only an observability path. Recent runs and metrics prove monitoring, but a recruiter/product reviewer needs a first-click way to submit a run.
- For split services, the API URL has two audiences. `WAYFINDER_API_BASE_URL` is for dashboard server-to-API fetches;`NEXT_PUBLIC_WAYFINDER_API_BASE_URL` is for browser-visible docs/links.
- Browser actions should go through dashboard-owned proxy routes when the API may be internal, protected by service networking, or missing CORS headers.
- Demo data is acceptable only when it is labeled and does not expose fake external links as if they were real traces.
- The frontend should preserve the same `RunSummary` contract as the backend. The launcher converts API snake_case payloads through the same `toDashboardRun()` mapper as the dashboard list.

### ⚠️ Gotchas Debugged

- `npm run build` initially failed because local `node_modules` contained duplicate/corrupt package folders such as `fdir 2` and `@types/estree 2`. Re-running `npm ci --cache /private/tmp/wayfinder-npm-cache` rebuilt a clean dependency tree.
- The dashboard package had no production `start` script. Commit 11 adds `npm run start` for the same standalone server path used by the Docker image.
- A GitHub URL run can pass through the frontend proxy but still return `missing_repo_path` from the backend if API ingestion has not materialized the repo into a local handle. The launcher default now uses `repo_url="."` so local/container demos hit the working local-path contract.
- Route handlers should keep backend errors visible. The proxy returns the FastAPI JSON payload and status code instead of hiding 404/409/422 details behind a generic frontend error.

### 💼 Interview Soundbites

- "I converted the dashboard from read-only observability into a launchable product surface:submit a run, poll status, refresh, and refine from the UI."
- "The frontend talks to the backend through Next route proxies, so Railway can keep the API on an internal service URL while browser links still point to the public API docs."
- "I kept demo fallback honest:demo rows are labeled and sample LangSmith URLs no longer appear as real traces."
- "The launcher reuses the backend `RunSummary` contract and the dashboard's existing mapping layer, so interactive runs and recent-run metrics stay schema-aligned."
