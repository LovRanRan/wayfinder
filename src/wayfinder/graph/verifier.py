"""Verifier and HITL approval helpers for high-risk code claims."""

import asyncio
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, Protocol, TypedDict, cast

from langgraph.types import interrupt

from wayfinder.graph.state import (
    Claim,
    ClaimStatus,
    GraphError,
    RiskLevel,
    TestResult,
    WayfinderState,
)
from wayfinder.mcp.adapter import MCPToolCallError
from wayfinder.mcp.models import MCPToolCall, MCPToolCallResult

Framework = Literal["pytest", "jest"]
TestToolName = Literal["run_single_test", "run_pytest", "run_jest"]
ObservationStatus = Literal["passed", "failed", "timed_out", "malformed", "tool_error"]
ApprovalAction = Literal["approve", "skip", "modify_filter"]

_RUNTIME_CLAIM_KEYWORDS = (
    "return",
    "returns",
    "raise",
    "raises",
    "mutate",
    "mutates",
    "validate",
    "validates",
    "parse",
    "parses",
    "reject",
    "rejects",
    "route",
    "routes",
    "retry",
    "retries",
    "time out",
    "times out",
    "becomes",
    "persist",
    "persists",
    "writes",
    "passes",
    "fails",
    "exit code",
    "status count",
)
_IGNORED_SUMMARY_PREFIXES = (
    "entry explanation evidence collected",
    "definition:",
    "signature:",
    "call chain:",
    "references:",
    "source citations:",
    "assumptions:",
    "class hierarchy:",
    "key functions:",
)
_HEDGE_WORDS = (" likely ", " may ", " appears ", " probably ", " might ")


class ApprovalDecision(TypedDict, total=False):
    action: ApprovalAction
    reason: str
    modifications: list[dict[str, object]]


@dataclass(frozen=True)
class RiskDecision:
    risk_level: Literal["low", "medium", "high"]
    should_verify: bool
    reason: str


@dataclass(frozen=True)
class TestRunRequest:
    test_ref: str
    claim_refs: tuple[str, ...]
    framework: Framework
    tool_name: TestToolName
    path: str
    test_filter: str
    timeout_seconds: float
    estimated_runtime_seconds: int
    max_output_bytes: int = 12000
    job_id: str | None = None
    run_owner: str | None = None
    repo_url: str | None = None


@dataclass(frozen=True)
class TestRunObservation:
    test_ref: str
    status: ObservationStatus
    output: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class TestPlan:
    claims_by_ref: dict[str, Claim]
    requests: tuple[TestRunRequest, ...]
    unverified_claims: tuple[Claim, ...]
    unverified_reasons: dict[str, str]


@dataclass(frozen=True)
class SkipResult:
    claim_refs: tuple[str, ...]
    reason: str


class TestRunner(Protocol):
    def run_test(self, request: TestRunRequest) -> TestRunObservation: ...


class _MCPAdapter(Protocol):
    async def call_tool(self, call: MCPToolCall) -> MCPToolCallResult: ...


class UnavailableTestRunner:
    def run_test(self, request: TestRunRequest) -> TestRunObservation:
        return TestRunObservation(
            test_ref=request.test_ref,
            status="tool_error",
            output="verifier test runner is not configured",
        )


class MCPTestRunner:
    def __init__(self, adapter: _MCPAdapter) -> None:
        self._adapter = adapter

    def run_test(self, request: TestRunRequest) -> TestRunObservation:
        try:
            command_result = self._call_dict(_test_execution_call(request))
        except MCPToolCallError as exc:
            return TestRunObservation(
                test_ref=request.test_ref,
                status="tool_error",
                output=exc.error.message,
            )

        if command_result.get("timed_out") is True:
            return TestRunObservation(
                test_ref=request.test_ref,
                status="timed_out",
                output=_command_output(command_result),
            )

        stdout = _stdout_for_parse(command_result, request)
        if stdout is None:
            return _observation_from_exit_code(request, command_result)

        try:
            parsed = self._call_dict(
                MCPToolCall(
                    tool_name="parse_test_output",
                    arguments={"stdout": stdout, "framework": request.framework},
                )
            )
        except (MCPToolCallError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return TestRunObservation(
                test_ref=request.test_ref,
                status="malformed",
                output=str(exc) or _command_output(command_result),
            )

        return _observation_from_parsed_result(
            request=request,
            parsed=parsed,
            fallback_output=_command_output(command_result),
        )

    def _call_dict(self, call: MCPToolCall) -> dict[str, object]:
        result = self._call_adapter(call)
        content = result.content
        if not isinstance(content, dict):
            raise TypeError(f"mcp-test-runner {call.tool_name} returned non-dict content")

        return cast(dict[str, object], content)

    def _call_adapter(self, call: MCPToolCall) -> MCPToolCallResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._adapter.call_tool(call))

        raise RuntimeError("MCP test runner cannot run inside an active event loop")


