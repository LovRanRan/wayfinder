# 005 — Architecture Path End-to-End (`architect_mapper`)

## Problem

Commit 3 solves the first real codebase-understanding path in Wayfinder:given a
repository and an architecture-oriented question, `architect_mapper` should help
the user understand the repository structure.

The module should focus on repo structure rather than behavioral explanation or
test-backed verification. Its job is to turn deterministic `mcp-repo-mapper`
evidence into a clear architecture overview:what the major directories/modules
are, what languages/frameworks appear, where likely entry points are, and what
dependency graph evidence is available.

## Input

`architect_mapper` consumes the repo context that is already prepared in
`WayfinderState`:

- the standardized repo information from the ingestion layer.
- the original user `query` and classified `intent`.
- a local repository path that `mcp-repo-mapper` can scan.

This module does not parse GitHub URLs, clone repositories, decide refs, manage
cache keys, or re-run repo size counting. Those responsibilities belong to the
Commit 1 ingestion layer. `architect_mapper` starts after the repo is already
available as a local path.

## Output

`architect_mapper` writes only the architecture-path fields that Commit 3 owns:

- `repo_metadata`: repository-level facts such as root path, language breakdown,
  detected frameworks, file counts, and evidence needed for the architecture
  overview.
- `module_dep_graph`: the dependency graph returned by `mcp-repo-mapper`, kept as
  structured data for later agents.
- `entry_points`: likely entry point candidates returned by `mcp-repo-mapper`.
- `partial_summaries["architect_mapper"]`: a human-readable architecture
  summary containing structure, evidence, confidence labels, and limitations.
- `errors`: only when a tool call or supported fallback path fails.
- `next_agent`: the graph routing value after the architecture path is done.

Commit 3 should not add a new state field for limitations yet. "What I cannot
prove" belongs inside `partial_summaries["architect_mapper"]` until a later
commit proves a stronger structured schema is necessary.

## Rules

- All structure facts must come from `mcp-repo-mapper`.
- The module may lightly organize tool evidence by directory, language, entry
  point, framework, and dependency edges.
- The module must not explain function behavior, call chains, or test results.
  Those belong to `entry_explainer` and `verifier`.
- The module must not write guesses as facts.
- Confidence labels are based on evidence strength:explicit entry point
  candidates, framework markers, and dependency edges produce stronger
  confidence than filename-only hints.
- Anything the module cannot prove must be written in the
  `partial_summaries["architect_mapper"]` "what I cannot prove" section.
- If the repository is not Python, the dependency graph may be empty or degraded
  because `mcp-repo-mapper` dependency graph support is currently Python-only.

## MCP Scanner Bridge Boundary

`MCPArchitectureScanner` receives only a local repository path. It calls Project
5 `repo_mapper.scan_repo` with that path and returns only a `dict[str, object]`
scan result to the architecture result-shaping layer.

The scanner owns the async bridge to `MCPAdapter.call_tool()` so async/MCP details
do not leak into `architect_mapper_node()`. The graph node should continue to
depend on the small `scan_repo(repo_path)` capability rather than adapter
construction, tool-call arguments, or event-loop mechanics.

If the MCP adapter returns non-dict content or the MCP call fails, the scanner
must convert that into an architecture-layer failure boundary instead of passing
unknown objects into `architecture_state_from_scan_result()` or inventing
architecture facts.

## Runtime Scanner Selection

`build_graph()` owns scanner selection and may receive an optional
`architecture_scanner`. By default it should keep using the placeholder scanner
so the graph remains runnable without a live MCP process.

When tests or runtime code need a different scanner, graph construction should
inject that scanner into a small `build_architect_mapper_node(scanner)` factory.
The returned node function closes over the scanner and keeps the architecture
node flow unchanged:repo path guard -> `scanner.scan_repo(repo_path)` ->
`architecture_state_from_scan_result(...)`.

Real MCP adapter construction belongs in graph/runtime wiring, not inside
`architect_mapper_node()`. The node should not know about fake vs real scanners,
stdio commands, MCP config, adapter construction, or async bridge mechanics.

## Real MCP Runtime Factory Boundary

The real Project 5 architecture scanner factory belongs in
`src/wayfinder/graph/runtime.py`. It constructs the scanner from Project 5 MCP
runtime pieces:select the `repo_mapper` config, build an MCP client, wrap it in
`MCPAdapter`, and return `MCPArchitectureScanner(adapter)`.

`architecture.py` should not directly know Project 5 config selection.
`nodes.py` should not know MCP adapter construction, stdio commands, or MCP
config. `build_graph()` should only receive an already-constructed
`ArchitectureScanner`.

For Commit 3, the runtime factory should select only the `repo_mapper` MCP
server config. It should not start `mcp-ast-explorer` or `mcp-test-runner`,
because `architect_mapper` only owns repo structure mapping.

## Real MCP Mode Activation

Real MCP mode must be explicit. By default, `/explain` and `build_graph()` should
continue to use the placeholder scanner so local development and unit tests do
not require a live Project 5 MCP process.

`WAYFINDER_ARCHITECTURE_SCANNER=mcp` is the opt-in switch for the real Project 5
`mcp-repo-mapper` scanner. Missing or `placeholder` values should return no
scanner override, allowing the graph to use its default placeholder scanner.
Unknown values should fail fast with a clear configuration error.

Environment parsing belongs in `graph/runtime.py`, not in `api/main.py`,
`build_graph()`, or graph nodes. The API should call a helper that returns either
an already-built `ArchitectureScanner` or `None`, then pass that value into
`build_graph(architecture_scanner=...)`.

## Failure Cases

- Missing repo input:if `repo_handle` or local path is missing, the node should
  write a structured `errors` entry and route to `final_writer` with a degraded
  explanation.
- MCP tool failure or timeout:if `mcp-repo-mapper` fails through the adapter, the
  node should preserve the normalized error and avoid inventing architecture
  facts.
- Oversized repository branch:if the ingestion layer has marked the repo as too
  large or sampled, the architecture summary should say that the map is based on
  sampled/guarded evidence rather than complete repo evidence.
- Unsupported language:the module may still report language breakdown,
  framework markers, and entry point candidates, but dependency graph evidence
  must be marked degraded or unavailable.
- No entry points found:the module should say that there is not enough entry
  point evidence instead of guessing one.
- AST parse warnings:Commit 3 does not call AST tools. It only leaves room to
  pass through parse warnings or mention that AST-level parsing belongs to
  Commit 4.

## Tests

- Supported Python fixture repo:the architecture path writes `repo_metadata`,
  `module_dep_graph`, `entry_points`, and `partial_summaries["architect_mapper"]`.
- MCP tool failure:the node writes `errors` and does not produce fake
  architecture facts.
- Unsupported or non-Python fixture:dependency graph evidence is marked
  degraded, while language/framework/entry point evidence is still reported when
  available.
- No-entry-point fixture:the summary explicitly says there is no strong entry
  point evidence.
- Oversized or sampled branch:the summary includes a sampling/guardrail
  limitation.
- `/explain` architectural query:the API/graph path can route from Supervisor to
  `architect_mapper` and then to `final_writer`.

## Interview Explanation

I built `architect_mapper` first because repo onboarding should start with a
repo-level map before explaining individual functions. This module only uses
deterministic `mcp-repo-mapper` evidence to write directory structure, language
breakdown, framework markers, entry points, and Python dependency graph evidence
into `WayfinderState`.

That gives later `entry_explainer` and `verifier` nodes grounded context before
they reason about file/function behavior or test-backed claims. The LLM should
not guess the repository architecture; it should compose explanations from tool
evidence and clearly label what cannot be proved.
