# 022 — Symbol-candidate resolver: filenames are not symbols

> Status: designed with Haichuan (rule 14, symbol-extraction policy); Cowork
> implements per his "直接全部完成". Follows design note 021 (routing fan-out).
> Goal: when a query names a real symbol, feed that symbol — not a filename —
> to `find_definition`, so symbol/behaviour questions return real AST evidence.

## Problem (verified live 2026-06-13)

After 021, symbol questions reach `entry_explainer` with architect_mapper entry
points as a fallback. But the *query-derived* candidate was still wrong:

- `_EXPLICIT_SYMBOL_PATTERN` only matches dotted/colon tokens, so for
  *"What does the merge_summaries reducer do in state.py?"* it captured
  **`state.py`** (a filename) and missed **`merge_summaries`** (no dot, and not
  after a trigger word). Single candidate `state.py` →
  `find_definition("state.py")` → *"Symbol not found: state.py"*.
- `_src_layout_symbol_fallback("state.py")` then fabricated `src.state.py`,
  which also fails — a filename can never resolve as a symbol.

So even with a healthy clone + architect evidence, the symbol path was handed a
filename and produced empty/degraded evidence.

## Decision

Two changes in `entry.py`, no new MCP calls:

1. **Filenames are never symbol candidates.** A token is a filename if it
   contains `/` or ends in a known code/text suffix (`.py`, `.ts`, `.tsx`,
   `.js`, `.json`, `.toml`, `.md`, ...). Exclude such tokens from both the
   backticked and dotted extractors, and short-circuit `_src_layout_symbol_fallback`.
2. **Prefer real identifiers when no dotted/backticked symbol exists.** Tiered
   extraction:
   - Tier 1 (high confidence): backticked tokens + dotted/colon tokens
     (`app.service.create_user`, `Session.request`), filenames removed. If any
     exist, return the lone one (or `None` if ambiguous) — unchanged behaviour
     for existing explicit-symbol queries.
   - Tier 2 (only if Tier 1 is empty): scan **all** standalone identifiers and
     keep those that look like code (`snake_case` or internal CamelCase) and are
     not filenames. Return the lone one, else `None`. This catches
     `merge_summaries`, `WayfinderState`, `build_graph` regardless of position.

`_looks_like_bare_code_symbol` (existing heuristic: has `_` or an internal
uppercase) keeps plain English out, so *"behavior of routing"* still yields
`None`. Tier ordering keeps `app.service.create_user` from being polluted by its
own `create_user` fragment.

## Files

Production:
- `src/wayfinder/graph/entry.py` — add `_looks_like_filename` +
  `_BARE_IDENTIFIER_PATTERN`; rewrite `_symbol_candidate_from_query` into the two
  tiers; guard `_src_layout_symbol_fallback`; drop the now-unused
  `_BARE_SYMBOL_CONTEXT_PATTERN`.

Tests (`tests/test_entry_explainer.py`):
- real symbol beats filename (`merge_summaries` from the live failing query),
- filename-only query yields `None` (falls back to entry points),
- standalone CamelCase symbol (`WayfinderState`),
- all six existing extraction tests stay green (explicit-symbol priority,
  backtick, contextual bare, plain-language `None`, ambiguous `None`).

## Gaps / non-goals (explicit)

- A filename-only question ("explain state.py") still returns no symbol; we do
  NOT yet list a file's symbols or map a file → its module members. That's a
  larger ast/repo_mapper feature.
- A pure natural-language question with no identifier ("how does the supervisor
  route?") still falls back to `entry_points[0]`; making that *semantically*
  relevant (fuzzy symbol search over the module graph) is a separate effort.
- We do not validate the candidate against the repo before calling
  `find_definition`; a wrong guess still degrades honestly (no hallucination).

## Step 4 — reverse-explanation prompts (Haichuan)

1. Why must Tier 2 run only when Tier 1 is empty — what breaks if standalone
   identifiers are always merged in? (hint: `app.service.create_user`)
2. How does `_looks_like_bare_code_symbol` keep "routing" out but let
   "merge_summaries" through?
3. Why is excluding filenames safer than trying to convert `state.py` into a
   module symbol?
4. After this, which two question shapes still can't get a precise symbol, and
   what would each need?