def claim_refs_for_pending_claims(claims: Sequence[Claim]) -> dict[str, Claim]:
    return {f"claim-{index}": claim for index, claim in enumerate(claims)}


def extract_pending_claims_from_state(state: WayfinderState) -> list[Claim]:
    existing_claims = state.get("pending_claims")
    if existing_claims:
        claims = [_normalize_claim(claim) for claim in existing_claims]
    else:
        partial_summaries = state.get("partial_summaries", {})
        entry_summary = partial_summaries.get("entry_explainer", "")
        claims = extract_pending_claims_from_entry_summary(entry_summary)

    # Also treat a high-risk user query as a verifiable claim, so an explicit
    # "does X do Y / verify that ..." request can be grounded by autonomous test
    # discovery even when no sub-agent emitted a testable summary line.
    query_claim = _claim_from_query(state.get("query", ""))
    if query_claim is not None and not _claims_cover_text(claims, query_claim["text"]):
        claims.append(query_claim)
    return claims


def _claim_from_query(query: str) -> Claim | None:
    text = query.strip()
    if not text or not _is_high_risk_text(text):
        return None
    return {
        "text": text,
        "source_agent": "supervisor",
        "risk_level": "high",
        "test_strategy": "existing_test",
        "test_id": _test_target_from_text(text),
        "status": "pending",
    }


def _claims_cover_text(claims: Sequence[Claim], text: str) -> bool:
    needle = text.strip()
    return any(claim.get("text", "").strip() == needle for claim in claims)


def extract_pending_claims_from_entry_summary(summary: str) -> list[Claim]:
    claims: list[Claim] = []
    for raw_line in summary.splitlines():
        text = _clean_claim_text(raw_line)
        if not text or not _is_testable_summary_line(text):
            continue

        test_id = _test_target_from_text(text)
        claims.append(
            {
                "text": text,
                "source_agent": "entry_explainer",
                "risk_level": "high",
                "test_strategy": "existing_test" if test_id is not None else "skip",
                "test_id": test_id,
                "status": "pending",
            }
        )

    return claims


def risk_policy_for_claim(claim: Claim) -> RiskDecision:
    text = claim.get("text", "")
    if claim.get("test_id"):
        return RiskDecision("high", True, "explicit test id")

    risk_level = claim.get("risk_level")
    if risk_level == "high":
        return RiskDecision("high", True, "high-risk claim")
    if risk_level == "medium":
        return RiskDecision("medium", False, "medium-risk claim skipped in Commit 5")
    if risk_level == "low":
        return RiskDecision("low", False, "low-risk claim skipped")

    if _is_high_risk_text(text):
        return RiskDecision("high", True, "testable runtime claim")

    return RiskDecision("low", False, "non-actionable explanation")


def build_test_plan(
    repo_path: str,
    claims: Sequence[Claim],
    ast_index: Mapping[str, object] | None = None,
    *,
    job_id: str | None = None,
    run_owner: str | None = None,
    repo_url: str | None = None,
    max_output_bytes: int = 12000,
) -> TestPlan:
    del ast_index

    claims_by_ref = claim_refs_for_pending_claims(claims)
    requests: list[TestRunRequest] = []
    unverified_claims: list[Claim] = []
    unverified_reasons: dict[str, str] = {}

    for claim_ref, claim in claims_by_ref.items():
        decision = risk_policy_for_claim(claim)
        if decision.risk_level != "high" or not decision.should_verify:
            continue

        target = _target_from_claim(claim)
        if target is None:
            target = _discover_best_test(Path(repo_path), claim.get("text", ""))
        if target is None:
            unverified_claims.append(_claim_with_status(claim, "unverified"))
            unverified_reasons[claim_ref] = "no_test_coverage"
            continue

        framework = _framework_for_target(Path(repo_path), target)
        if framework is None:
            unverified_claims.append(_claim_with_status(claim, "unverified"))
            unverified_reasons[claim_ref] = "ambiguous_test_framework"
            continue

        tool_name = (
            "run_single_test" if _is_single_test_target(target) else _tool_for_framework(framework)
        )
        timeout_seconds = 10.0 if tool_name == "run_single_test" else 20.0
        requests.append(
            TestRunRequest(
                test_ref=f"test-{len(requests)}",
                claim_refs=(claim_ref,),
                framework=framework,
                tool_name=tool_name,
                path=repo_path,
                test_filter=target,
                timeout_seconds=timeout_seconds,
                estimated_runtime_seconds=int(timeout_seconds),
                max_output_bytes=max_output_bytes,
                job_id=job_id,
                run_owner=run_owner,
                repo_url=repo_url,
            )
        )

    return TestPlan(
        claims_by_ref=claims_by_ref,
        requests=tuple(requests),
        unverified_claims=tuple(unverified_claims),
        unverified_reasons=unverified_reasons,
    )


