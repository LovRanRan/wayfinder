from wayfinder.enterprise.policy import TOOL_POLICIES, evaluate_policy


def test_policy_table_covers_all_expected_policy_values() -> None:
    assert set(TOOL_POLICIES.values()) == {
        "allow",
        "allow_if_low_risk",
        "requires_approval",
        "deny",
    }


def test_allow_policy_executes_without_approval() -> None:
    result = evaluate_policy("match_jobs", "high")

    assert result.allowed is True
    assert result.approval_required is False
    assert result.denied is False


def test_allow_if_low_risk_only_executes_for_low_risk() -> None:
    low_result = evaluate_policy("update_crm_status", "low")
    high_result = evaluate_policy("update_crm_status", "high")

    assert low_result.allowed is True
    assert high_result.allowed is False
    assert high_result.approval_required is True


def test_requires_approval_policy_never_executes_directly() -> None:
    result = evaluate_policy("send_email", "low")

    assert result.allowed is False
    assert result.approval_required is True
    assert result.denied is False


def test_unknown_or_denied_action_is_blocked() -> None:
    delete_result = evaluate_policy("delete_candidate", "low")
    unknown_result = evaluate_policy("unknown_mutation", "low")

    assert delete_result.denied is True
    assert unknown_result.denied is True
