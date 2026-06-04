"""State and data contracts for the enterprise workflow case study."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["low", "medium", "high"]
PolicyDecision = Literal["allow", "allow_if_low_risk", "requires_approval", "deny"]
ApprovalStatus = Literal["pending", "approved", "rejected", "needs_edit"]
AuditStatus = Literal["success", "failed", "blocked", "waiting_approval"]
ActionStatus = Literal["proposed", "allowed", "blocked", "waiting_approval", "executed"]
FinalStatus = Literal["completed", "waiting_approval", "blocked", "failed"]


class CandidateProfile(BaseModel):
    candidate_id: str
    name: str
    education: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    location: str = ""
    constraints: list[str] = Field(default_factory=list)


class JobDescription(BaseModel):
    job_id: str
    company: str
    title: str
    requirements: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    location: str = ""


class Contact(BaseModel):
    contact_id: str
    company: str
    role: str
    relationship: str
    allowed_contact_method: str


class JobMatch(BaseModel):
    job_id: str
    company: str
    title: str
    score: float
    matched_requirements: list[str] = Field(default_factory=list)
    reason: str


class RiskFlag(BaseModel):
    flag_type: str
    risk_level: RiskLevel
    message: str


class ProposedAction(BaseModel):
    action_name: str
    action_summary: str
    risk_level: RiskLevel
    status: ActionStatus = "proposed"
    reason: str


class ApprovalTask(BaseModel):
    task_id: str
    run_id: str
    action_name: str
    action_summary: str
    risk_level: RiskLevel
    reason: str
    status: ApprovalStatus = "pending"
    created_at: datetime


class AuditEvent(BaseModel):
    event_id: str
    run_id: str
    node_name: str
    tool_name: str | None
    input_summary: str
    output_summary: str
    risk_level: RiskLevel | None
    approval_required: bool
    status: AuditStatus
    latency_ms: int
    cost_usd: float
    error_type: str | None
    created_at: datetime


class EnterpriseWorkflowState(BaseModel):
    run_id: str
    candidate: CandidateProfile
    jobs: list[JobDescription] = Field(default_factory=list)
    contacts: list[Contact] = Field(default_factory=list)
    parsed_profile: dict[str, object] = Field(default_factory=dict)
    job_matches: list[JobMatch] = Field(default_factory=list)
    outreach_draft: str = ""
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    risk_level: RiskLevel = "low"
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    approval_tasks: list[ApprovalTask] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)
    final_status: FinalStatus = "failed"
    final_report: str = ""
