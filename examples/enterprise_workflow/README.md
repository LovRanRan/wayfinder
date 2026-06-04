# Enterprise Workflow Example

This example runs the Permission-Gated Recruiting CRM Agent case study with
synthetic local data. It does not connect to Gmail, Salesforce, a real CRM, or
any external account.

Run from the repository root:

```bash
uv run python examples/enterprise_workflow/recruiting_crm_demo.py
```

The runner loads:

- `mock_candidates.json`
- `mock_jobs.json`
- `mock_contacts.json`
- `mock_policy.md`

It writes deterministic sample artifacts to `expected_outputs/`:

- `sample_audit_log.json`
- `sample_approval_task.json`
- `sample_agent_report.md`

The point of the example is workflow safety: policy-controlled execution,
approval routing, auditability, and explicit blocking of unsafe actions.