def build_test_approval_payload(test_plan: TestPlan) -> dict[str, object]:
    return {
        "type": "test_approval",
        "request_id": "verifier-test-approval-0",
        "summary": (
            "Verifier wants to run "
            f"{len(test_plan.requests)} focused tests for "
            f"{len(_claim_refs_in_requests(test_plan.requests))} high-risk claims."
        ),
        "claims": [
            _claim_payload(claim_ref, test_plan.claims_by_ref[claim_ref])
            for claim_ref in _claim_refs_in_requests(test_plan.requests)
        ],
        "proposed_tests": [_request_payload(request) for request in test_plan.requests],
        "allowed_actions": ["approve", "skip", "modify_filter"],
    }


def apply_test_approval_decision(
    test_plan: TestPlan,
    decision: Mapping[str, object],
) -> TestPlan | SkipResult:
    action_value = decision.get("action")
    if action_value == "approve":
        return test_plan

    if action_value == "skip":
        reason = decision.get("reason")
        return SkipResult(
            claim_refs=tuple(_claim_refs_in_requests(test_plan.requests)),
            reason=str(reason) if reason is not None else "skipped_by_user",
        )

    if action_value == "modify_filter":
        return _modified_test_plan(test_plan, decision)

    raise ValueError(f"Unsupported verifier HITL action: {action_value}")


def verification_state_from_test_results(
    claims_by_ref: Mapping[str, Claim],
    observations: Mapping[str, TestRunObservation],
    requests: Sequence[TestRunRequest],
    *,
    existing_partial_summaries: Mapping[str, str] | None = None,
    initial_verified_claims: Sequence[Claim] = (),
    initial_test_results: Mapping[str, TestResult] | None = None,
    initial_unverified_claims: Sequence[Claim] = (),
    initial_unverified_reasons: Mapping[str, str] | None = None,
    errors: Sequence[GraphError] = (),
) -> WayfinderState:
    verified_claims: list[Claim] = list(initial_verified_claims)
    unverified_claims: list[Claim] = list(initial_unverified_claims)
    contradicted_claims: list[Claim] = []
    test_results: dict[str, TestResult] = dict(initial_test_results or {})
    summary_reasons: dict[str, str] = dict(initial_unverified_reasons or {})
    result_errors: list[GraphError] = list(errors)

    for request in requests:
        observation = observations[request.test_ref]
        test_results[request.test_ref] = _test_result_from_observation(
            observation,
            claim_ref=",".join(request.claim_refs),
        )
        status = _claim_status_from_observation(observation, request)
        for claim_ref in request.claim_refs:
            claim = _claim_with_status(claims_by_ref[claim_ref], status)
            if status == "verified":
                verified_claims.append(claim)
            elif status == "contradicted":
                contradicted_claims.append(claim)
            else:
                unverified_claims.append(claim)
                summary_reasons[claim_ref] = _unverified_reason_from_observation(
                    observation,
                    request,
                )

        error = _error_from_observation(observation, request)
        if error is not None:
            result_errors.append(error)

    return _verification_state(
        verified_claims=verified_claims,
        unverified_claims=unverified_claims,
        contradicted_claims=contradicted_claims,
        test_results=test_results,
        summary_reasons=summary_reasons,
        existing_partial_summaries=existing_partial_summaries,
        errors=result_errors,
    )


