# 025 — Module-source grounding for behavioural questions

> Status: design + isolated primitive + minimal wiring Cowork-implemented at
> Haichuan's explicit request ("都做了吧"). The **graph-level multi-symbol claim
> slice is deferred and Haichuan-owned** (rules 13–15). Reverse-explanation owed
> over `module_source.py` + the node wiring (rule 16).
> Goal: behavioural/architectural questions that name a *module* but no *symbol*
> reach grounded evidence instead of dead-ending at verified 0.

## Problem (diagnosed live 2026-06-22, CloakBrowser)

Questions like "what does geoip do?", "what is this repo?", "explain the
browser module" route (post note-021) `architect_mapper → entry_explainer`, but
`symbol_candidate_from_state` finds no code symbol (and it is not a CLI query),
so the node returns `entry_explainer_missing_symbol_candidate()` — no AST, no
claims, verified 0. The source is right there (`cloakbrowser/geoip.py` defines
`resolve_proxy_geo` at line 54), but nothing reads a *module body*: the entry
path only does targeted `find_definition(symbol)`. This is exactly note 021's
"Gap 2" (map NL → a *relevant* symbol).

A real user's first questions are module-level, so "verified 0 on everything I
ask" is the dominant bad impression even though precise symbol questions verify
perfectly.

## Decision

Add a deterministic **module-source fallback** that converts a module-naming
query into a real symbol, then reuses the existing AST/verifier path. No new
graph node, state channel, schema, or routing edge — the change rides the
entry_explainer slot, like note 022's extraction tiering.

`graph/module_source.py` (pure, stdlib `ast` only):
- `find_module_file(repo_path, query)` — dotted module in the query wins; else a
  bare query token matched against file stems, unambiguous (or uniquely
  shallowest) only, else None (stays honest, no guess).
- `outline_module_source(source)` — top-level functions/classes with real line
  numbers, signatures (`ast.unparse`), first-line docstrings, public flag.
- `select_symbol(definitions, tokens)` — prefer a definition whose name overlaps
  a query token, else first public function, then class.
- `module_symbol_candidate(repo_path, query)` — orchestrates the three.

Wiring: `entry.py:module_symbol_candidate_from_state` (state → repo path →
candidate); `nodes.py:build_entry_explainer_node` calls it **only after**
`symbol_candidate_from_state` returns None, before the missing-candidate dead
end. The resolved symbol then flows through `scan_symbol_for_entry` →
`entry_state_from_ast_result` → verifier unchanged, so a behavioural question
now produces the same grounded/verified evidence a symbol question does.

## Files

Production: `src/wayfinder/graph/module_source.py` (new),
`src/wayfinder/graph/entry.py` (`module_symbol_candidate_from_state` + import),
`src/wayfinder/graph/nodes.py` (2-line fallback in the entry node).
Tests: `tests/test_module_source.py` (outline / find / select / end-to-end /
state).

## Gaps / non-goals (explicit — deferred Haichuan-owned slice)

- Resolves to **one** representative symbol per module, not a full module
  outline as a multi-claim packet. A richer "module digest" claim set (every
  public symbol verified, dependency edges cited) is the deferred slice — it
  touches claim schema / verifier policy, which are Haichuan's call (rules
  13–15). The outline primitive is built so that slice can consume it directly.
- `find_module_file` does an `rglob` (capped at 5000 files, noise dirs skipped);
  a future version should reuse architect_mapper's already-built module graph in
  state instead of re-walking.
- Token→stem matching is lexical; a module whose file stem differs from its
  conceptual name (e.g. `gi.py` for "geoip") won't match.

## Step 4 — reverse-explanation prompts (Haichuan)

1. Why wire the fallback inside the entry node rather than as a new graph node?
   What would a new node have forced you to decide (schema/routing)?
2. Trace "what does geoip do?" end-to-end: which function picks `geoip.py`,
   which picks `resolve_proxy_geo`, and where does verification happen?
3. Why does `find_module_file` return None on ambiguity instead of guessing —
   how does that protect wayfinder's "honest refusal" brand?
4. What's the difference between this single-symbol fallback and the deferred
   multi-claim module digest, and why is the digest *your* call not Cowork's?
