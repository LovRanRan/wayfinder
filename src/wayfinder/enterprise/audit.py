"""Audit helpers for the enterprise workflow case study."""

from datetime import UTC, datetime

from wayfinder.enterprise.state import AuditEvent, AuditStatus, RiskLevel


def append_audit_event(
    events: list[AuditEvent],
    *,
    run_id: str,
    node_name: str,
    input_summary: str,
    output_summary: str,
    status: AuditStatus,
    tool_name: str | None = None,
    risk_level: RiskLevel | None = None,
    approval_required: bool = False,
    error_type: str | None = None,
    latency_ms: int = 0,
    cost_usd: float = 0.0,
    created_at: datetime | None = None,
) -> AuditEvent:
    """Append one deterministic audit event and return it."""
    event = AuditEvent(
        event_id=f"audit-{len(events) + 1:03d}",
        run_id=run_id,
        node_name=node_name,
        tool_name=tool_name,
        input_summary=input_summary,
        output_summary=output_summary,
        risk_level=risk_level,
        approval_required=approval_required,
        status=status,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        error_type=error_type,
        created_at=created_at or datetime.now(UTC),
    )
    events.append(event)
    return event
