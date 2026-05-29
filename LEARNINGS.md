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
