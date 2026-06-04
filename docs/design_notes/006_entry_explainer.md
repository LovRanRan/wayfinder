# 006 — Entry Explanation + AST Anti-Hallucination (`entry_explainer`)

## Problem

Commit 4 solves the semantic entry-path explanation path in Wayfinder:when a
user asks how an entry function executes, who calls it, or how data flows through
the code, `entry_explainer` must not rely on the LLM to guess function names or
call chains.

The module should use Project 5 `mcp-ast-explorer` evidence to look up real
definitions, signatures, references, call chains, and class hierarchy facts
before writing an explanation. If a requested symbol does not exist in the AST
index, the module should say that clearly and treat it as a missing-symbol /
anti-hallucination gate instead of inventing a function or class.

## Input

`entry_explainer` consumes the semantic context that is already available in
`WayfinderState`:

- the standardized repo information from `repo_handle`, including the local repo
  path that `mcp-ast-explorer` can scan.
- the original user `query`.
- the classified `intent` and `route_decision` from the Supervisor.
- `entry_points` already found by `architect_mapper`.
- any symbol, function, method, or class name that the user explicitly mentioned.

This module does not parse GitHub URLs, clone repositories, decide refs, or
invent entry points from free text. It starts from the local repo path plus
explicit or upstream-discovered symbol candidates, then asks `mcp-ast-explorer`
whether those symbols actually exist.

## Output

`entry_explainer` writes the semantic-entry-path fields that Commit 4 owns:

- `ast_index`: AST-backed symbol evidence or a compact symbol index summary from
  `mcp-ast-explorer`.
- key symbol evidence for the requested or selected entry path, including
  definitions, signatures, references, call-chain facts, and class hierarchy
  facts when relevant.
- `partial_summaries["entry_explainer"]`: a human-readable entry-path
  explanation containing call chain, definition/signature, references, key
  functions, data flow, assumptions, and source citations.
- `errors` or limitations when a symbol is missing, language support is
  unavailable, AST parsing fails, or the tool cannot provide enough evidence.
- `next_agent`: the graph routing value after the entry explanation path is
  done.

If the requested symbol does not exist or the language is unsupported, the
module should write a degraded explanation instead of a confident entry-path
answer. The degraded output should preserve what was checked, what failed, and
what cannot be proven from AST evidence.

## Rules

- Every function, class, or method name must pass an existence check through
  `mcp-ast-explorer` before it can appear as a factual symbol in the
  explanation.
- The explanation must cite AST-backed evidence from definition, signature,
  references, and call-chain tool results. Class hierarchy evidence is included
  when the question depends on inheritance or class relationships.
- LLM inference may organize the explanation, but it must not create new symbol
  facts, call-chain edges, source locations, or behavior claims that are not
  present in tool evidence.
- Missing symbols must produce a missing-symbol degraded answer instead of a
  guessed definition or fabricated call path.
- Commit 4 v1 only treats Python AST evidence as authoritative because Project 5
  `mcp-ast-explorer` v1 is Python-focused.
- Non-Python repositories, unsupported languages, and AST parse errors must be
  labeled as limitations in the output instead of being hidden behind confident
  prose.

## Real MCP Scanner Bridge Boundary

The real `mcp-ast-explorer` scanner must call `find_definition` first. This is
the symbol-existence gate:if the definition is missing, the scanner should
return missing-symbol evidence and must not continue into signatures,
references, call chains, or class hierarchy guesses.

When the definition exists, the scanner may collect semantic evidence in this
order:

1. `find_definition` for symbol existence, source location, and definition
   evidence.
2. `function_signature` for callable signature evidence.
3. `find_references` for same-module/source references.
4. `call_chain` for direct caller/callee evidence.

`class_hierarchy` is not part of the default tool sequence. It should run only
when the resolved symbol is a class or the user query asks about inheritance or
class relationships.

The scanner should return one normalized dictionary shape to
`entry_state_from_ast_result()`:

```python
{
    "symbol": symbol,
    "status": "found" | "missing" | "unsupported" | "tool_error",
    "definition": object | None,
    "signature": object | None,
    "references": list[object],
    "call_chain": list[object],
    "class_hierarchy": object | None,
    "limitations": list[str],
}
```

