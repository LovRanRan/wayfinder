# Enterprise Workflow Case Study

## Permission-Gated Recruiting CRM Agent

This case study extends Wayfinder with a lightweight enterprise workflow demo.
It is not a separate recruiting product and does not connect to Gmail,
Salesforce, a real CRM, login, or any external account.

The goal is to show that Wayfinder's agent architecture generalizes beyond
codebase onboarding into risk-controlled business workflows:

```text
candidate profile
-> job matching
-> outreach draft
-> risk check
-> approval routing
-> mock CRM update
-> audit log
-> final report
```

## What It Demonstrates

- permission-gated tool execution;
- approval tasks for high-risk actions;
- audit events for every node and mock tool decision;
- unsafe-action blocking;
- deterministic synthetic inputs;
- workflow-level evaluation contract.

## Implemented Files

```text
src/wayfinder/enterprise/state.py
src/wayfinder/enterprise/policy.py
src/wayfinder/enterprise/audit.py
src/wayfinder/enterprise/tools.py
src/wayfinder/enterprise/graph.py
examples/enterprise_workflow/
tests/test_enterprise_policy.py
tests/test_enterprise_workflow.py
```

## Policy Boundary

The model or workflow may propose actions, but policy controls execution.

| Action | Policy |
|---|---|
| `read_candidate` | `allow` |
| `match_jobs` | `allow` |
| `draft_outreach` | `allow` |
| `add_crm_note` | `allow_if_low_risk` |
| `update_crm_status` | `allow_if_low_risk` |
| `create_referral_request` | `requires_approval` |
| `send_email` | `requires_approval` |
| `bulk_send_email` | `requires_approval` |
| `delete_candidate` | `deny` |
| `invent_contact` | `deny` |

This means draft-only work can proceed, but external communication and risky CRM
mutations stop at an approval task.

## Run The Demo

From the repository root:

```bash
uv run python examples/enterprise_workflow/recruiting_crm_demo.py
```

The runner loads 50 synthetic candidates, 20 job descriptions, and 20 contacts.
It writes:

```text
examples/enterprise_workflow/expected_outputs/sample_audit_log.json
examples/enterprise_workflow/expected_outputs/sample_approval_task.json
examples/enterprise_workflow/expected_outputs/sample_agent_report.md
```

The sample run ends in `waiting_approval` because `create_referral_request` and
`send_email` require human review.

## Failure Handling

| Failure Mode | Handling |
|---|---|
| Missing candidate info | Adds a risk flag and routes mutations to approval. |
| No matching job | Blocks outreach draft creation. |
| Low fit score | Requires approval before CRM mutation. |
| Email send requested | Creates approval task, does not send. |
| High-risk CRM update | Creates approval task. |
| Policy violation | Blocks action and writes audit event. |
| Missing contact | Blocks invented contact action. |

## Interview Explanation

"Wayfinder is primarily a verifier-backed codebase onboarding agent. I added a
small enterprise workflow case study to show the same architecture can handle a
business workflow with permissioned tools, approval queues, audit logs, and
unsafe-action blocking. The workflow can draft and match automatically, but it
cannot send email, invent contacts, or mutate CRM state without policy approval."
