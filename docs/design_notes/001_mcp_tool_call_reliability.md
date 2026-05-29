# 001 — MCP Tool-Call Reliability

## Problem

This module solves the problem that MCP tool calls can fail in many different
ways, such as missing tools, timeouts, connection failures, and tool runtime
errors. Wayfinder needs to standardize these failures so later graph nodes can
handle them consistently.

If this module does not exist, raw errors from different MCP tools will leak into
the graph in messy and inconsistent shapes. That would make retry decisions,
user-facing error messages, and tests harder to reason about.

## Input

The main input is a tool call request:

- `tool_name`: the MCP tool Wayfinder wants to call.
- `arguments`: the arguments passed into that MCP tool.

The module also needs reliability settings and lookup context:

- `timeout_seconds`: how long one tool attempt can run before timing out.
- `max_attempts`: how many times retryable failures can be attempted.
- available tools list from the MCP client, so the adapter can check whether
  `tool_name` exists before invoking it.

## Output

On success, the module returns the existing standardized Wayfinder result model:

- `MCPToolCallResult`

On failure, the module should raise an exception wrapper that carries a
standardized error shape instead of leaking raw third-party exceptions:

- `MCPToolError`
- `MCPToolCallError`

The error should include enough information for later graph nodes to make a
decision:

- `tool_name`: which tool failed.
- `error_type`: the normalized category of failure.
- `message`: a readable error message.
- `retryable`: whether retrying this failure makes sense.

Decision: failures should be raised through `MCPToolCallError` instead of
returned as normal `MCPToolCallResult` content. Success and failure are different
control-flow paths: success returns `MCPToolCallResult`; failure raises
`MCPToolCallError` with `error: MCPToolError`.

## Rules

Retry policy:

- `tool not found`: do not retry. The requested tool name is invalid or not
  registered, so repeating the same call will not fix it.
- `timeout`: retry. Timeout may be a temporary MCP server or process-boundary
  issue.
- `connection error`: retry. Connection failures may be temporary.
- generic `RuntimeError` / tool internal error: do not retry. With the same
  arguments, this is likely a bad input, code bug, or deterministic tool failure.
- `max_attempts`: default to 3 total attempts. This gives transient failures a
  chance to recover without making repo scans, AST parsing, or test execution
  wait too long.

Normalized v1 error types:

- `not_found`: the requested tool does not exist.
- `timeout`: a tool call exceeded the configured timeout.
- `tool_error`: all other tool failures. Connection errors are included here in
  v1 with `retryable=True`; generic runtime errors are included here with
  `retryable=False`.

## Failure Cases

Initial failure cases for this module:

- The requested tool name does not exist in the MCP client's tool list.
- The tool call times out.
- The MCP client or server has a connection error.
- The tool raises an internal runtime error.
- A retryable failure still fails after `max_attempts`.

This is the v1 failure boundary. More categories can be added later if real MCP
integration exposes additional failure modes.

## Tests

Test cases:

- When the tool name does not exist, the adapter should raise `MCPToolCallError`
  carrying a `not_found` error and should not retry.
- When a timeout happens, the adapter should retry up to 3 total attempts and
  then raise `MCPToolCallError` carrying a `timeout` error.
- When a connection error happens, the adapter should retry up to 3 total
  attempts and then raise `MCPToolCallError` carrying a retryable `tool_error`.
- When a generic `RuntimeError` happens, the adapter should call the tool only
  once and raise `MCPToolCallError` carrying a non-retryable `tool_error`.
- When the tool call succeeds, the adapter should return `MCPToolCallResult`.

## Interview Explanation

I designed this module because MCP tools are external execution boundaries and
can fail in inconsistent ways. It helps Wayfinder turn messy tool failures into
structured decisions for retry, user messages, and later graph nodes.

## Things I Am Unsure About

- Why `max_attempts` should be 3 instead of another number.
- Why generic `RuntimeError` should not be retried.
- Whether future versions should split `connection_error` out of `tool_error`.
- Whether graph nodes should catch `MCPToolCallError` directly or wrap it again
  in a higher-level node error.
