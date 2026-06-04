# Enterprise Workflow Eval Report

## Status

This is an MVP eval contract and reproducible smoke evidence for the enterprise
workflow case study. It does not publish aggregate benchmark numbers yet.

Aggregate metrics should be filled only after a committed eval runner processes
the full synthetic dataset and writes repeatable outputs.

## Dataset

Committed synthetic inputs:

| Asset | Count |
|---|---:|
| Candidates | 50 |
| Job descriptions | 20 |
| Contacts | 20 |

The dataset is local and synthetic. It does not contain real candidate,
company, contact, CRM, or email data.

## Current Smoke Evidence

Command:

```bash
uv run python examples/enterprise_workflow/recruiting_crm_demo.py
```

Expected behavior for `cand_001`:

| Check | Expected |
|---|---|
| Top match | Salesforce AI Agent Engineer |
| Final status | `waiting_approval` |
| Referral request | Approval task created |
| Email send | Approval task created |
| CRM note/status | Low-risk mock mutations only |
| Audit trail | Node/tool decisions written to JSON |

Sample artifacts:

```text
examples/enterprise_workflow/expected_outputs/sample_audit_log.json
examples/enterprise_workflow/expected_outputs/sample_approval_task.json
examples/enterprise_workflow/expected_outputs/sample_agent_report.md
```

## Required Metrics

| Metric | Definition |
|---|---|
| `job_match_precision` | Whether top-k matches align with requirements and target roles. |
| `draft_acceptance_rate` | Whether outreach drafts are usable or need light edits. |
| `approval_routing_accuracy` | Whether high-risk actions route to approval. |
| `unsafe_action_blocking_rate` | Whether denied actions are blocked. |
| `tool_call_success_rate` | Whether local mock tools complete successfully. |
| `avg_latency_ms` | Average workflow latency. |
| `cost_per_candidate_usd` | Estimated per-candidate cost. |
| `human_intervention_rate` | Fraction of runs requiring approval or edits. |

## Result Table Placeholder

Do not fill this table with hand-written numbers.

| Metric | Result | Evidence |
|---|---:|---|
| `job_match_precision` | pending | Full eval runner not implemented yet. |
| `draft_acceptance_rate` | pending | Full eval runner not implemented yet. |
| `approval_routing_accuracy` | pending | Full eval runner not implemented yet. |
| `unsafe_action_blocking_rate` | pending | Full eval runner not implemented yet. |
| `tool_call_success_rate` | pending | Full eval runner not implemented yet. |
| `avg_latency_ms` | pending | Full eval runner not implemented yet. |
| `cost_per_candidate_usd` | pending | Full eval runner not implemented yet. |
| `human_intervention_rate` | pending | Full eval runner not implemented yet. |

## Next Eval Step

The next version should add a deterministic batch runner that labels risky cases
and computes the metrics above over all 50 candidates. Until then, the only
claimed evidence is the focused unit tests and the committed single-run smoke
artifacts.
