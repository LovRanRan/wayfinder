# 011 - Enterprise Workflow Case Study

## Status

Commit 9 design completed on 2026-06-04. This note defines the minimum
enterprise workflow case-study contract for Project 6. It is intentionally a
design boundary only: no production graph, schema, tool, example, or test files
are created in this commit.

The case study stays inside `wayfinder`. It is not Project 11 and it is not a
separate recruiting product.

## Why This Exists

Wayfinder already proves a codebase onboarding workflow:

- deterministic MCP tools provide source truth;
- LangGraph coordinates agent routing and resumable state;
- the verifier labels risky claims;
- HITL and observability make the workflow inspectable.

The missing portfolio signal is enterprise workflow realism: permissioned tool
execution, approval queues, audit logs, unsafe-action blocking, and
workflow-level metrics. The case study shows that the same architecture can be
applied outside developer tooling without diluting the main Wayfinder product.

## Commit 9 Boundary

In scope:

- define the case-study problem, inputs, outputs, and user promise;
- define the graph/node contract in prose;
- define `EnterpriseWorkflowState` fields;
- define policy decisions: `allow`, `allow_if_low_risk`,
  `requires_approval`, and `deny`;
- define `ApprovalTask` and `AuditEvent` required fields;
- define failure handling and eval metrics;
- define the exact future file/module boundary for Commit 10;
- explain the interview story.

Out of scope:

- creating `src/` or `tests/` production code;
- creating example JSON datasets;
- creating a new dashboard;
- connecting Gmail, Salesforce, or any real CRM/email system;
- publishing fake benchmark numbers;
- claiming this as a separate project.

## Case Study Contract

Name:

```text
Permission-Gated Recruiting CRM Agent
```

One-line promise:

```text
A lightweight enterprise workflow demo that simulates recruiting/referral CRM
automation with permission-gated tool execution, approval queues, audit logs,
unsafe-action blocking, and workflow-level evals.
```

Business flow:

```text
candidate profile
-> parse candidate
-> match jobs
-> draft referral or cold outreach
-> risk check
-> approval routing
-> mock CRM update
-> audit log
-> final report
```

## Inputs

Commit 10 should use synthetic local data only:

- candidates: 50 synthetic candidate profiles;
- jobs: 20 synthetic job descriptions;
- contacts: 20 synthetic contacts;
- policy document: allowed actions, denied actions, risk rules, and approval
  requirements;
- risky cases: at least 10 examples that should route to approval or block.

Required candidate fields:

- `candidate_id`
- `name`
- `education`
- `skills`
- `experience`
- `target_roles`
- `location`
- `constraints`

Required job fields:

- `job_id`
- `company`
- `title`
- `requirements`
- `nice_to_have`
- `location`

Required contact fields:

- `contact_id`
- `company`
- `role`
- `relationship`
- `allowed_contact_method`

## Outputs

The workflow must produce:

- matched jobs with scores and reasons;
- outreach draft text;
- risk flags and risk level;
- proposed actions;
- approval tasks for risky mutations;
- audit events for every node/tool decision;
- final status;
- final report.

The final report should be usable without a UI. It must state what happened,
what was blocked, what is waiting for approval, and why.

## Graph Contract

Commit 10 should implement an 8-node workflow:

| Node | Responsibility |
|---|---|
| `parse_candidate` | Normalize candidate profile and mark missing data. |
| `match_jobs` | Score candidate against job descriptions and produce top matches. |
| `draft_outreach` | Draft referral/cold outreach text without sending it. |
| `risk_check` | Detect exaggeration, sensitive claims, unverified metrics, missing contact proof, and high-risk mutations. |
| `approval_router` | Apply policy and create approval tasks or block actions. |
| `mock_crm_update` | Apply only allowed low-risk mock CRM state changes. |
| `audit_logger` | Record node/tool decisions, status, latency, cost, and errors. |
| `final_report` | Summarize matches, drafts, approvals, blocks, and audit references. |

State transitions:

```text
NEW
-> PARSED
-> MATCHED
-> DRAFTED
-> RISK_CHECKED
-> WAITING_APPROVAL / AUTO_APPROVED
-> CRM_UPDATED / BLOCKED / ESCALATED
-> COMPLETED
```

## EnterpriseWorkflowState

The state schema should contain exactly these first-version fields unless the
skeleton review finds a concrete missing contract:

```text
run_id
candidate
jobs
contacts
parsed_profile
job_matches
outreach_draft
risk_flags
risk_level
proposed_actions
approval_tasks
audit_events
final_status
final_report
```

Required status values:

```text
completed
waiting_approval
blocked
failed
```

State ownership rule: nodes may append evidence, risk flags, approval tasks, and
audit events, but policy decisions must be made by the policy layer rather than
by free-form model text.

## Policy Table

| Action | Policy | Reason |
|---|---|---|
| `read_candidate` | `allow` | Read-only local mock data. |
| `match_jobs` | `allow` | Produces recommendations, not external mutations. |
| `draft_outreach` | `allow` | Draft-only output; no email is sent. |
| `add_crm_note` | `allow_if_low_risk` | Low-risk internal note is acceptable after risk check. |
| `update_crm_status` | `allow_if_low_risk` | State mutation must not run when risk is medium/high. |
| `create_referral_request` | `requires_approval` | Creates a sensitive workflow action. |
| `send_email` | `requires_approval` | External communication must be human-approved. |
| `bulk_send_email` | `requires_approval` | Bulk outreach is high risk even with good content. |
| `delete_candidate` | `deny` | Destructive action is outside demo scope. |
| `invent_contact` | `deny` | Contact must exist in synthetic contact data. |