def verifier_state_from_state(
    state: WayfinderState,
    *,
    test_runner: TestRunner | None = None,
    approval_decision: Mapping[str, object] | None = None,
) -> WayfinderState:
    claims = extract_pending_claims_from_state(state)
    partial_summaries = state.get("partial_summaries", {})
    ast_verified_claims = _verified_claims_from_ast_index(state.get("ast_index"))
    ast_test_results = _test_results_from_ast_claims(ast_verified_claims)
    if not claims:
        if ast_verified_claims:
            return _verification_state(
                verified_claims=ast_verified_claims,
                test_results=ast_test_results,
                existing_partial_summaries=partial_summaries,
            )

        return _verification_state(
            existing_partial_summaries=partial_summaries,
            summary_override="Verification summary: no high-risk claims selected.",
        )

    repo_path = _repo_path_from_state(state)
    if repo_path is None:
        unverified_claims = [_claim_with_status(claim, "unverified") for claim in claims]
        return _verification_state(
            verified_claims=ast_verified_claims,
            unverified_claims=unverified_claims,
            test_results=ast_test_results,
            summary_reasons={
                claim_ref: "missing_repo_path"
                for claim_ref in claim_refs_for_pending_claims(claims)
            },
            existing_partial_summaries=partial_summaries,
            errors=[
                {
                    "node": "verifier",
                    "error_type": "missing_repo_path",
                    "message": "verifier requires a local repo path before test execution.",
                    "retryable": False,
                }
            ],
        )

    plan = build_test_plan(
        repo_path,
        claims,
        state.get("ast_index"),
        job_id=state.get("thread_id"),
        run_owner=state.get("user_id"),
        repo_url=state.get("repo_url"),
    )
    if not plan.requests:
        return _verification_state(
            verified_claims=ast_verified_claims,
            unverified_claims=plan.unverified_claims,
            test_results=ast_test_results,
            summary_reasons=plan.unverified_reasons,
            existing_partial_summaries=partial_summaries,
        )

    payload = build_test_approval_payload(plan)
    decision = (
        approval_decision
        if approval_decision is not None
        else cast(
            Mapping[str, object],
            interrupt(payload),
        )
    )

    try:
        approved_plan = apply_test_approval_decision(plan, decision)
    except ValueError as exc:
        return _invalid_approval_state(
            plan=plan,
            message=str(exc),
            existing_partial_summaries=partial_summaries,
        )

    if isinstance(approved_plan, SkipResult):
        return _skipped_plan_state(
            plan=plan,
            skip_result=approved_plan,
            existing_partial_summaries=partial_summaries,
        )

    runner = test_runner or UnavailableTestRunner()
    observations, executed_requests = _run_requests_with_timeout_retry(
        runner,
        approved_plan.requests,
    )
    return verification_state_from_test_results(
        approved_plan.claims_by_ref,
        observations,
        executed_requests,
        existing_partial_summaries=partial_summaries,
        initial_verified_claims=ast_verified_claims,
        initial_test_results=ast_test_results,
        initial_unverified_claims=approved_plan.unverified_claims,
        initial_unverified_reasons=approved_plan.unverified_reasons,
    )


def _verified_claims_from_ast_index(
    ast_index: Mapping[str, object] | None,
) -> tuple[Claim, ...]:
    if ast_index is None:
        return ()

    status = ast_index.get("status")
    if status in ("missing", "unsupported", "tool_error"):
        return ()

    definition = ast_index.get("definition")
    if not _ast_definition_found(definition):
        return ()

    symbol = _ast_symbol(ast_index, definition)
    claims: list[Claim] = [
        _claim_with_status(
            {
                "text": f"{symbol} has AST definition evidence",
                "source_agent": "entry_explainer",
                "risk_level": "low",
                "test_strategy": "skip",
                "test_id": None,
                "status": "pending",
            },
            "verified",
        )
    ]

    definition_location = _ast_definition_location(definition)
    if definition_location is not None:
        claims.append(
            _claim_with_status(
                {
                    "text": f"{symbol} is defined at {definition_location}",
                    "source_agent": "entry_explainer",
                    "risk_level": "low",
                    "test_strategy": "skip",
                    "test_id": None,
                    "status": "pending",
                },
                "verified",
            )
        )

    signature = _ast_signature(ast_index)
    if signature is not None:
        claims.append(
            _claim_with_status(
                {
                    "text": f"{symbol} has signature {signature}",
                    "source_agent": "entry_explainer",
                    "risk_level": "low",
                    "test_strategy": "skip",
                    "test_id": None,
                    "status": "pending",
                },
                "verified",
            )
        )

    return tuple(claims)


def _test_results_from_ast_claims(claims: Sequence[Claim]) -> dict[str, TestResult]:
    return {
        f"ast-evidence-{index}": {
            "status": "passed",
            "output": "Verified from deterministic mcp-ast-explorer evidence.",
            "claim_ref": f"ast-evidence-{index}",
        }
        for index, _claim in enumerate(claims)
    }


def _ast_definition_found(definition: object) -> bool:
    if not isinstance(definition, dict):
        return False

    definition_dict = cast(dict[str, object], definition)
    found = definition_dict.get("found")
    if isinstance(found, bool):
        return found

    return bool(
        definition_dict.get("location")
        or definition_dict.get("path")
        or definition_dict.get("relative_path")
    )


def _ast_symbol(ast_index: Mapping[str, object], definition: object) -> str:
    symbol = ast_index.get("symbol")
    if symbol:
        return str(symbol)

    if isinstance(definition, dict):
        definition_symbol = cast(dict[str, object], definition).get("symbol")
        if definition_symbol:
            return str(definition_symbol)

    return "symbol"


