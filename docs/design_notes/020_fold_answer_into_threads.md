# 020 — Fold the Answer view into Threads (Commit 24 follow-up)

> Status: drafted by Cowork at Haichuan's explicit request. Frontend-only.
> Goal: make Threads the single surface by surfacing the rich structured run
> report (verified/unverified/contradicted pills, evidence cards, claim
> provenance panel) inside a thread, so the standalone Answer tab becomes
> redundant and can be retired.

## Problem

After Commit 24 retired the Run tab, two surfaces remain: **Threads** (chat +
grounded runs) and **Answer** (the rich structured viewer = `CurrentRunConsole`).
Threads currently shows a run's Context panel, Agent-trace panel, and a status
line, but NOT the rich answer body (claim pills, evidence cards, provenance).
So a user must leave Threads and switch to Answer to see the grounded report.

## Approach (this step: fold in; next step: drop Answer)

Reuse `CurrentRunConsole` rather than duplicating it.

1. Add an optional `embedded` mode to `CurrentRunConsole`:
   - default (tab) mode unchanged: `min-h-[620px]`, `grid-rows-[auto_1fr]`,
     internal `overflow-y-auto` body.
   - embedded mode: drop the fixed height and internal scroll so the report
     flows as normal content (it lives inside the Threads transcript, which
     already scrolls). `publicApiBaseUrl` becomes optional; the API-docs button
     only renders when a `publicApiBaseUrl` is supplied (hidden when embedded).
2. In `repo-conversation-workspace.tsx`, render the embedded console inside a
   collapsible `<details>` ("Grounded report") in the transcript, for the
   active/selected run (`activeRun`). Collapsed by default so it never crowds
   the chat; expand to see the full report.

**Ordering / safety:** keep the Answer tab in this step. Only after Haichuan
visually confirms the in-thread report matches the Answer console's richness
do we remove the Answer tab (union + `WorkspaceTabs` + `agent-workbench` block +
default-tab/`selectRun` redirects to `threads`). Removing Answer before
confirming the embed would risk leaving no good run view.

## Files

- `dashboard/components/current-run-console.tsx`: `embedded` prop, optional
  `publicApiBaseUrl`, conditional root/body classes, guarded API-docs button.
- `dashboard/components/repo-conversation-workspace.tsx`: import + render the
  embedded console in a `<details>` in the transcript.

## Failure cases / risk

- Nested scroll: avoided by dropping the console's internal scroll in embedded
  mode (the transcript is the single scroll container).
- No run yet: `activeRun === null` → the `<details>` is not rendered.
- Frontend only; backend/API untouched. Needs `npm run lint/typecheck/build`
  and a visual check (can't be verified by Cowork).

## Deferred to the next step

- Remove the Answer tab and redirect default-tab / `selectRun` navigation to
  `threads` once the in-thread report is visually confirmed.
- Optional: per-message expandable report attachments (the original design
  spec) instead of one shared collapsible report.

## Interview explanation

"I consolidated three entry points into one ambient chat surface. The rich
grounded report (claim verification + per-agent provenance) is the same
component reused in an embedded mode inside the thread, so there's no duplicated
rendering logic — and I sequenced it safely: surface the report in-thread and
verify it before deleting the old tab."
