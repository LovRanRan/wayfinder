# 021 — Grounding fan-out fix: symbol questions get architect_mapper first

> Status: designed with Haichuan (guided-design, rule 14 routing ownership);
> Cowork implements the local code per his decision "全部前置 cartographer".
> Goal: stop wayfinder returning empty evidence on symbol/behavioural questions
> against its own (and any) repo.

## Problem (diagnosed live 2026-06-13)

Pointing wayfinder at `LovRanRan/wayfinder` and asking a symbol/behaviour
question ("how does the supervisor route between workers?", "what does
merge_summaries do?") returned an **empty evidence packet** → an honest refusal
with verified 0. Reading the authenticated run records
(`/api/wayfinder/threads/{id}` via the dashboard) showed the clone and
`architect_mapper` are healthy (74 Python files, full module graph, no errors).
The failure is upstream of the LLM, in routing:

- `entry_explainer` summary: *"I cannot inspect AST evidence because no symbol
  candidate was available from the user query or architect_mapper entry points."*
- `entry.py:symbol_candidate_from_state` takes a symbol from the query, else
  falls back to `state["entry_points"][0]` (produced by architect_mapper).
- But for `runtime/behavioral/debug` intents the supervisor routed to
  `entry_explainer` **alone** — architect_mapper never ran, so `entry_points`
  was empty; and a behaviour question carries no bare symbol → candidate `None`
  → `entry_explainer_missing_symbol_candidate()` → empty packet.

So the symbol path was starved of its fallback candidate.

## Decision

Make every non-architectural grounding question run **architect_mapper → then
entry_explainer**, reusing the existing `mixed` graph path (zero new edges).
After architect_mapper runs, `entry_points` is populated, so even a
symbol-less behaviour question has a fallback candidate.

This requires two coordinated routing changes (both Haichuan-owned territory),
because the supervisor runs `next_agent` first and only then drains
`pending_workers`:

1. `routing.py:choose_next_agent` — `runtime/behavioral/debug` now return
   `architect_mapper` (was `entry_explainer`). This closes the existing
   `# TODO: Decide whether runtime should route to entry_explainer or
   architect_mapper`. So architect_mapper is the supervisor's first hop.
2. `planning.py:plan_workers_for_intent` — `runtime/behavioral/debug` now fan
   out `(repo_cartographer, symbol_investigator)` (was investigator-only), so
   `entry_explainer` is queued as a pending worker and `route_after_architect`
   continues to it after architect_mapper.

Resulting path (identical to today's working `mixed` path):
`supervisor → architect_mapper → entry_explainer → verifier → final_writer`.

## Files

Production:
- `src/wayfinder/graph/routing.py` — `choose_next_agent`.
- `src/wayfinder/graph/planning.py` — `plan_workers_for_intent`.

Tests (assertions that encode the OLD routing, must flip to architect_mapper /
fan-out):
- `tests/test_routing.py` — `test_choose_next_agent_*` parametrize
  (runtime/behavioral/debug → architect_mapper); LLM-router runtime case;
  `parse_llm_route_decision` debug + runtime cases.
- `tests/test_supervisor_plan.py` — behavioural intents now fan out to both.
- `tests/test_resilience.py` — user-correction `intent=behavioral` next_agent.

## Gaps / non-goals (explicit)

- This only guarantees a **fallback** candidate (the first entry point). It does
  NOT guarantee the candidate matches the user's actual question — e.g. asking
  about "supervisor routing" may fall back to `dashboard/Dockerfile`. Making the
  candidate *relevant* (resolve filenames like `state.py`, map NL → real
  symbols, repo_mapper symbol search before `find_definition`) is **Gap 2**, a
  separate change.
- Pure `runtime` questions ("how do I run this") now also pay one
  architect_mapper scan. Acceptable: architect_mapper is fast/healthy on large
  repos (verified live, no timeout) and its entry points directly help runtime
  answers.
- `behavioral/runtime/debug` now share the `mixed` execution path. Intent
  classification is retained (architectural still diverges; `mixed` still sets
  `needs_human_review`) for future divergence + HITL.

## Step 4 — reverse-explanation prompts (Haichuan)

1. Why does changing only `plan_workers_for_intent` not fix it — what does the
   supervisor do with `next_agent` vs `pending_workers`?
2. Trace the state: after architect_mapper, which field feeds
   `symbol_candidate_from_state`'s fallback?
3. What's the cost/benefit of routing pure runtime questions through
   architect_mapper first?
4. After this fix, why can "how does the supervisor route?" still produce a weak
   answer — and which gap fixes that?
