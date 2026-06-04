from wayfinder.enterprise.graph import run_enterprise_workflow
from wayfinder.enterprise.state import CandidateProfile, Contact, JobDescription


def _candidate(**overrides: object) -> CandidateProfile:
    payload: dict[str, object] = {
        "candidate_id": "cand_001",
        "name": "Alex Chen",
        "education": "MS Analytics",
        "skills": ["Python", "FastAPI", "LangGraph", "RAG"],
        "experience": ["Backend internship", "RAG project"],
        "target_roles": ["AI Engineer"],
        "location": "San Francisco",
        "constraints": ["needs sponsorship"],
    }
    payload.update(overrides)
    return CandidateProfile.model_validate(payload)


def _jobs() -> list[JobDescription]:
    return [
        JobDescription(
            job_id="job_001",
            company="Salesforce",
            title="AI Agent Engineer",
            requirements=["Python", "FastAPI", "LangGraph", "RAG"],
            nice_to_have=["CRM", "enterprise workflow"],
            location="San Francisco",
        ),
        JobDescription(
            job_id="job_002",
            company="DataCorp",
            title="Analytics Engineer",
            requirements=["SQL", "dbt", "Airflow"],
            nice_to_have=["Python"],
            location="New York",
        ),
    ]


def _contacts() -> list[Contact]:
    return [
        Contact(
            contact_id="contact_001",
            company="Salesforce",
            role="Software Engineer",
            relationship="alumni",
            allowed_contact_method="draft_only",
        )
    ]


def test_enterprise_workflow_routes_email_send_to_approval() -> None:
    state = run_enterprise_workflow(_candidate(), _jobs(), _contacts())

    approval_actions = {task.action_name for task in state.approval_tasks}
    assert "send_email" in approval_actions
    assert "create_referral_request" in approval_actions
    assert state.final_status == "waiting_approval"
    assert all(action.action_name != "send_email" or action.status == "waiting_approval"
               for action in state.proposed_actions)


def test_enterprise_workflow_blocks_hallucinated_contact() -> None:
    state = run_enterprise_workflow(_candidate(), _jobs(), [])

    blocked_actions = [action for action in state.proposed_actions if action.status == "blocked"]
    assert blocked_actions[0].action_name == "invent_contact"
    assert any(event.error_type == "policy_denied" for event in state.audit_events)
    assert "No verified contact exists" in state.outreach_draft


def test_high_risk_crm_update_requires_approval() -> None:
    candidate = _candidate(skills=["Python"], experience=["Backend internship"])

    state = run_enterprise_workflow(candidate, _jobs(), _contacts())

    update_action = next(
        action for action in state.proposed_actions if action.action_name == "update_crm_status"
    )
    assert update_action.status == "waiting_approval"
    assert any(task.action_name == "update_crm_status" for task in state.approval_tasks)


def test_missing_candidate_info_routes_to_human_review() -> None:
    state = run_enterprise_workflow(
        _candidate(education="", skills=[]),
        _jobs(),
        _contacts(),
    )

    assert any(flag.flag_type == "missing_candidate_info" for flag in state.risk_flags)
    assert state.final_status == "waiting_approval"
    assert any(task.status == "pending" for task in state.approval_tasks)


def test_audit_events_and_final_report_reference_evidence_ids() -> None:
    state = run_enterprise_workflow(_candidate(), _jobs(), _contacts(), run_id="run_test")

    statuses = {event.status for event in state.audit_events}
    assert {"success", "waiting_approval"}.issubset(statuses)
    assert "approval-001" in state.final_report
    assert "audit-001" in state.final_report
    assert state.audit_events[-1].node_name == "final_report"
