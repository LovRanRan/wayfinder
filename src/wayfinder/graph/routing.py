"""Routing decisions for the Wayfinder Supervisor graph."""

import json
from typing import cast

from wayfinder.graph.state import AgentName, Intent, RouteDecision, WayfinderState

_SUPPORTED_INTENTS = {"architectural", "runtime", "behavioral", "debug", "mixed"}


def classify_intent(state: WayfinderState) -> Intent:
    """Classify the user's query before selecting the next agent."""
    query = state.get("query", "").lower()

    # TODO: Replace keyword rules with the final deterministic routing policy.
    if any(word in query for word in ("architecture", "structure", "module", "overview")):
        return "architectural"

    if any(word in query for word in ("run", "runtime", "start", "entrypoint")):
        return "runtime"

    if any(word in query for word in ("behavior", "logic", "flow", "function")):
        return "behavioral"

    if any(word in query for word in ("bug", "error", "traceback", "failing")):
        return "debug"

    return "mixed"


def choose_next_agent(intent: Intent) -> AgentName:
    """Map a normalized intent to the placeholder agent that should run next."""
    # TODO: Decide whether runtime should route to entry_explainer or architect_mapper.
    if intent == "architectural":
        return "architect_mapper"

    if intent in ("runtime", "behavioral", "debug"):
        return "entry_explainer"

    return "architect_mapper"


def build_route_decision(state: WayfinderState) -> RouteDecision:
    """Build the state-attached routing decision used by the Supervisor node."""
    corrected_intent = _intent_from_user_corrections(state.get("user_corrections", []))
    if corrected_intent is not None:
        return {
            "intent": corrected_intent,
            "next_agent": choose_next_agent(corrected_intent),
            "source": "user_correction",
            "reason": "accepted user HITL route correction",
            "needs_human_review": False,
        }

    intent = classify_intent(state)
    next_agent = choose_next_agent(intent)

    return {
        "intent": intent,
        "next_agent": next_agent,
        "source": "rule",
        "reason": "matched deterministic keyword routing",
        "needs_human_review": intent == "mixed",
    }


def build_safe_default_route_decision(reason: str) -> RouteDecision:
    """Build a conservative routing fallback that asks for human review."""
    intent: Intent = "mixed"
    return {
        "intent": intent,
        "next_agent": choose_next_agent(intent),
        "source": "safe_default",
        "reason": reason,
        "needs_human_review": True,
    }


def parse_llm_route_decision(raw_response: str) -> RouteDecision:
    """Validate a mocked LLM routing response without making an LLM call."""
    try:
        payload: object = json.loads(raw_response)
    except json.JSONDecodeError:
        return build_safe_default_route_decision("LLM routing response was not valid JSON")

    if not isinstance(payload, dict):
        return build_safe_default_route_decision("LLM routing response was not a JSON object")

    payload_dict = cast(dict[str, object], payload)

    intent_value = payload_dict.get("intent")
    if not isinstance(intent_value, str) or intent_value not in _SUPPORTED_INTENTS:
        return build_safe_default_route_decision("LLM routing response had unsupported intent")

    intent = cast(Intent, intent_value)
    reason_value = payload_dict.get("reason")
    reason = (
        reason_value.strip()
        if isinstance(reason_value, str) and reason_value.strip()
        else "accepted LLM routing response"
    )

    return {
        "intent": intent,
        "next_agent": choose_next_agent(intent),
        "source": "llm",
        "reason": reason,
        "needs_human_review": False,
    }


def _intent_from_user_corrections(corrections: list[str]) -> Intent | None:
    for correction in reversed(corrections):
        lowered = correction.lower()
        for intent in _SUPPORTED_INTENTS:
            if f"intent={intent}" in lowered or f"intent: {intent}" in lowered:
                return cast(Intent, intent)
    return None