def _ast_definition_location(definition: object) -> str | None:
    if not isinstance(definition, dict):
        return None

    definition_dict = cast(dict[str, object], definition)
    location = definition_dict.get("location")
    if isinstance(location, dict):
        location_dict = cast(dict[str, object], location)
        path = location_dict.get("relative_path") or location_dict.get("path")
        line = location_dict.get("line")
        if path and line:
            return f"{path}:{line}"
        if path:
            return str(path)

    path = definition_dict.get("relative_path") or definition_dict.get("path")
    line = definition_dict.get("line")
    if path and line:
        return f"{path}:{line}"
    if path:
        return str(path)

    return None


def _ast_signature(ast_index: Mapping[str, object]) -> str | None:
    signature = ast_index.get("signature")
    if isinstance(signature, str) and signature.strip():
        return signature.strip()

    if isinstance(signature, dict):
        signature_dict = cast(dict[str, object], signature)
        value = signature_dict.get("signature")
        if isinstance(value, str) and value.strip():
            return value.strip()

    definition = ast_index.get("definition")
    if isinstance(definition, dict):
        definition_signature = cast(dict[str, object], definition).get("signature")
        if isinstance(definition_signature, str) and definition_signature.strip():
            return definition_signature.strip()

    return None


def _repo_path_from_state(state: WayfinderState) -> str | None:
    repo_handle = state.get("repo_handle")
    if repo_handle is None:
        return None
    return str(repo_handle.local_path)


def _normalize_claim(claim: Claim) -> Claim:
    default_risk: RiskLevel = "high" if _is_high_risk_text(claim.get("text", "")) else "low"
    risk_level: RiskLevel = claim.get("risk_level", default_risk)
    test_strategy = claim.get(
        "test_strategy",
        "existing_test" if claim.get("test_id") else "skip",
    )
    return {
        "text": claim.get("text", ""),
        "source_agent": claim.get("source_agent", "entry_explainer"),
        "risk_level": risk_level,
        "test_strategy": test_strategy,
        "test_id": claim.get("test_id"),
        "status": claim.get("status", "pending"),
    }


def _clean_claim_text(raw_line: str) -> str:
    return raw_line.strip().removeprefix("-").strip().rstrip(".")


def _is_testable_summary_line(text: str) -> bool:
    lowered = f" {text.lower()} "
    if any(lowered.strip().startswith(prefix) for prefix in _IGNORED_SUMMARY_PREFIXES):
        return False
    if any(word in lowered for word in _HEDGE_WORDS):
        return False
    return _is_high_risk_text(text)


def _is_high_risk_text(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in _RUNTIME_CLAIM_KEYWORDS)


def _test_target_from_text(text: str) -> str | None:
    for token in text.replace(",", " ").replace(";", " ").split():
        candidate = token.strip("`'\"()[]")
        if _looks_like_test_target(candidate):
            return candidate
    return None


def _target_from_claim(claim: Claim) -> str | None:
    test_id = claim.get("test_id")
    if isinstance(test_id, str) and test_id.strip():
        return test_id.strip()

    return _test_target_from_text(claim.get("text", ""))


_DISCOVERY_STOPWORDS = frozenset(
    {
        "does",
        "what",
        "when",
        "this",
        "that",
        "with",
        "from",
        "into",
        "test",
        "tests",
        "function",
        "method",
        "class",
        "the",
        "and",
        "for",
        "run",
        "report",
        "whether",
        "verify",
        "relevant",
        "suite",
        "across",
        "using",
        "their",
        "there",
        "about",
        "http",
        "https",
    }
)


def _claim_stems(text: str) -> set[str]:
    """Meaningful lowercase word-stems from a claim, for test-name matching."""
    stems: set[str] = set()
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_]+", text.lower()):
        for part in token.split("_"):
            if len(part) >= 4 and part not in _DISCOVERY_STOPWORDS:
                stems.add(part)
    return stems


def _test_function_names(repo_path: Path) -> list[str]:
    """Collect lowercase `test_*` function names from the repo's test dirs."""
    names: list[str] = []
    seen: set[Path] = set()
    for root in (repo_path / "tests", repo_path / "test"):
        if not root.is_dir():
            continue
        for pattern in ("test_*.py", "*_test.py"):
            for path in sorted(root.rglob(pattern))[:300]:
                if path in seen:
                    continue
                seen.add(path)
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                names.extend(
                    match.group(1).lower()
                    for match in re.finditer(r"def (test_[A-Za-z0-9_]+)", content)
                )
    return names


