"""Permission policy for the enterprise workflow case study."""

from pydantic import BaseModel

from wayfinder.enterprise.state import PolicyDecision, RiskLevel

TOOL_POLICIES: dict[str, PolicyDecision] = {
    "read_candidate": "allow",
    "match_jobs": "allow",
    "draft_outreach": "allow",
    "add_crm_note": "allow_if_low_risk",
    "update_crm_status": "allow_if_low_risk",
    "create_referral_request": "requires_approval",
    "send_email": "requires_approval",
    "bulk_send_email": "requires_approval",
    "delete_candidate": "deny",
    "invent_contact": "deny",
}


class PolicyResult(BaseModel):
    action_name: str
    policy: PolicyDecision
    allowed: bool
    approval_required: bool
    denied: bool
    reason: str


def evaluate_policy(action_name: str, risk_level: RiskLevel) -> PolicyResult:
    """Return the deterministic execution decision for an action."""
    policy = TOOL_POLICIES.get(action_name, "deny")

    if policy == "allow":
        return PolicyResult(
            action_name=action_name,
            policy=policy,
            allowed=True,
            approval_required=False,
            denied=False,
            reason="Action is read-only or draft-only.",
        )

    if policy == "allow_if_low_risk":
        if risk_level == "low":
            return PolicyResult(
                action_name=action_name,
                policy=policy,
                allowed=True,
                approval_required=False,
                denied=False,
                reason="Action is allowed because risk is low.",
            )
        return PolicyResult(
            action_name=action_name,
            policy=policy,
            allowed=False,
            approval_required=True,
            denied=False,
            reason="Action mutates workflow state and requires approval above low risk.",
        )

    if policy == "requires_approval":
        return PolicyResult(
            action_name=action_name,
            policy=policy,
            allowed=False,
            approval_required=True,
            denied=False,
            reason="Action requires human approval before execution.",
        )

    return PolicyResult(
        action_name=action_name,
        policy="deny",
        allowed=False,
        approval_required=False,
        denied=True,
        reason="Action is denied by policy.",
    )
