from pathlib import Path

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from wayfinder.graph import build_graph
from wayfinder.graph.nodes import build_verifier_node
from wayfinder.graph.state import Claim, WayfinderState
from wayfinder.graph.verifier import (
    SkipResult,
    apply_test_approval_decision,
    build_test_approval_payload,
    build_test_plan,
    extract_pending_claims_from_entry_summary,
    risk_policy_for_claim,
    verifier_state_from_state,
)
from wayfinder.graph.verifier import (
    TestPlan as VerifierTestPlan,
)
from wayfinder.graph.verifier import (
    TestRunObservation as VerifierRunObservation,
)
from wayfinder.graph.verifier import (
    TestRunRequest as VerifierRunRequest,
)
from wayfinder.ingestion.models import RepoHandle, RepoSource


class FakeVerifierRunner:
    def __init__(self, status: str = "passed") -> None:
        self.status = status
        self.requests: list[VerifierRunRequest] = []

    def run_test(self, request: VerifierRunRequest) -> VerifierRunObservation:
        self.requests.append(request)
        if self.status == "failed":
            return VerifierRunObservation(
                test_ref=request.test_ref,
                status="failed",
                output="assertion failed",
                passed=0,
                failed=1,
                failures=("tests/test_parser.py::test_invalid_input",),
            )
        if self.status == "timed_out":
            return VerifierRunObservation(
                test_ref=request.test_ref,
                status="timed_out",
                output="test command timed out",
            )
        return VerifierRunObservation(
            test_ref=request.test_ref,
            status="passed",
            output="1 passed",
            passed=1,
        )


class SequencedVerifierRunner:
    def __init__(self, observations: list[VerifierRunObservation]) -> None:
        self.observations = observations
        self.requests: list[VerifierRunRequest] = []

    def run_test(self, request: VerifierRunRequest) -> VerifierRunObservation:
        self.requests.append(request)
        observation = self.observations.pop(0)
        return VerifierRunObservation(
            test_ref=request.test_ref,
            status=observation.status,
            output=observation.output,
            passed=observation.passed,
            failed=observation.failed,
            skipped=observation.skipped,
            failures=observation.failures,
        )


def _repo_handle(tmp_path: Path) -> RepoHandle:
    return RepoHandle(
        source=RepoSource(kind="local", original_ref=str(tmp_path)),
        local_path=tmp_path,
    )


def _claim(test_id: str | None = "tests/test_parser.py::test_invalid_input") -> Claim:
    return {
        "text": "parse_user raises ValueError for invalid input",
        "source_agent": "entry_explainer",
        "risk_level": "high",
        "test_strategy": "existing_test" if test_id is not None else "skip",
        "test_id": test_id,
        "status": "pending",
    }


def test_extract_pending_claims_from_entry_summary_selects_runtime_claims() -> None:
    summary = "\n".join(
        [
            "Definition: app/service.py:2.",
            "Signature: parse_user(raw: str) -> User.",
            "parse_user raises ValueError for invalid input.",
            "field user_id is persisted after verifier node.",
            "Assumptions: empty references are not proof of unused code.",
            "This likely calls the parser.",
        ]
    )

    claims = extract_pending_claims_from_entry_summary(summary)

    assert [claim["text"] for claim in claims] == [
        "parse_user raises ValueError for invalid input",
        "field user_id is persisted after verifier node",
    ]
    assert all(claim["risk_level"] == "high" for claim in claims)


def test_risk_policy_triggers_only_high_risk_or_explicit_test_id() -> None:
    assert risk_policy_for_claim(_claim()).should_verify is True
    low_claim: Claim = {
        "text": "This is orientation text",
        "risk_level": "low",
        "test_strategy": "skip",
        "test_id": None,
    }
    assert (
        risk_policy_for_claim(low_claim).should_verify
        is False
    )