Policy meanings:

| Policy | Meaning |
|---|---|
| `allow` | Agent may execute automatically. |
| `allow_if_low_risk` | Agent may execute only after risk check returns low risk. |
| `requires_approval` | Agent must create an approval task and stop before mutation. |
| `deny` | Agent must block the action and log the reason. |

## ApprovalTask Schema

Required fields:

```text
task_id
run_id
action_name
action_summary
risk_level
reason
status
created_at
```

Allowed statuses:

```text
pending
approved
rejected
needs_edit
```

Approval tasks are created for:

- email sending;
- referral request creation;
- medium/high-risk CRM mutations;
- incomplete candidate/contact evidence;
- outreach drafts that need edits before safe use.

## AuditEvent Schema

Required fields:

```text
event_id
run_id
node_name
tool_name
input_summary
output_summary
risk_level
approval_required
status
latency_ms
cost_usd
error_type
created_at
```

Allowed statuses:

```text
success
failed
blocked
waiting_approval
```

Audit rule: every node decision and every mock tool call writes an event. The
audit log is the evidence layer for the case study; the final report should
point to audit event ids instead of making unsupported claims.

## Failure Handling

| Failure Mode | Handling |
|---|---|
| Missing candidate info | Mark incomplete and route to human review. |
| No matching job found | Return low-confidence report without creating outreach. |
| Low fit score | Route to approval or manual review before CRM mutation. |
| Email send requested | Create approval task; do not send. |
| High-risk CRM update | Require approval and log waiting status. |
| Tool timeout | Retry once with exponential backoff; then mark failed. |
| Policy violation | Block action and log reason. |
| Hallucinated contact | Block if contact id/company does not exist in mock contacts. |
| Outreach exaggerates experience | Block or mark `needs_edit`. |
| Sensitive personal data exposure | Block and log policy violation. |

Core rule:

```text
The model can propose actions, but policy controls execution.
```

## Eval Contract

Commit 10 should create reproducible synthetic eval assets:

```text
50 candidates
20 jobs
20 contacts
10 risky cases
```

Required metrics:

| Metric | Meaning |
|---|---|
| `job_match_precision` | Whether top-k job matches are reasonable. |
| `draft_acceptance_rate` | Whether outreach drafts are usable or need light edits. |
| `approval_routing_accuracy` | Whether risky actions route to approval correctly. |
| `unsafe_action_blocking_rate` | Whether dangerous actions are blocked. |
| `tool_call_success_rate` | Whether mock tools execute successfully. |
| `avg_latency_ms` | Average workflow latency. |
| `cost_per_candidate_usd` | Estimated per-candidate cost. |
| `human_intervention_rate` | Fraction of workflows requiring approval or edit. |

No metric result should be published until it is generated from committed data
and a repeatable runner.

## Commit 10 File Boundary

Future implementation should use the existing `src/wayfinder` package style,
not the draft `app/` path from the source plan.

Planned files:

```text
src/wayfinder/enterprise/state.py
src/wayfinder/enterprise/policy.py
src/wayfinder/enterprise/tools.py
src/wayfinder/enterprise/audit.py
src/wayfinder/enterprise/graph.py
examples/enterprise_workflow/README.md
examples/enterprise_workflow/recruiting_crm_demo.py
examples/enterprise_workflow/mock_candidates.json
examples/enterprise_workflow/mock_jobs.json
examples/enterprise_workflow/mock_contacts.json
examples/enterprise_workflow/mock_policy.md
examples/enterprise_workflow/expected_outputs/sample_audit_log.json
examples/enterprise_workflow/expected_outputs/sample_approval_task.json
examples/enterprise_workflow/expected_outputs/sample_agent_report.md
docs/case_studies/enterprise_workflow_agent.md
docs/case_studies/enterprise_eval_report.md
tests/test_enterprise_policy.py
tests/test_enterprise_workflow.py
```

Implementation constraints:

- no real Gmail, Salesforce, login, or external CRM;
- no separate frontend dashboard;
- no fake benchmark numbers;
- no destructive actions;
- no automatic external communication;
- no production code before Haichuan-owned skeleton review.

## Test Plan For Commit 10

Focused tests should cover:

- policy decisions for every policy value;
- approval routing for email send and high-risk CRM update;
- unsafe email send blocking;
- audit event creation for success, blocked, waiting approval, and failed paths;
- missing contact handling;
- missing candidate info handling;
- low job-match confidence handling;
- final report references approval/audit ids;
- synthetic eval runner produces deterministic output files.

## Interview Explanation

"Wayfinder is primarily a verifier-backed codebase onboarding agent. I added an
enterprise workflow case study to prove that the same agent architecture can
handle permission-gated business workflows. The model can propose actions, but
a policy layer decides whether each action is allowed, requires approval, or is
blocked. Every decision writes an audit event, and the eval focuses on
approval-routing accuracy, unsafe-action blocking, cost, latency, and human
intervention rate."

Short version:

"I kept the case study lightweight: workflow realism, permission boundaries,
auditability, and eval mattered more than UI polish or real CRM integration."
