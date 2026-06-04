"""Deterministic enterprise workflow graph for the case study MVP."""

from collections.abc import Iterable
from datetime import UTC, datetime

from wayfinder.enterprise.audit import append_audit_event
from wayfinder.enterprise.policy import evaluate_policy
from wayfinder.enterprise.state import (
    ApprovalTask,
    CandidateProfile,
    Contact,
    EnterpriseWorkflowState,
    JobDescription,
    ProposedAction,
    RiskFlag,
    RiskLevel,
)
from wayfinder.enterprise.tools import (
    draft_outreach,
    find_contact_for_company,
    match_jobs_to_candidate,
)


def run_enterprise_workflow(
    candidate: CandidateProfile,
    jobs: list[JobDescription],
    contacts: list[Contact],
    *,
    run_id: str = "run_001",
    created_at: datetime | None = None,
) -> EnterpriseWorkflowState:
    """Run one synthetic candidate through the permission-gated workflow."""
    event_time = created_at or datetime.now(UTC)
    state = EnterpriseWorkflowState(
        run_id=run_id,
        candidate=candidate,
        jobs=jobs,
        contacts=contacts,
    )

    _parse_candidate(state, event_time)
    _match_jobs(state, event_time)
    _draft_outreach(state, event_time)
    _risk_check(state, event_time)
    _approval_router(state, event_time)
    _mock_crm_update(state, event_time)
    _final_report(state, event_time)
    return state


def _parse_candidate(state: EnterpriseWorkflowState, created_at: datetime) -> None:
    missing_fields = [
        field
        for field, value in {
            "education": state.candidate.education,
            "skills": state.candidate.skills,
            "experience": state.candidate.experience,
            "target_roles": state.candidate.target_roles,
            "location": state.candidate.location,
        }.items()
        if not value
    ]
    state.parsed_profile = {
        "candidate_id": state.candidate.candidate_id,
        "skill_count": len(state.candidate.skills),
        "target_role_count": len(state.candidate.target_roles),
        "missing_fields": missing_fields,
    }
    if missing_fields:
        state.risk_flags.append(
            RiskFlag(
                flag_type="missing_candidate_info",
                risk_level="medium",
                message=f"Missing candidate fields: {', '.join(missing_fields)}.",
            )
        )

    append_audit_event(
        state.audit_events,
        run_id=state.run_id,
        node_name="parse_candidate",
        tool_name="read_candidate",
        input_summary=state.candidate.candidate_id,
        output_summary=f"parsed with {len(missing_fields)} missing fields",
        risk_level="medium" if missing_fields else "low",
        status="success",
        latency_ms=14,
        cost_usd=0.0,
        created_at=created_at,
    )


def _match_jobs(state: EnterpriseWorkflowState, created_at: datetime) -> None:
    state.job_matches = match_jobs_to_candidate(state.candidate, state.jobs)
    if not state.job_matches:
        state.risk_flags.append(
            RiskFlag(
                flag_type="no_matching_job",
                risk_level="medium",
                message="No matching job found; do not create outreach.",
            )
        )
    elif state.job_matches[0].score < 0.45:
        state.risk_flags.append(
            RiskFlag(
                flag_type="low_fit_score",
                risk_level="medium",
                message=f"Top match score is only {state.job_matches[0].score}.",
            )
        )

    append_audit_event(
        state.audit_events,
        run_id=state.run_id,
        node_name="match_jobs",
        tool_name="match_jobs",
        input_summary=f"{state.candidate.candidate_id} against {len(state.jobs)} jobs",
        output_summary=f"{len(state.job_matches)} candidate matches",
        risk_level="low" if state.job_matches else "medium",
        status="success",
        latency_ms=31,
        cost_usd=0.0,
        created_at=created_at,
    )


