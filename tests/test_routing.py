import pytest

from wayfinder.graph.app import route_from_supervisor
from wayfinder.graph.routing import (
    LLMRouter,
    build_route_decision,
    choose_next_agent,
    classify_intent,
    parse_llm_route_decision,
)
from wayfinder.graph.state import AgentName, Intent, WayfinderState


class FakeLLMRouter:
    def __init__(self, raw_response: str) -> None:
        self.raw_response = raw_response
        self.calls: list[WayfinderState] = []

    def route(self, state: WayfinderState) -> str:
        self.calls.append(state)
        return self.raw_response


class ExplodingLLMRouter:
    def route(self, state: WayfinderState) -> str:
        del state
        raise RuntimeError("llm unavailable")


@pytest.mark.parametrize(
    ("query", "expected_intent"),
    [
        ("Explain the architecture of this repo", "architectural"),
        ("Where does the application start at runtime?", "runtime"),
        ("Explain the behavior of this function", "behavioral"),
        ("Debug this failing traceback", "debug"),
        ("Help me understand this repo", "mixed"),
    ],
)
def test_classify_intent_uses_deterministic_keyword_rules(
    query: str,
    expected_intent: Intent,
) -> None:
    assert classify_intent({"query": query}) == expected_intent


@pytest.mark.parametrize(
    ("intent", "expected_agent"),
    [
        ("architectural", "architect_mapper"),
        ("runtime", "entry_explainer"),
        ("behavioral", "entry_explainer"),
        ("debug", "entry_explainer"),
        ("mixed", "architect_mapper"),
    ],
)
def test_choose_next_agent_maps_intent_to_placeholder_agent(
    intent: Intent,
    expected_agent: AgentName,
) -> None:
    assert choose_next_agent(intent) == expected_agent


def test_build_route_decision_marks_mixed_query_for_human_review() -> None:
    decision = build_route_decision({"query": "Help me understand this repo"})

    assert decision == {
        "intent": "mixed",
        "next_agent": "architect_mapper",
        "source": "rule",
        "reason": "matched deterministic keyword routing",
        "needs_human_review": True,
    }


def test_build_route_decision_uses_llm_router_for_mixed_query() -> None:
    router = FakeLLMRouter(
        '{"intent": "runtime", "reason": "User asks where to start"}'
    )

    decision = build_route_decision(
        {"query": "Where should a new contributor begin?"},
        llm_router=router,
    )

    assert decision == {
        "intent": "runtime",
        "next_agent": "entry_explainer",
        "source": "llm",
        "reason": "User asks where to start",
        "needs_human_review": False,
    }
    assert router.calls == [{"query": "Where should a new contributor begin?"}]


def test_build_route_decision_keeps_rule_hit_without_calling_llm() -> None:
    router: LLMRouter = ExplodingLLMRouter()

    decision = build_route_decision(
        {"query": "Explain the architecture"},
        llm_router=router,
    )

    assert decision["intent"] == "architectural"
    assert decision["source"] == "rule"


def test_build_route_decision_falls_back_when_llm_router_fails() -> None:
    decision = build_route_decision(
        {"query": "Help me understand this repo"},
        llm_router=ExplodingLLMRouter(),
    )

    assert decision["intent"] == "mixed"
    assert decision["next_agent"] == "architect_mapper"
    assert decision["source"] == "safe_default"
    assert decision["needs_human_review"] is True
    assert "LLM routing fallback unavailable" in decision["reason"]


def test_parse_llm_route_decision_accepts_supported_intent_json() -> None:
    decision = parse_llm_route_decision(
        '{"intent": "debug", "reason": "User mentioned traceback"}'
    )

    assert decision == {
        "intent": "debug",
        "next_agent": "entry_explainer",
        "source": "llm",
        "reason": "User mentioned traceback",
        "needs_human_review": False,
    }


def test_parse_llm_route_decision_uses_default_reason_when_reason_is_missing() -> None:
    decision = parse_llm_route_decision('{"intent": "runtime"}')

    assert decision == {
        "intent": "runtime",
        "next_agent": "entry_explainer",
        "source": "llm",
        "reason": "accepted LLM routing response",
        "needs_human_review": False,
    }


@pytest.mark.parametrize(
    "raw_response",
    [
        "not json",
        '["debug"]',
        '{"intent": "security", "reason": "unsupported intent"}',
    ],
)
def test_parse_llm_route_decision_uses_safe_default_for_invalid_response(
    raw_response: str,
) -> None:
    decision = parse_llm_route_decision(raw_response)

    assert decision["intent"] == "mixed"
    assert decision["next_agent"] == "architect_mapper"
    assert decision["source"] == "safe_default"
    assert decision["needs_human_review"] is True


@pytest.mark.parametrize(
    ("state", "expected_agent"),
    [
        ({"next_agent": "architect_mapper"}, "architect_mapper"),
        ({"next_agent": "entry_explainer"}, "entry_explainer"),
        ({"next_agent": "verifier"}, "verifier"),
        ({"next_agent": "final_writer"}, "architect_mapper"),
        ({}, "architect_mapper"),
    ],
)
def test_route_from_supervisor_uses_safe_default_for_invalid_next_agent(
    state: WayfinderState,
    expected_agent: AgentName,
) -> None:
    assert route_from_supervisor(state) == expected_agent