def test_build_test_plan_uses_single_pytest_target(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='sample'\n")

    plan = build_test_plan(str(tmp_path), [_claim()])

    assert plan.unverified_claims == ()
    assert len(plan.requests) == 1
    request = plan.requests[0]
    assert request.tool_name == "run_single_test"
    assert request.framework == "pytest"
    assert request.test_filter == "tests/test_parser.py::test_invalid_input"
    assert request.estimated_runtime_seconds == 10


def test_build_test_plan_marks_high_risk_claim_without_test_unverified(tmp_path: Path) -> None:
    plan = build_test_plan(str(tmp_path), [_claim(test_id=None)])

    assert plan.requests == ()
    assert len(plan.unverified_claims) == 1
    assert plan.unverified_claims[0]["status"] == "unverified"
    assert plan.unverified_reasons == {"claim-0": "no_test_coverage"}


def test_build_test_approval_payload_contains_claims_and_tests(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='sample'\n")
    plan = build_test_plan(str(tmp_path), [_claim()])

    payload = build_test_approval_payload(plan)

    assert payload["type"] == "test_approval"
    assert payload["allowed_actions"] == ["approve", "skip", "modify_filter"]
    assert payload["claims"] == [
        {
            "claim_ref": "claim-0",
            "text": "parse_user raises ValueError for invalid input",
            "risk_level": "high",
            "source_agent": "entry_explainer",
            "test_strategy": "existing_test",
            "test_id": "tests/test_parser.py::test_invalid_input",
        }
    ]
    proposed_tests = payload["proposed_tests"]
    assert isinstance(proposed_tests, list)
    first_test = proposed_tests[0]
    assert isinstance(first_test, dict)
    assert first_test["test_ref"] == "test-0"


def test_apply_test_approval_decision_supports_skip_and_modify(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='sample'\n")
    plan = build_test_plan(str(tmp_path), [_claim()])

    skipped = apply_test_approval_decision(plan, {"action": "skip", "reason": "not now"})
    assert isinstance(skipped, SkipResult)
    assert skipped.reason == "not now"

    modified = apply_test_approval_decision(
        plan,
        {
            "action": "modify_filter",
            "modifications": [
                {
                    "test_ref": "test-0",
                    "test_filter": "tests/test_parser.py::test_edge_case",
                }
            ],
        },
    )
    assert isinstance(modified, VerifierTestPlan)
    assert modified.requests[0].test_filter == "tests/test_parser.py::test_edge_case"


def test_verifier_state_from_state_marks_approved_passing_test_verified(tmp_path: Path) -> None:
    runner = FakeVerifierRunner(status="passed")

    result = verifier_state_from_state(
        {
            "repo_handle": _repo_handle(tmp_path),
            "pending_claims": [_claim()],
            "partial_summaries": {"entry_explainer": "entry summary"},
        },
        test_runner=runner,
        approval_decision={"action": "approve"},
    )

    assert len(runner.requests) == 1
    assert result["verified_claims"][0]["status"] == "verified"
    assert result["unverified_claims"] == []
    assert result["contradicted_claims"] == []
    assert "entry_explainer" in result["partial_summaries"]
    assert "1 verified" in result["partial_summaries"]["verifier"]


def test_verifier_state_from_state_marks_failed_test_contradicted(tmp_path: Path) -> None:
    result = verifier_state_from_state(
        {
            "repo_handle": _repo_handle(tmp_path),
            "pending_claims": [_claim()],
        },
        test_runner=FakeVerifierRunner(status="failed"),
        approval_decision={"action": "approve"},
    )

    assert result["verified_claims"] == []
    assert result["contradicted_claims"][0]["status"] == "contradicted"
    assert "1 contradicted" in result["partial_summaries"]["verifier"]


def test_verifier_state_from_state_marks_skip_unverified(tmp_path: Path) -> None:
    result = verifier_state_from_state(
        {
            "repo_handle": _repo_handle(tmp_path),
            "pending_claims": [_claim()],
        },
        test_runner=FakeVerifierRunner(),
        approval_decision={"action": "skip", "reason": "skipped_by_user"},
    )

    assert result["verified_claims"] == []
    assert result["unverified_claims"][0]["status"] == "unverified"
    assert "skipped_by_user" in result["partial_summaries"]["verifier"]


def test_verifier_state_from_state_records_timeout_as_unverified(tmp_path: Path) -> None:
    result = verifier_state_from_state(
        {
            "repo_handle": _repo_handle(tmp_path),
            "pending_claims": [_claim()],
        },
        test_runner=FakeVerifierRunner(status="timed_out"),
        approval_decision={"action": "approve"},
    )

    assert result["unverified_claims"][0]["status"] == "unverified"
    assert result["test_results"]["test-0"]["status"] == "timed_out"
    assert result["errors"][0]["error_type"] == "validation_timed_out"


def test_verifier_retries_timeout_once_and_can_recover(tmp_path: Path) -> None:
    runner = SequencedVerifierRunner(
        [
            VerifierRunObservation(
                test_ref="test-0",
                status="timed_out",
                output="test command timed out",
            ),
            VerifierRunObservation(
                test_ref="test-0",
                status="passed",
                output="1 passed",
                passed=1,
            ),
        ]
    )

    result = verifier_state_from_state(
        {
            "repo_handle": _repo_handle(tmp_path),
            "pending_claims": [_claim()],
        },
        test_runner=runner,
        approval_decision={"action": "approve"},
    )

    assert len(runner.requests) == 2
    assert runner.requests[1].timeout_seconds > runner.requests[0].timeout_seconds
    assert result["verified_claims"][0]["status"] == "verified"
    assert result["errors"] == []


def test_verifier_retry_timeout_still_unverified(tmp_path: Path) -> None:
    runner = SequencedVerifierRunner(
        [
            VerifierRunObservation(
                test_ref="test-0",
                status="timed_out",
                output="first timeout",
            ),
            VerifierRunObservation(
                test_ref="test-0",
                status="timed_out",
                output="second timeout",
            ),
        ]
    )

    result = verifier_state_from_state(
        {
            "repo_handle": _repo_handle(tmp_path),
            "pending_claims": [_claim()],
        },
        test_runner=runner,
        approval_decision={"action": "approve"},
    )

    assert len(runner.requests) == 2
    assert result["unverified_claims"][0]["status"] == "unverified"
    assert result["errors"][0]["error_type"] == "validation_timed_out"


def test_verifier_marks_unrelated_suite_failure_unverified(tmp_path: Path) -> None:
    runner = SequencedVerifierRunner(
        [
            VerifierRunObservation(
                test_ref="test-0",
                status="failed",
                output="unrelated test failed",
                failed=1,
                failures=("tests/test_other.py::test_unrelated",),
            ),
        ]
    )

    result = verifier_state_from_state(
        {
            "repo_handle": _repo_handle(tmp_path),
            "pending_claims": [_claim()],
        },
        test_runner=runner,
        approval_decision={"action": "approve"},
    )

    assert result["contradicted_claims"] == []
    assert result["unverified_claims"][0]["status"] == "unverified"
    assert "test_suite_failed_unrelated" in result["partial_summaries"]["verifier"]


def test_verifier_state_from_state_handles_missing_repo_path() -> None:
    result = verifier_state_from_state({"pending_claims": [_claim()]})

    assert result["unverified_claims"][0]["status"] == "unverified"
    assert result["errors"][0]["node"] == "verifier"
    assert result["errors"][0]["error_type"] == "missing_repo_path"


def test_build_verifier_node_routes_to_final_writer_when_no_test_target(
    tmp_path: Path,
) -> None:
    node = build_verifier_node(FakeVerifierRunner())

    result = node(
        {
            "repo_handle": _repo_handle(tmp_path),
            "pending_claims": [_claim(test_id=None)],
        }
    )

    assert result["next_agent"] == "final_writer"
    assert result["unverified_claims"][0]["status"] == "unverified"


def test_graph_interrupt_resume_approves_verifier_test(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='sample'\n")
    runner = FakeVerifierRunner(status="passed")
    graph = build_graph(checkpointer=InMemorySaver(), verifier_runner=runner)
    config: RunnableConfig = {"configurable": {"thread_id": "verifier-hitl"}}

    graph_input: WayfinderState = {
        "repo_url": str(tmp_path),
        "query": "Explain behavior of app.service.parse_user",
        "repo_handle": _repo_handle(tmp_path),
        "entry_points": ["app.service.parse_user"],
        "pending_claims": [_claim()],
    }
    initial = graph.invoke(graph_input, config=config)

    assert "__interrupt__" in initial

    resumed = graph.invoke(Command(resume={"action": "approve"}), config=config)

    assert runner.requests[0].test_filter == "tests/test_parser.py::test_invalid_input"
    assert resumed["verified_claims"][0]["status"] == "verified"
    assert resumed["final_output"] is not None
    assert "Verification summary" in resumed["final_output"]