def _discover_best_test(repo_path: Path, text: str) -> str | None:
    """Autonomously map a behavioural claim to the most relevant repo test.

    Matches claim word-stems against test-function-name tokens (prefix-aware) and
    returns the single best `test_*` name as a pytest ``-k`` filter. Requires at
    least two shared stems so only a confidently-related test is executed.
    """
    stems = _claim_stems(text)
    if not stems:
        return None

    best_name: str | None = None
    best_score = 0
    for name in set(_test_function_names(repo_path)):
        name_words = {word for word in name.split("_") if word}
        score = sum(
            1
            for stem in stems
            if any(
                stem == word
                or (len(word) >= 4 and (stem.startswith(word) or word.startswith(stem)))
                for word in name_words
            )
        )
        if score > best_score:
            best_score = score
            best_name = name

    if best_name is None or best_score < 2:
        return None
    return best_name


def _framework_for_target(repo_path: Path, target: str) -> Framework | None:
    if target.startswith("jest:"):
        return "jest"
    if ".py" in target or "::" in target:
        return "pytest"
    if _repo_has_jest_indicators(repo_path):
        return "jest"
    if _repo_has_pytest_indicators(repo_path):
        return "pytest"
    return None


def _repo_has_pytest_indicators(repo_path: Path) -> bool:
    return any(
        (repo_path / name).exists() for name in ("pyproject.toml", "pytest.ini", "tox.ini", "tests")
    )


def _repo_has_jest_indicators(repo_path: Path) -> bool:
    package_json = repo_path / "package.json"
    return package_json.exists()


def _looks_like_test_target(candidate: str) -> bool:
    return (
        candidate.startswith("jest:")
        or "::" in candidate
        or candidate.startswith("tests/")
        or candidate.endswith(".test.js")
        or candidate.endswith(".spec.js")
    )


def _is_single_test_target(target: str) -> bool:
    return target.startswith("jest:") or "::" in target


def _tool_for_framework(framework: Framework) -> TestToolName:
    return "run_pytest" if framework == "pytest" else "run_jest"


def _claim_with_status(claim: Claim, status: ClaimStatus) -> Claim:
    result = cast(Claim, dict(claim))
    result["status"] = status
    return result


def _claim_refs_in_requests(requests: Sequence[TestRunRequest]) -> list[str]:
    refs: list[str] = []
    for request in requests:
        for claim_ref in request.claim_refs:
            if claim_ref not in refs:
                refs.append(claim_ref)
    return refs


def _claim_payload(claim_ref: str, claim: Claim) -> dict[str, object]:
    return {
        "claim_ref": claim_ref,
        "text": claim.get("text", ""),
        "risk_level": claim.get("risk_level", "high"),
        "source_agent": claim.get("source_agent", "entry_explainer"),
        "test_strategy": claim.get("test_strategy", "skip"),
        "test_id": claim.get("test_id"),
    }


def _request_payload(request: TestRunRequest) -> dict[str, object]:
    return {
        "test_ref": request.test_ref,
        "claim_refs": list(request.claim_refs),
        "framework": request.framework,
        "tool_name": request.tool_name,
        "path": request.path,
        "test_filter": request.test_filter,
        "timeout_seconds": request.timeout_seconds,
        "estimated_runtime_seconds": request.estimated_runtime_seconds,
        "max_output_bytes": request.max_output_bytes,
        "job_id": request.job_id,
        "run_owner": request.run_owner,
        "repo_url": request.repo_url,
    }


def _modified_test_plan(test_plan: TestPlan, decision: Mapping[str, object]) -> TestPlan:
    modifications = decision.get("modifications")
    if not isinstance(modifications, list):
        raise ValueError("modify_filter decision requires modifications")

    requests_by_ref = {request.test_ref: request for request in test_plan.requests}
    for modification in modifications:
        if not isinstance(modification, dict):
            raise ValueError("modify_filter modification must be an object")

        modification_dict = cast(dict[str, object], modification)
        test_ref = modification_dict.get("test_ref")
        new_filter = modification_dict.get("test_filter")
        if not isinstance(test_ref, str) or test_ref not in requests_by_ref:
            raise ValueError("modify_filter referenced an unknown test_ref")
        if not isinstance(new_filter, str) or not new_filter.strip():
            raise ValueError("modify_filter requires a non-empty test_filter")

        timeout = modification_dict.get("timeout_seconds")
        timeout_seconds = (
            float(timeout)
            if isinstance(timeout, int | float) and float(timeout) > 0
            else requests_by_ref[test_ref].timeout_seconds
        )
        requests_by_ref[test_ref] = replace(
            requests_by_ref[test_ref],
            test_filter=new_filter.strip(),
            timeout_seconds=timeout_seconds,
            estimated_runtime_seconds=int(timeout_seconds),
        )

    return TestPlan(
        claims_by_ref=test_plan.claims_by_ref,
        requests=tuple(requests_by_ref[request.test_ref] for request in test_plan.requests),
        unverified_claims=test_plan.unverified_claims,
        unverified_reasons=test_plan.unverified_reasons,
    )