`status` is required. `entry_state_from_ast_result()` should use it to distinguish
normal evidence from missing-symbol, unsupported-language, and tool-error
branches instead of guessing from absent fields.

`MCPEntryScanner` should reuse the Commit 3 async bridge rule from
`MCPArchitectureScanner`. The scanner receives an adapter and internally calls
`asyncio.run(adapter.call_tool(...))` for each MCP tool call. If it is called
inside an already-active event loop, it should raise a clear `RuntimeError`
instead of nesting `asyncio.run()`.

Async/MCP details stay inside the scanner. `nodes.py` should continue to know
only the sync `EntryScanner.explain_symbol(repo_path, symbol)` contract and must
not construct MCP calls, manage event loops, or know the adapter mechanics.

Real entry scanner mode must be explicit and parallel to Commit 3 architecture
scanner selection. `WAYFINDER_ENTRY_SCANNER` controls the runtime scanner for
`entry_explainer`:

- missing or `placeholder`:use the default placeholder scanner.
- `mcp`:build a real Project 5 entry scanner with `build_project5_entry_scanner()`.
- unknown value:raise `ValueError`.

`build_project5_entry_scanner()` should select only the Project 5
`mcp-ast-explorer` config. It should not start `mcp-repo-mapper`,
`mcp-test-runner`, or community MCP servers.

Environment parsing belongs in `graph/runtime.py`, not in `nodes.py`,
`entry.py`, or `api/main.py`. The API can later call
`entry_scanner_from_env(os.environ)` and pass the returned scanner into
`build_graph(entry_scanner=...)`.

## Failure Cases

- Missing repo path:if `repo_handle` or local path is missing, the module cannot
  call `mcp-ast-explorer` and must return a degraded explanation with a
  structured error.
- No symbol candidate:if the user did not name a symbol and `entry_points` does
  not provide a usable candidate, the module should ask for or report the
  missing entry target instead of guessing one.
- Missing symbol:if `mcp-ast-explorer` cannot find the requested symbol, the
  module must return a missing-symbol / anti-hallucination degraded answer.
- Unsupported language:if the AST tool reports an unsupported language, the
  module should mark the answer as unsupported for AST-backed entry explanation.
- AST parse error:if parsing fails, the module should preserve the parse failure
  as a limitation and avoid claiming symbol-level certainty.
- MCP tool timeout or failure:if the AST tool call fails through the adapter, the
  module should preserve the normalized error and avoid inventing fallback
  symbol facts.
- Empty references or call chain:if the symbol exists but references or direct
  callers are empty, the module should say that no references/call-chain evidence
  was found rather than treating it as proof that the symbol is unused globally.
- Ambiguous symbol:if multiple same-name symbols make the target unclear, the
  module should report the ambiguity and avoid choosing one without stronger
  evidence.

## Tests

- Existing symbol:given a supported Python fixture and a real symbol, the module
  writes `ast_index`, key symbol evidence, and
  `partial_summaries["entry_explainer"]`.
- Missing symbol:given a symbol that is not present in the AST index, the module
  returns a degraded answer and does not invent a definition or call path.
- Missing local path:given state without a usable local repo path, the module
  writes a structured error and routes forward without calling AST tools.
- Unsupported language:given an unsupported language response from
  `mcp-ast-explorer`, the module writes a limitation instead of a confident
  explanation.
- Parse error:given an AST parse failure, the module records the parse error and
  avoids symbol-level certainty.
- Empty references or call chain:given an existing symbol with empty reference or
  call-chain evidence, the module says no evidence was found and does not claim
  the symbol is globally unused.
- Ambiguous symbol:given multiple plausible same-name symbols, the module reports
  ambiguity instead of choosing one automatically.
- `/explain` behavioral query:the API/graph path can route from Supervisor to
  `entry_explainer` and persist semantic evidence in `WayfinderState`.

## Interview Explanation

I designed `entry_explainer` as the symbol-grounded explanation layer in
Wayfinder. `architect_mapper` first gives the repo-level map, then
`entry_explainer` uses Project 5 `mcp-ast-explorer` to verify that concrete
functions and classes exist before explaining them.

The module uses definition, signature, references, and call-chain evidence to
produce an entry-path explanation. The LLM can organize the final prose, but it
does not own code facts. If a symbol cannot be found, the module explicitly
degrades the answer instead of inventing a function, class, or call path.
