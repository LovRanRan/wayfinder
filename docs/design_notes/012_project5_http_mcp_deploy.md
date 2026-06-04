# 012 — Project 5 HTTP MCP Deploy

## Problem

The public Railway demo can submit GitHub URLs and complete runs, but the API
currently uses placeholder scanner modes. The real Project 5 tools are
stdio-first MCP servers, which works well for local development but is awkward
for split-service Railway deployment.

Commit 13 adds an HTTP boundary for the two read-only Project 5 MCP servers:

- `mcp-repo-mapper`
- `mcp-ast-explorer`

`mcp-test-runner` remains disabled for public deployment until there is a
stronger sandbox/auth story.

The first deployment shape intentionally starts these HTTP MCP servers inside
the API container as localhost sidecars. Separate Railway services would not be
able to read the API container's cloned repository path without a shared
artifact or repo-URL handoff redesign.

## Inputs

- Local sidecar URL for repo mapper MCP:
  `WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL`
- Local sidecar URL for AST explorer MCP:
  `WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL`
- Sidecar opt-in:
  `WAYFINDER_START_PROJECT5_HTTP_MCP=1`
- Runtime mode switches:
  `WAYFINDER_ARCHITECTURE_SCANNER=mcp_http` and
  `WAYFINDER_ENTRY_SCANNER=mcp_http`

## Outputs

- API can create `MCPArchitectureScanner` from a Streamable HTTP MCP config.
- API can create `MCPEntryScanner` from a Streamable HTTP MCP config.
- Final output uses collected architecture / entry evidence instead of a
  placeholder final-writer fallback.
- Entry scanner can retry common `src/` layout symbols, for example resolving
  `wayfinder.graph.app.build_graph` to `src.wayfinder.graph.app.build_graph`.
- Reader MCP services can be deployed from this repo with:
  - `deploy/run_fastmcp_http.py`
  - `deploy/start_api.py`
  - `Dockerfile.api`

## Rules

- Keep stdio mode intact for local Project 5 integration tests.
- HTTP mode is opt-in through `mcp_http`; existing `placeholder` and `mcp`
  behavior must not change.
- Do not expose `mcp-test-runner` through HTTP in the public demo.
- The MCP endpoint path is `/mcp`.
- HTTP reader MCP services are stateless.
- Keep the reader MCP HTTP processes in the API container for now so cloned repo
  paths are valid for both API and MCP tools.
- Keep symbol fallback conservative:only retry dotted symbols without `:` by
  prefixing `src.` once.

## Failure Cases

- Missing repo mapper URL with `WAYFINDER_ARCHITECTURE_SCANNER=mcp_http`:
  raise a clear config error naming `WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL`.
- Missing AST explorer URL with `WAYFINDER_ENTRY_SCANNER=mcp_http`:
  raise a clear config error naming `WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL`.
- HTTP MCP service unreachable:
  preserve existing MCP adapter timeout / connection error normalization.
- API deploy without sidecars enabled:
  keep placeholder mode as the safe fallback.
- Separate Railway MCP service deployment:
  not supported by this commit because the MCP service would not share the API
  service filesystem.

## Tests

- Project 5 config tests cover Streamable HTTP config generation.
- Runtime tests cover `mcp_http` scanner construction and missing-url errors.
- Entry tests cover bare-symbol extraction, final output evidence aggregation,
  and `src.` layout fallback.
- A local smoke verified FastMCP HTTP server + `streamable_http`
  `MultiServerMCPClient` can list tools and call `health`.
- Docker / Compose smoke verified the API image starts both localhost sidecars
  and can complete GitHub URL runs through `repo_mapper` and `ast_explorer`
  evidence paths.

## Interview Explanation

I kept stdio for local development because it is the simplest way to launch MCP
servers from a client process. For Railway, I added HTTP MCP sidecars inside the
API container so the API uses the production MCP HTTP transport while still
sharing the cloned repo filesystem with the tools. I deliberately did not expose
the test runner over HTTP in the public demo because remote test execution needs
a stronger sandbox. I also removed the final placeholder aggregation, so the
dashboard shows the evidence returned by the reader MCPs as the main answer.
