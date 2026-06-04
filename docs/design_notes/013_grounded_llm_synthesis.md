# 013 — Grounded LLM Synthesis + Community Context Policy

## Problem

Commit 16 fixes a product-level gap: Wayfinder should behave like a grounded LLM
copilot, not a deterministic MCP fact panel.

Before this commit, the reader MCPs could collect real architecture and AST
facts, but the final answer was mostly deterministic string assembly. The LLM
routing fallback was also only a parser for mocked JSON, not a real model call.
Community MCPs were configured and tested, but they were not part of graph
runtime.

## Input

The synthesis layer receives bounded graph state:

- user query and repo reference;
- route decision;
- Project 5 architecture facts from `mcp-repo-mapper`;
- Project 5 AST facts from `mcp-ast-explorer`;
- verifier labels: `verified`, `unverified`, `contradicted`;
- structured graph errors / limitations;
- optional community context from Tavily or GitHub search MCP.

The LLM must not receive raw secrets or arbitrary full repository contents.

## Output

The LLM final writer returns one user-facing answer with:

- answer-first explanation;
- evidence-backed architecture and symbol details;
- explicit verification status;
- uncertainty / limitation labels;
- optional external/community context clearly marked as supporting context.

If the LLM call is unavailable, Wayfinder falls back to the existing deterministic
final writer and records an `llm_synthesis_unavailable` graph error.

## Rules

- Project 5 MCP evidence is the primary source of code truth.
- Verified AST/test claims can be stated confidently.
- Unverified runtime/data-flow claims must remain labeled unverified.
- Contradicted claims must not be restated as true.
- Tavily/GitHub MCP output is supporting community context only.
- Community context cannot override repository facts and cannot create verified
  code claims.
- Real LLM use is runtime-gated. Unit tests use fake clients and do not require
  `OPENAI_API_KEY`.
- OpenAI Responses API calls use `OPENAI_API_KEY` from process env or local
  `.env`; secrets are never committed or printed.

## Failure Cases

- Missing `OPENAI_API_KEY`: keep deterministic final writer.
- OpenAI API timeout or 4xx/5xx: keep deterministic final writer and record a
  retryable/non-retryable LLM error.
- LLM returns empty text: keep deterministic final writer.
- LLM routing returns invalid JSON or unsupported intent: use safe default route.
- Community MCP env is missing: skip community context.
- Community MCP timeout or malformed output: skip community context and keep the
  Project 5-grounded answer.
- External snippets conflict with AST/repo facts: repository facts win.

## Tests

- Routing test: ambiguous query uses injected LLM router when available.
- Routing test: invalid LLM routing output falls back to safe default.
- Final writer test: injected LLM synthesizer receives grounded packet and its
  text becomes `final_output`.
- Final writer test: LLM failure falls back to deterministic output and records
  an LLM limitation.
- Community context test: injected provider adds supporting context but does not
  create verified claims.
- Runtime test: env factory builds OpenAI clients only when explicitly enabled.
- Runtime test: local `.env` lookup can find `OPENAI_API_KEY` without printing it.

## Interview Explanation

I separate facts from synthesis. Project 5 MCPs inspect the repo and produce
ground truth about files, symbols, and tests. Community MCPs add external
discussion context, but only as context. The LLM is useful for turning those
bounded facts into a readable onboarding answer and for ambiguous intent
routing. It is not allowed to invent symbols, override verifier labels, or turn
external snippets into code facts.

