# 023 — AST explorer resolves bare / partially-qualified symbols (Gap 3)

> Status: designed with Haichuan (rule 14); Cowork implemented the ast-explorer
> change + the wayfinder deploy wiring per his "直接完成 Gap 3" + git-install
> deploy choice. Spans two repos: `mcp-ast-explorer` (Project 5) and `wayfinder`.
> Follows design notes 021 (routing) + 022 (symbol extraction).

## Problem (found by live re-test 2026-06-14)

After 021 + 022 shipped and were verified live, the symbol path finally received
the *correct* symbol (`merge_summaries`, `build_graph`) — but
`mcp-ast-explorer.find_definition` still returned *"Symbol not found"* for
symbols that demonstrably exist (`def merge_summaries(...)` in
`src/wayfinder/graph/state.py`; `build_graph` in `src/wayfinder/graph/app.py`).

Root cause (in `mcp-ast-explorer/src/mcp_ast_explorer/indexer.py`):
`find_definition_in_index` matched **only** on exact `qualified_name == symbol`.
`_module_name_for_path` builds module names from the relative path, so on a
src-layout repo `merge_summaries`'s `qualified_name` is
`src.wayfinder.graph.state.merge_summaries`. Therefore:

- `find_definition("merge_summaries")` — no match (needs full module path)
- `find_definition("wayfinder.graph.state.merge_summaries")` — no match (missing
  the `src.` prefix; this is also what wayfinder's `_src_layout_symbol_fallback`
  tries to patch around, and its double lookup TIMED OUT the entry_explainer node)
- only `find_definition("src.wayfinder.graph.state.merge_summaries")` matched

A symbol-lookup tool that cannot resolve a bare symbol name is the bug.

## Decision

Fix in the tool (correct layer; fixes all consumers), backward-compatible:
`find_definition_in_index` now (1) keeps exact qualified-name match as the first
and highest-priority branch (unchanged behaviour), then (2) falls back to a
dotted-boundary suffix match (`qualified_name.endswith("." + symbol)`) or leaf
`name == symbol`, resolving **only when the match is unambiguous** (one distinct
symbol). Collisions return `None` rather than guess. This makes `merge_summaries`
and `graph.state.merge_summaries` both resolve to the src-layout qualified name.

## Files

`mcp-ast-explorer` (Project 5):
- `src/mcp_ast_explorer/indexer.py` — `find_definition_in_index` two-stage match.
- `tests/test_indexer.py` — bare name, partial-qualified name, ambiguous→None,
  and the existing exact-match / missing tests stay green (18 passed locally).
- `pyproject.toml` — version `0.1.0 → 0.1.1`.

`wayfinder` (deploy wiring, git-install path chosen over a PyPI release):
- `Dockerfile.api` — install `mcp-ast-explorer @ git+...@main` instead of the
  pinned `==0.1.0`; repo-mapper stays on the published release. CI already checks
  out the ast-explorer repo, so it picks up the fix automatically.

## Deploy order

1. Push `mcp-ast-explorer` (fix + version bump) to GitHub `main`.
2. Push `wayfinder` (Dockerfile.api change).
3. Railway redeploy api (the edited RUN line busts the Docker layer cache so the
   latest ast-explorer main is fetched) + dashboard.
4. Re-test the live thread: `merge_summaries` / `build_graph` should now return
   real AST definition evidence with `verified > 0` instead of "Symbol not found".

## Gaps / non-goals

- Future ast-explorer main updates may be Docker-layer-cached on rebuild unless
  this line changes or the build runs with no cache; pin to a commit SHA if
  reproducibility matters. Cleanest long-term: publish 0.1.1 to PyPI and re-pin.
- Ambiguous bare names (same leaf in multiple modules) still return `None` by
  design; callers should pass a qualifying prefix to disambiguate.

## Step 4 — reverse-explanation prompts (Haichuan)

1. Why is exact-match kept as the first branch instead of always doing suffix
   matching?
2. Why return `None` on an ambiguous bare name rather than the first hit?
3. Why did fixing this in the tool beat fixing it in wayfinder's entry.py?
4. What's the caching risk of `git+...@main` in the Dockerfile, and the two ways
   to make the deploy reproducible?
