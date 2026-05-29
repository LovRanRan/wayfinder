# wayfinder

`wayfinder` is a multi-agent codebase onboarding copilot for engineers entering an unfamiliar GitHub repository. Given a repo and a question, it maps architecture, explains entry paths, and verifies high-risk code understanding claims with real tests.

## Problem

Most codebase explanation tools sound confident before they are grounded. They can summarize a README, name plausible modules, or describe functions, but they rarely distinguish between facts backed by code evidence, assumptions, and claims contradicted by test behavior.

`wayfinder` is built around that distinction. It treats codebase onboarding as an evidence workflow, not a narration task.

## Product Promise

For a target repo, `wayfinder` will:

- map the project structure, framework signals, dependency graph, and entry points;
- explain key call paths and symbols from AST-backed evidence;
- extract high-risk claims from generated explanations;
- run the smallest relevant pytest or jest targets when verification is useful;
- label claims as `verified`, `unverified`, or `contradicted`;
- rewrite final explanations when tests contradict earlier claims.

The primary demo target is a pinned commit of `langchain-ai/langchain`, so the launch demo can show `wayfinder` explaining part of the ecosystem it depends on.

## Architecture

`wayfinder` uses a LangGraph Supervisor coordinating three sub-agents:

- `architect_mapper`: architecture overview, using `mcp-repo-mapper`;
- `entry_explainer`: call chains and key functions, using `mcp-ast-explorer`;
- `verifier`: cross-cutting claim verification, using `mcp-test-runner`.

Two community MCP servers extend context when useful: one for research-paper context and one for external search or GitHub discussion context.

## Verification Strategy

The verifier is not a default narrator. It is triggered only for high-risk claims: concrete function names, numeric claims, runtime behavior, or statements that can be checked with existing tests.

Low-risk orientation text can remain unverified. Missing test coverage is labeled explicitly as `unverified`. Contradicted claims trigger a bounded reflection loop: generate, verify, rewrite, with a hard cap of two iterations.

## Project Lineage

Project 5 built the deterministic tool layer:

- `mcp-repo-mapper`: repo structure and architecture primitives;
- `mcp-ast-explorer`: AST-backed symbol truth;
- `mcp-test-runner`: pytest/jest execution for verification.

Project 6 turns those tools into a product workflow with Supervisor routing, HITL, persistence, tracing, API endpoints, and a dashboard.

Project 7 will evaluate whether this architecture actually improves codebase understanding and claim verification over a simpler ReAct baseline.

## Build Scope

The first shippable version will include:

- LangGraph Supervisor with `WayfinderState` and `Claim` schemas;
- five MCP integrations through `langchain-mcp-adapters`;
- FastAPI endpoints for `/explain`, `/status/{job_id}`, and `/refine/{job_id}`;
- SQLite checkpointing for resumable runs;
- HITL checkpoints for intent confirmation, pre-test approval, and final verification review;
- LangSmith tracing with agent/tool/claim metadata;
- Next.js + shadcn dashboard for runs, traces, verification stats, latency, cost, and failure modes;
- Docker Compose and a Railway or Cloud Run deployment;
- README, `DESIGN.md`, demo video, and bilingual launch post.