def _draft_outreach(state: EnterpriseWorkflowState, created_at: datetime) -> None:
    if not state.job_matches:
        state.outreach_draft = "No outreach draft created because no safe job match exists."
        append_audit_event(
            state.audit_events,
            run_id=state.run_id,
            node_name="draft_outreach",
            tool_name="draft_outreach",
            input_summary="no job match",
            output_summary="draft skipped",
            risk_level="medium",
            status="blocked",
            error_type="no_matching_job",
            latency_ms=7,
            cost_usd=0.0,
            created_at=created_at,
        )
        return

    top_match = state.job_matches[0]
    contact = find_contact_for_company(state.contacts, top_match.company)
    if contact is None:
        state.risk_flags.append(
            RiskFlag(
                flag_type="missing_contact",
                risk_level="high",
                message=f"No verified contact found for {top_match.company}.",
            )
        )

    state.outreach_draft = draft_outreach(state.candidate, top_match, contact)
    append_audit_event(
        state.audit_events,
        run_id=state.run_id,
        node_name="draft_outreach",
        tool_name="draft_outreach",
        input_summary=top_match.job_id,
        output_summary=(
            "draft created" if contact is not None else "draft blocked by missing contact"
        ),
        risk_level="low" if contact is not None else "high",
        status="success" if contact is not None else "blocked",
        error_type=None if contact is not None else "missing_contact",
        latency_ms=44,
        cost_usd=0.01,
        created_at=created_at,
    )


def _risk_check(state: EnterpriseWorkflowState, created_at: datetime) -> None:
    state.risk_level = _highest_risk(flag.risk_level for flag in state.risk_flags)
    if not state.job_matches:
        state.proposed_actions = []
    else:
        top_match = state.job_matches[0]
        has_contact = find_contact_for_company(state.contacts, top_match.company) is not None
        state.proposed_actions = [
            ProposedAction(
                action_name="add_crm_note",
                action_summary=f"Add match note for {state.candidate.name}.",
                risk_level=state.risk_level,
                reason="Internal note documenting the match result.",
            ),
            ProposedAction(
                action_name="update_crm_status",
                action_summary=f"Move {state.candidate.name} to matched for {top_match.job_id}.",
                risk_level=state.risk_level if top_match.score < 0.75 else "low",
                reason="CRM status mutation must respect risk level.",
            ),
        ]
        if has_contact:
            state.proposed_actions.extend(
                [
                    ProposedAction(
                        action_name="create_referral_request",
                        action_summary=f"Create referral request for {top_match.company}.",
                        risk_level="medium",
                        reason="Referral workflow action requires review.",
                    ),
                    ProposedAction(
                        action_name="send_email",
                        action_summary=f"Send outreach draft for {top_match.company}.",
                        risk_level="high",
                        reason="External communication must not be automatic.",
                    ),
                ]
            )
        else:
            state.proposed_actions.append(
                ProposedAction(
                    action_name="invent_contact",
                    action_summary=f"Create a placeholder contact for {top_match.company}.",
                    risk_level="high",
                    reason="Contacts must come from synthetic contact data.",
                )
            )

    append_audit_event(
        state.audit_events,
        run_id=state.run_id,
        node_name="risk_check",
        tool_name="mock_policy_store",
        input_summary=f"{len(state.risk_flags)} risk flags",
        output_summary=f"{state.risk_level} risk; {len(state.proposed_actions)} actions",
        risk_level=state.risk_level,
        status="success",
        latency_ms=18,
        cost_usd=0.0,
        created_at=created_at,
    )