def _test_execution_call(request: TestRunRequest) -> MCPToolCall:
    if request.tool_name == "run_single_test":
        return MCPToolCall(
            tool_name="run_single_test",
            arguments={
                "path": request.path,
                "test_id": request.test_filter.removeprefix("jest:"),
                "framework": request.framework,
                "timeout_seconds": request.timeout_seconds,
            },
        )

    return MCPToolCall(
        tool_name=request.tool_name,
        arguments={
            "path": request.path,
            "test_filter": request.test_filter.removeprefix("jest:"),
            "timeout_seconds": request.timeout_seconds,
        },
    )


def _stdout_for_parse(
    command_result: Mapping[str, object],
    request: TestRunRequest,
) -> str | None:
    stdout = command_result.get("stdout")
    if isinstance(stdout, str) and _looks_like_json(stdout):
        return stdout

    report_file = ".pytest-report.json" if request.framework == "pytest" else ".jest-report.json"
    report_path = Path(request.path) / report_file
    if report_path.exists():
        return report_path.read_text(encoding="utf-8")

    return None


def _looks_like_json(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("{") and stripped.endswith("}")


def _command_output(command_result: Mapping[str, object]) -> str:
    stdout = command_result.get("stdout")
    stderr = command_result.get("stderr")
    parts = [str(part) for part in (stdout, stderr) if part]
    return "\n".join(parts)


def _observation_from_parsed_result(
    *,
    request: TestRunRequest,
    parsed: Mapping[str, object],
    fallback_output: str,
) -> TestRunObservation:
    passed = _int_value(parsed.get("passed"))
    failed = _int_value(parsed.get("failed"))
    skipped = _int_value(parsed.get("skipped"))
    failures = _failure_ids(parsed.get("failures"))
    if failed == 0 and passed == 0 and skipped == 0 and " passed" in fallback_output:
        passed = 1

    if failed > 0:
        return TestRunObservation(
            test_ref=request.test_ref,
            status="failed",
            output=fallback_output,
            passed=passed,
            failed=failed,
            skipped=skipped,
            failures=tuple(failures),
        )

    return TestRunObservation(
        test_ref=request.test_ref,
        status="passed",
        output=fallback_output,
        passed=passed,
        failed=failed,
        skipped=skipped,
        failures=tuple(failures),
    )


def _observation_from_exit_code(
    request: TestRunRequest,
    command_result: Mapping[str, object],
) -> TestRunObservation:
    exit_code = command_result.get("exit_code")
    if exit_code == 0:
        return TestRunObservation(
            test_ref=request.test_ref,
            status="passed",
            output=_command_output(command_result) or "test command exited 0",
            passed=1,
        )

    return TestRunObservation(
        test_ref=request.test_ref,
        status="malformed",
        output=(
            _command_output(command_result)
            or f"test command returned unparseable output with exit_code={exit_code}"
        ),
    )


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return 0


def _failure_ids(failures: object) -> list[str]:
    if not isinstance(failures, list):
        return []
    result: list[str] = []
    for failure in cast(list[object], failures):
        if not isinstance(failure, dict):
            continue
        failure_dict = cast(dict[str, object], failure)
        test_id = failure_dict.get("test_id")
        if test_id is not None:
            result.append(str(test_id))
    return result


def _run_requests_with_timeout_retry(
    runner: TestRunner,
    requests: Sequence[TestRunRequest],
) -> tuple[dict[str, TestRunObservation], tuple[TestRunRequest, ...]]:
    observations: dict[str, TestRunObservation] = {}
    executed_requests: list[TestRunRequest] = []
    for request in requests:
        observation = runner.run_test(request)
        final_request = request
        if observation.status == "timed_out":
            retry_request = replace(
                request,
                timeout_seconds=request.timeout_seconds * 2,
                estimated_runtime_seconds=int(request.timeout_seconds * 2),
            )
            observation = runner.run_test(retry_request)
            final_request = retry_request

        observations[request.test_ref] = observation
        executed_requests.append(final_request)

    return observations, tuple(executed_requests)


def _claim_status_from_observation(
    observation: TestRunObservation,
    request: TestRunRequest,
) -> ClaimStatus:
    if observation.status == "passed":
        return "verified"
    if observation.status == "failed":
        if _failed_observation_matches_request(observation, request):
            return "contradicted"
        return "unverified"
    return "unverified"


def _failed_observation_matches_request(
    observation: TestRunObservation,
    request: TestRunRequest,
) -> bool:
    if not observation.failures:
        return True
    normalized_filter = request.test_filter.removeprefix("jest:")
    return any(
        normalized_filter in failure or failure in normalized_filter
        for failure in observation.failures
    )


def _unverified_reason_from_observation(
    observation: TestRunObservation,
    request: TestRunRequest,
) -> str:
    if observation.status == "failed" and not _failed_observation_matches_request(
        observation,
        request,
    ):
        return "test_suite_failed_unrelated"
    if observation.status == "timed_out":
        return "validation_timed_out"
    if observation.status == "malformed":
        return "malformed_test_output"
    if observation.status == "tool_error":
        return "test_runner_unavailable"
    return "unverified"


def _test_result_from_observation(
    observation: TestRunObservation,
    *,
    claim_ref: str,
) -> TestResult:
    status: Literal["passed", "failed", "skipped", "timed_out"]
    if observation.status == "passed":
        status = "passed"
    elif observation.status == "failed":
        status = "failed"
    elif observation.status == "timed_out":
        status = "timed_out"
    else:
        status = "skipped"

    return {"status": status, "output": observation.output, "claim_ref": claim_ref}


def _error_from_observation(
    observation: TestRunObservation,
    request: TestRunRequest,
) -> GraphError | None:
    if observation.status == "failed" and not _failed_observation_matches_request(
        observation,
        request,
    ):
        return {
            "node": "verifier",
            "error_type": "test_suite_failed_unrelated",
            "message": observation.output,
            "retryable": False,
        }

    if observation.status not in ("timed_out", "malformed", "tool_error"):
        return None
    error_type_by_status: dict[ObservationStatus, str] = {
        "timed_out": "validation_timed_out",
        "malformed": "malformed_test_output",
        "tool_error": "test_runner_unavailable",
        "passed": "none",
        "failed": "none",
    }
    return {
        "node": "verifier",
        "error_type": error_type_by_status[observation.status],
        "message": observation.output,
        "retryable": observation.status == "timed_out",
    }


def _verification_state(
    *,
    verified_claims: Sequence[Claim] = (),
    unverified_claims: Sequence[Claim] = (),
    contradicted_claims: Sequence[Claim] = (),
    test_results: Mapping[str, TestResult] | None = None,
    summary_reasons: Mapping[str, str] | None = None,
    existing_partial_summaries: Mapping[str, str] | None = None,
    errors: Sequence[GraphError] = (),
    summary_override: str | None = None,
) -> WayfinderState:
    partial_summaries = dict(existing_partial_summaries or {})
    partial_summaries["verifier"] = summary_override or _verification_summary(
        verified_count=len(verified_claims),
        unverified_count=len(unverified_claims),
        contradicted_count=len(contradicted_claims),
        reasons=summary_reasons or {},
    )
    return {
        "pending_claims": [],
        "verified_claims": list(verified_claims),
        "unverified_claims": list(unverified_claims),
        "contradicted_claims": list(contradicted_claims),
        "test_results": dict(test_results or {}),
        "partial_summaries": partial_summaries,
        "errors": list(errors),
        "next_agent": "final_writer",
    }


def _verification_summary(
    *,
    verified_count: int,
    unverified_count: int,
    contradicted_count: int,
    reasons: Mapping[str, str],
) -> str:
    parts = [
        "Verification summary:",
        f"{verified_count} verified",
        f"{unverified_count} unverified",
        f"{contradicted_count} contradicted",
    ]
    if reasons:
        reason_text = ", ".join(
            f"{claim_ref}={reason}" for claim_ref, reason in sorted(reasons.items())
        )
        parts.append(f"reasons: {reason_text}")
    return "; ".join(parts) + "."


def _invalid_approval_state(
    *,
    plan: TestPlan,
    message: str,
    existing_partial_summaries: Mapping[str, str],
) -> WayfinderState:
    claim_refs = _claim_refs_in_requests(plan.requests)
    return _verification_state(
        unverified_claims=[
            _claim_with_status(plan.claims_by_ref[claim_ref], "unverified")
            for claim_ref in claim_refs
        ],
        summary_reasons={claim_ref: "invalid_test_filter" for claim_ref in claim_refs},
        existing_partial_summaries=existing_partial_summaries,
        errors=[
            {
                "node": "verifier",
                "error_type": "invalid_test_filter",
                "message": message,
                "retryable": False,
            }
        ],
    )


def _skipped_plan_state(
    *,
    plan: TestPlan,
    skip_result: SkipResult,
    existing_partial_summaries: Mapping[str, str],
) -> WayfinderState:
    return _verification_state(
        unverified_claims=[
            _claim_with_status(plan.claims_by_ref[claim_ref], "unverified")
            for claim_ref in skip_result.claim_refs
        ],
        summary_reasons={
            claim_ref: skip_result.reason or "skipped_by_user"
            for claim_ref in skip_result.claim_refs
        },
        existing_partial_summaries=existing_partial_summaries,
    )
