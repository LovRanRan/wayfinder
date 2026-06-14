"""Routing decisions for the Wayfinder Supervisor graph."""

import json
from typing import Protocol, cast

from wayfinder.graph.llm import LLMClient
from wayfinder.graph.state import AgentName, Intent, RouteDecision, WayfinderState

_SUPPORTED_INTENTS = {"architectural", "runtime", "behavioral", "debug", "mixed"}


class LLMRouter(Protocol):
    def route(self, state: WayfinderState) -> str: ...


class PromptedLLMRouter:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def route(self, state: WayfinderState) -> str:
        return self._client.complete(
            instructions=_ROUTING_INSTRUCTIONS,
            input_text=json.dumps(
                {
                    "query": state.get("query", ""),
                    "repo_url": state.get("repo_url", ""),
                    "user_corrections": state.get("user_corrections", []),
                },
                sort_keys=True,
            ),
        )


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
    """Map a normalized intent to the first grounding agent to run.

    Every non-architectural grounding question starts at ``architect_mapper`` so
    the symbol path has architect_mapper's entry points as a fallback symbol
    candidate before ``entry_explainer`` runs. ``entry_explainer`` is queued as a
    pending worker by ``plan_workers_for_intent`` and reached via
    ``route_after_architect`` — never as the supervisor's first hop. This is what
    prevents empty-evidence answers on symbol/behaviour questions (design note
    021). Architectural questions need only the cartographer, which is also the
    first hop here, so all intents share one entry point into the grounding path.
    """
    del intent  # routing currently always enters via the cartographer
    return "architect_mapper"


def build_route_decision(
    state: WayfinderState,
    *,
    llm_router: LLMRouter | None = None,
) -> RouteDecision:
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
    if intent == "mixed" and llm_router is not None:
        try:
            return parse_llm_route_decision(llm_router.route(state))
        except (RuntimeError, TypeError, ValueError) as exc:
            return build_safe_default_route_decision(
                f"LLM routing fallback unavailable: {exc}"
            )

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


_ROUTING_INSTRUCTIONS = """
Classify a codebase onboarding query into one intent.

Return only JSON with:
- intent: one of architectural, runtime, behavioral, debug, mixed
- reason: one short reason

Definitions:
- architectural: repo structure, modules, overview
- runtime: how to run, start, configure, entrypoint
- behavioral: what a function/class/path does
- debug: errors, tracebacks, failing tests
- mixed: genuinely unclear or broad
""".strip()