def _approval_router(state: EnterpriseWorkflowState, created_at: datetime) -> None:
    for action in state.proposed_actions:
        decision = evaluate_policy(action.action_name, action.risk_level)
        if decision.allowed:
            action.status = "allowed"
            append_audit_event(
                state.audit_events,
                run_id=state.run_id,
                node_name="approval_router",
                tool_name="tool_permissions",
                input_summary=action.action_name,
                output_summary=decision.reason,
                risk_level=action.risk_level,
                status="success",
                latency_ms=5,
                cost_usd=0.0,
                created_at=created_at,
            )
            continue

        if decision.approval_required:
            action.status = "waiting_approval"
            state.approval_tasks.append(
                ApprovalTask(
                    task_id=f"approval-{len(state.approval_tasks) + 1:03d}",
                    run_id=state.run_id,
                    action_name=action.action_name,
                    action_summary=action.action_summary,
                    risk_level=action.risk_level,
                    reason=decision.reason,
                    status="pending",
                    created_at=created_at,
                )
            )
            append_audit_event(
                state.audit_events,
                run_id=state.run_id,
                node_name="approval_router",
                tool_name="approval_queue",
                input_summary=action.action_name,
                output_summary=decision.reason,
                risk_level=action.risk_level,
                approval_required=True,
                status="waiting_approval",
                latency_ms=8,
                cost_usd=0.0,
                created_at=created_at,
            )
            continue

        action.status = "blocked"
        append_audit_event(
            state.audit_events,
            run_id=state.run_id,
            node_name="approval_router",
            tool_name="tool_permissions",
            input_summary=action.action_name,
            output_summary=decision.reason,
            risk_level=action.risk_level,
            status="blocked",
            error_type="policy_denied",
            latency_ms=5,
            cost_usd=0.0,
            created_at=created_at,
        )


def _mock_crm_update(state: EnterpriseWorkflowState, created_at: datetime) -> None:
    executed = 0
    for action in state.proposed_actions:
        if action.status != "allowed":
            continue
        if action.action_name in {"add_crm_note", "update_crm_status"}:
            action.status = "executed"
            executed += 1
            append_audit_event(
                state.audit_events,
                run_id=state.run_id,
                node_name="mock_crm_update",
                tool_name=action.action_name,
                input_summary=action.action_summary,
                output_summary="mock CRM mutation recorded",
                risk_level=action.risk_level,
                status="success",
                latency_ms=22,
                cost_usd=0.0,
                created_at=created_at,
            )

    if state.approval_tasks:
        state.final_status = "waiting_approval"
    elif any(action.status == "blocked" for action in state.proposed_actions):
        state.final_status = "blocked"
    elif executed > 0:
        state.final_status = "completed"
    else:
        state.final_status = "failed"


def _final_report(state: EnterpriseWorkflowState, created_at: datetime) -> None:
    match_lines = [
        f"- {match.company} {match.title} ({match.score:.2f}): {match.reason}"
        for match in state.job_matches
    ] or ["- No safe job match found."]
    approval_lines = [
        f"- {task.task_id}: {task.action_name} -> {task.status} ({task.reason})"
        for task in state.approval_tasks
    ] or ["- No approval tasks."]
    blocked_lines = [
        f"- {action.action_name}: {action.reason}"
        for action in state.proposed_actions
        if action.status == "blocked"
    ] or ["- No blocked actions."]
    audit_refs = ", ".join(event.event_id for event in state.audit_events)
    state.final_report = "\n".join(
        [
            f"Enterprise workflow run {state.run_id}",
            f"Candidate: {state.candidate.name}",
            f"Final status: {state.final_status}",
            "Job matches:",
            *match_lines,
            "Outreach draft:",
            state.outreach_draft,
            "Approval tasks:",
            *approval_lines,
            "Blocked actions:",
            *blocked_lines,
            f"Audit events: {audit_refs}",
        ]
    )
    append_audit_event(
        state.audit_events,
        run_id=state.run_id,
        node_name="final_report",
        tool_name=None,
        input_summary=state.final_status,
        output_summary="final report generated",
        risk_level=state.risk_level,
        status="success",
        latency_ms=12,
        cost_usd=0.0,
        created_at=created_at,
    )


def _highest_risk(levels: Iterable[RiskLevel]) -> RiskLevel:
    order = {"low": 0, "medium": 1, "high": 2}
    highest: RiskLevel = "low"
    for level in levels:
        if order[level] > order[highest]:
            highest = level
    return highest
