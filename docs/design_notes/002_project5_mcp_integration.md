# 002 — Project 5 MCP Integration

## Problem

This module solves the problem of connecting Wayfinder to the real Project 5 MCP
servers that inspect repositories and provide grounded facts.

If this step is not finished, the agent cannot answer repo-understanding
questions based on facts provided by `mcp-repo-mapper`, `mcp-ast-explorer`, and
`mcp-test-runner`. Wayfinder would still have an adapter shape, but it would not
yet prove that the product can use real MCP tools as its grounding layer.

## Input

The main inputs are:

- `repo_path`: the local repository path that the MCP tools should inspect.
- Project 5 MCP server configs, built from `build_project5_mcp_configs()`.
- the specific tool name Wayfinder wants to call.
- the arguments required by that tool.

The module needs to know which Project 5 tool should be used for each integration
check and what arguments that tool requires. For example, repo mapping tools need
a repository path, AST tools need a repository path plus a symbol, and test
runner tools need a repository path plus test command or filter details.

## Output

On success, the integration returns the existing standardized adapter result:

- `MCPToolCallResult`

On failure, it should use the same structured failure path from the MCP
reliability layer:

- `MCPToolCallError`

This integration should not invent a new output shape. Real Project 5 MCP calls
should behave like the fake-tool adapter tests: successful calls return
`MCPToolCallResult`; failed calls raise `MCPToolCallError` with a structured
`MCPToolError`.

## Rules

Integration rules:

- Ordinary unit tests should not depend on real Project 5 MCP packages being
  installed locally.
- Real MCP integration tests should be isolated from unit tests, either with a
  marker, skip condition, or dedicated test file.
- Real MCP integration tests should only run when explicitly enabled, so normal
  `pytest` stays fast and does not depend on local Project 5 commands even if
  they happen to be installed.
- The first version should not call every primary tool from every server.
- The first version only needs one happy-path tool call per Project 5 MCP server.
- If the local environment does not have the MCP package / command installed,
  the real integration test should skip instead of failing ordinary development
  checks.

## Failure Cases

The integration should handle or test these failure cases:

- Project 5 MCP command is not installed locally.
- MCP server fails during startup.
- `list_tools` fails.
- The expected Project 5 tool is missing from the server tool list.
- The happy-path tool call returns an error.
- The repository fixture path is invalid.

## Tests

Unit tests should verify the static integration contract:

- `build_project5_mcp_configs()` returns three server configs.
- Each server config has the expected name, transport, and command.
- `project5_primary_tool_names()` includes the expected primary tool names.
- Unit tests must not start a real MCP process.

Real integration tests should verify the actual Project 5 boundary:

- Start each Project 5 MCP server.
- Call `list_tools()`.
- Check that the expected tool exists.
- Call one happy-path tool per server.

If a Project 5 MCP command is missing locally, the real integration test should
skip instead of failing normal `pytest`.

Normal `pytest` should also skip real MCP integration tests unless the developer
explicitly enables them with an environment variable such as
`WAYFINDER_RUN_PROJECT5_MCP_INTEGRATION=1`.

The first real integration pass should call one representative tool per server:

- repo mapper: one repo scan tool.
- ast explorer: one symbol lookup tool.
- test runner: one test-running or output-parsing tool.

## Interview Explanation

I separated fake adapter tests from real MCP integration tests because they prove
different things. Fake adapter tests prove Wayfinder's retry/error logic is
correct in isolation. Real MCP integration tests prove Wayfinder can actually
start the Project 5 servers, discover their tools, and call them against a
repository.

## Things I Am Unsure About

No uncertainty for now.
