# 003 — Community MCP Integration

## Problem

This module solves the problem of adding external context to Wayfinder without
turning community MCPs into the primary source of truth.

Project 5 MCP servers remain the primary grounding layer for repository facts:
repo structure, symbols, call paths, and test results. Community MCPs should
only provide supporting context that helps explain why a repo pattern exists,
where external docs discuss a behavior, or whether related issues / PRs give
more background.

Candidate community MCP roles:

- `arxiv-mcp`: add paper or technical background for code explanations.
- `tavily-mcp`: search external docs, issues, changelogs, or web references.
- GitHub search MCP: search related GitHub issues, PRs, examples, or upstream
  repository discussions.

For Commit 1, the scope should stay at two community MCP integrations. A third
community MCP can be parked unless it is clearly needed for the core Wayfinder
demo.

Commit 1 scope decision:

- Include `tavily-mcp`.
- Include GitHub search MCP.
- Park `arxiv-mcp` for later.

## Input

The community MCP inputs should stay narrow and search-oriented.

For `tavily-mcp`:

- `query`
- optional `max_results`

For GitHub search MCP:

- repository owner / name
- `query`
- optional search type such as issue, PR, or code search

Community MCPs should not receive the full Wayfinder state as their primary
input. Wayfinder should decide what external context is needed, then send a
specific search request with a narrow scope.

## Output

On success, community MCP calls should return the existing standardized adapter
result:

- `MCPToolCallResult`

The result content should include external context, links, snippets, or search
metadata that Wayfinder can cite as supporting context.

On failure, community MCP calls should use the existing structured failure path:

- `MCPToolCallError`

Community MCP failures should not block the final answer. Wayfinder should be
able to continue with repository-grounded Project 5 facts and mark external
context as unavailable.

## Rules

Core rules:

- Project 5 MCP facts are primary.
- Community MCP results are supporting context only.
- Community MCP failure should degrade gracefully.
- Do not trust external snippets without labeling them as external context.
- Do not require API keys for normal unit tests.
- Real community MCP tests should be env-gated and skip-safe.

## Failure Cases

Failure cases:

- API key is missing.
- External service is rate limited.
- Network timeout.
- Community MCP tool is not installed.
- Search returns no useful results.
- Returned snippet conflicts with repository facts.
- GitHub repository name is invalid.
- External service returns a malformed response.

If external snippets conflict with Project 5 repository facts, repository facts
win. The external result should be treated as context to review, not as proof.

## Tests

Tests:

- Unit test: config factory declares Tavily and GitHub search MCP configs.
- Unit test: normal tests do not require API keys.
- Fake adapter test: a community tool success still returns `MCPToolCallResult`.
- Fake adapter test: a community tool failure still raises `MCPToolCallError`.
- Real integration test: env-gated.
- Real integration test: skips if command or API key is missing.
- Real integration test: one happy-path search per community MCP.

## Interview Explanation

I use Project 5 MCPs as the primary grounding layer because they inspect the
actual repository. Community MCPs are supporting tools: they add external docs,
issue, PR, or changelog context, but they do not override repo evidence. This
keeps Wayfinder useful for onboarding while still preventing web-search
hallucinations from becoming code facts.

## Things I Am Unsure About

Current uncertainties:

- Exact Tavily MCP package / command name. Resolved: official package name is
  `tavily-mcp`; local stdio command can use `npx -y tavily-mcp@latest`; primary
  search tool name is `tavily_search` based on real `list_tools()` output.
- Exact GitHub search MCP package / command name. Resolved: use GitHub's
  official `github/github-mcp-server`; local Docker command can use
  `docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN -e GITHUB_TOOLSETS
  ghcr.io/github/github-mcp-server`.
- Whether API keys are available locally. Still environment-dependent:
  `TAVILY_API_KEY` and `GITHUB_PERSONAL_ACCESS_TOKEN` should be required only
  for real integration tests, not normal unit tests.
- Whether GitHub search should use an MCP server or existing GitHub API/tooling.
  Resolved for product code: use the official GitHub MCP server so Wayfinder's
  external context path stays MCP-based. Existing GitHub API / Codex connector
  tooling can still help development, but should not become the product
  integration boundary.

Source references:

- Tavily MCP official repo: https://github.com/tavily-ai/tavily-mcp
- GitHub MCP official repo: https://github.com/github/github-mcp-server
