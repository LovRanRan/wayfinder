"""Grounded final-answer synthesis helpers."""

from __future__ import annotations

import json
from typing import Protocol, cast

from wayfinder.graph.community_context import CommunityContextProvider, community_context_summary
from wayfinder.graph.llm import LLMCallError, LLMClient
from wayfinder.graph.state import CommunityContextItem, GraphError, WayfinderState


class FinalSynthesizer(Protocol):
    def synthesize(
        self,
        *,
        state: WayfinderState,
        deterministic_output: str,
    ) -> str: ...


class LLMFinalSynthesizer:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def synthesize(
        self,
        *,
        state: WayfinderState,
        deterministic_output: str,
    ) -> str:
        return self._client.complete(
            instructions=_SYNTHESIS_INSTRUCTIONS,
            input_text=json.dumps(
                grounded_synthesis_packet(
                    state=state,
                    deterministic_output=deterministic_output,
                ),
                indent=2,
                sort_keys=True,
            ),
        )


def collect_community_context_for_state(
    state: WayfinderState,
    provider: CommunityContextProvider | None,
) -> WayfinderState:
    if provider is None:
        return state

    try:
        items = provider.collect(state)
    except Exception as exc:
        return _state_with_added_error(
            state,
            {
                "node": "community_context",
                "error_type": "community_context_unavailable",
                "message": str(exc) or type(exc).__name__,
                "retryable": True,
            },
        )

    partial_summaries = dict(state.get("partial_summaries", {}))
    partial_summaries["community_context"] = community_context_summary(items)

    updated = dict(state)
    updated["community_context"] = items
    updated["partial_summaries"] = partial_summaries
    return cast(WayfinderState, updated)


def synthesize_or_fallback(
    *,
    state: WayfinderState,
    deterministic_output: str,
    synthesizer: FinalSynthesizer | None,
) -> tuple[str, WayfinderState]:
    if synthesizer is None:
        return deterministic_output, state

    try:
        synthesized = synthesizer.synthesize(
            state=state,
            deterministic_output=deterministic_output,
        ).strip()
    except (LLMCallError, RuntimeError, ValueError) as exc:
        return deterministic_output, _state_with_added_error(
            state,
            {
                "node": "final_writer",
                "error_type": "llm_synthesis_unavailable",
                "message": str(exc) or type(exc).__name__,
                "retryable": isinstance(exc, LLMCallError),
            },
        )

    if not synthesized:
        return deterministic_output, _state_with_added_error(
            state,
            {
                "node": "final_writer",
                "error_type": "llm_synthesis_empty",
                "message": "LLM final writer returned empty text.",
                "retryable": True,
            },
        )

    return synthesized, state


def grounded_synthesis_packet(
    *,
    state: WayfinderState,
    deterministic_output: str,
) -> dict[str, object]:
    return {
        "query": state.get("query", ""),
        "repo_url": state.get("repo_url", ""),
        "conversation_memory": state.get("conversation_memory", ""),
        "route_decision": state.get("route_decision"),
        "repo_metadata": state.get("repo_metadata", {}),
        "module_dep_graph": state.get("module_dep_graph"),
        "entry_points": state.get("entry_points"),
        "ast_index": state.get("ast_index"),
        "partial_summaries": state.get("partial_summaries", {}),
        "verified_claims": state.get("verified_claims", []),
        "unverified_claims": state.get("unverified_claims", []),
        "contradicted_claims": state.get("contradicted_claims", []),
        "test_results": state.get("test_results", {}),
        "community_context": _community_context_payload(
            state.get("community_context", [])
        ),
        "errors": state.get("errors", []),
        "deterministic_fallback": deterministic_output,
        "grounding_policy": {
            "primary_code_facts": "Project 5 MCP evidence and verifier labels",
            "community_context": "supporting context only; never verified code facts",
            "conversation_memory": "continuity context only; never verified code facts",
            "must_label_uncertainty": True,
        },
    }


def _community_context_payload(
    items: list[CommunityContextItem],
) -> list[dict[str, str | None]]:
    return [
        {
            "source": item["source"],
            "title": item["title"],
            "snippet": item["snippet"],
            "url": item["url"],
        }
        for item in items
    ]


def _state_with_added_error(
    state: WayfinderState,
    error: GraphError,
) -> WayfinderState:
    updated = dict(state)
    updated["errors"] = [*state.get("errors", []), error]
    return cast(WayfinderState, updated)


_SYNTHESIS_INSTRUCTIONS = """
You are Wayfinder, a grounded codebase onboarding copilot.

Write a concise answer for an engineer entering this repository.

Rules:
- Use Project 5 MCP repository/AST/test evidence as the primary code facts.
- Do not invent files, functions, modules, tests, or behavior that are not in
  the packet.
- State verified claims confidently only when they appear under verified_claims.
- Label unverified runtime/data-flow claims as unverified.
- Do not restate contradicted claims as true.
- Treat community_context as external supporting context only.
- Treat conversation_memory as continuity context only. Do not quote the raw
  memory packet unless the user explicitly asks for a transcript.
- Mention important limitations when errors or unverified claims exist.
""".strip()
