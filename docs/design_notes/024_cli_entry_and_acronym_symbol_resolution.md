# 024 — CLI/entry resolution + acronym stop-list for symbol extraction

> Status: Cowork-implemented at Haichuan's explicit request ("都做了吧"),
> bounded enhancement of the existing `entry.py` symbol path (same slot as note
> 022, no graph/schema/routing change). Reverse-explanation owed by Haichuan
> (rule 16).
> Goal: stop two classes of live false-misses on `CloakHQ/CloakBrowser`.

## Problem (diagnosed live 2026-06-22)

Testing wayfinder against `CloakHQ/CloakBrowser` (52 real `.py` files, flat
layout), two symbol-path misses:

1. **"verify the exact CLI"** → `find_definition` was called with symbol `CLI`
   → "Symbol not found: CLI". `_looks_like_bare_code_symbol` accepts `CLI`
   because `"CLI"[1:]` ("LI") contains an uppercase letter, so it reads as
   CamelCase. Every all-caps acronym (`API`, `URL`, `HTTP`, `JSON`, …) leaks
   into `find_definition` the same way and always misses. The real CLI is
   `cloakbrowser.__main__:main` (argparse, sub-commands install/info/update),
   declared in `pyproject.toml [project.scripts]`.
2. CLI/entry-point questions that name no symbol fell back to
   `state["entry_points"][0]` (note 021's fallback), which on this repo is a
   `Dockerfile` container entry — not a Python symbol → miss.

## Decision

Two small, additive changes in `entry.py`, both Tier-2-only (an explicit
backticked/dotted symbol still wins):

- **Acronym stop-list** (`_ACRONYM_STOPWORDS`): `_looks_like_bare_code_symbol`
  returns `False` for known acronyms (CLI/API/URL/HTTP/JSON/SDK/…). They no
  longer pollute the bare-symbol candidate set, which also unblocks a *real*
  symbol that previously co-occurred with an acronym (two candidates → ambiguous
  → None; now one candidate → resolved).
- **pyproject CLI resolution**: when the query is a CLI/entry-point question
  (`_is_cli_entry_query`: word `\bclis?\b`, or phrases "entry point", "how to
  run", "console script", "executable", …), read `pyproject.toml`
  `[project.scripts]` / `[project.entry-points."console_scripts"]` and convert
  the first target `pkg.module:func` → `pkg.module.func` (note-023 AST resolver
  resolves the dotted/qualified name). This runs *before* the `entry_points[0]`
  fallback inside `symbol_candidate_from_state`.

## Files

Production: `src/wayfinder/graph/entry.py` (imports `tomllib` + `pathlib.Path`;
py3.11 stdlib, no new dep).
Tests: `tests/test_entry_explainer.py` — acronym rejection + real-symbol
unblock; `_symbol_from_script_target` / `_console_script_symbol` /
`_is_cli_entry_query` units; CLI-query → pyproject symbol end-to-end; non-CLI
query keeps the old entry-point fallback.

## Gaps / non-goals

- The pyproject path returns the first console script only; multi-CLI packages
  are not disambiguated by query.
- `_is_cli_entry_query` is keyword-based, not LLM intent. Accepts a few false
  positives (cheap: only triggers a local file read, still guarded by an
  unambiguous pyproject parse).
- The acronym list is finite; an unusual project acronym used as a real symbol
  could be suppressed on the bare path (recover by backticking it).

## Step 4 — reverse-explanation prompts (Haichuan)

1. Why is the acronym filter applied only on the Tier-2 bare path and not Tier 1?
2. `resolve_proxy_geo build the URL?` previously resolved to None — trace why,
   and why the stop-list fixes it without a new branch.
3. Why convert `module:func` to `module.func` rather than passing bare `func` —
   what does the note-023 resolver do with each?
4. What stops `_is_cli_entry_query` from firing on "explain the client"?
