"""Distinct role contracts for the Wayfinder multi-agent graph (Commit 23).

Each agent has its own mission, system prompt, least-privilege tool surface, and
output contract. Splitting these contracts is the foundation of true
multi-agent behaviour: distinct prompts per worker instead of one shared
persona. This module is additive — it does not change graph wiring — so the
existing graph and tests are untouched.
"""

from dataclasses import dataclass
from typing import Literal

AgentRoleName = Literal[
    "conversation_memory",
    "supervisor",
    "repo_cartographer",
    "symbol_investigator",
    "verification",
    "final_synthesizer",
]


@dataclass(frozen=True)
class AgentRole:
    """A single agent's distinct identity and contract."""

    name: AgentRoleName
    mission: str
    system_prompt: str
    allowed_tools: tuple[str, ...]
    output_contract: str
    # The existing compiled-graph node this role maps onto today, if any.
    # `None` for roles that do not yet have a dedicated node (conversation,
    # supervisor planning); slice 2 uses this map when rewiring the graph.
    graph_node: str | None


AGENT_ROLES: dict[AgentRoleName, AgentRole] = {
    "conversation_memory": AgentRole(
        name="conversation_memory",
        mission=(
            "Hold the repo conversation context and bounded memory so follow-up "
            "questions resolve against the active repo without re-grounding."
        ),
        system_prompt=(
            "You are Wayfinder's conversation and memory agent. You never invent "
            "code facts. You resolve the active repo/thread, summarise prior turns "
            "into bounded memory, and decide whether a new question needs grounding "
            "or can be answered from existing evidence."
        ),
        allowed_tools=(),
        output_contract="conversation_memory_update",
        graph_node=None,
    ),
    "supervisor": AgentRole(
        name="supervisor",
        mission=(
            "Classify intent and plan which worker agents must run for one "
            "question, deterministic rule first and LLM fallback second."
        ),
        system_prompt=(
            "You are Wayfinder's supervisor. You do not answer questions yourself. "
            "You classify intent (architectural / runtime / behavioral / debug / "
            "mixed) and produce a plan of one or more workers to run. Prefer the "
            "deterministic rule; only fall back to the LLM for ambiguous queries."
        ),
        allowed_tools=(),
        output_contract="route_plan",
        graph_node="supervisor",
    ),
    "repo_cartographer": AgentRole(
        name="repo_cartographer",
        mission=(
            "Map repo structure: dependency graph, language breakdown, "
            "frameworks, and entry points, grounded in mcp-repo-mapper."
        ),
        system_prompt=(
            "You are Wayfinder's repo cartographer. Use only mcp-repo-mapper "
            "evidence. Describe architecture and entry points, and state plainly "
            "what the structure scan cannot prove. Emit claim packets, not prose."
        ),
        allowed_tools=("mcp-repo-mapper",),
        output_contract="claim_packets",
        graph_node="architect_mapper",
    ),
    "symbol_investigator": AgentRole(
        name="symbol_investigator",
        mission=(
            "Resolve symbols: definitions, signatures, references, and call "
            "chains, grounded in mcp-ast-explorer with a hard anti-hallucination "
            "gate."
        ),
        system_prompt=(
            "You are Wayfinder's symbol investigator. Use only mcp-ast-explorer "
            "evidence. Never assert a function or class that the AST cannot "
            "confirm. Emit claim packets with AST evidence and explicit "
            "limitations for anything unproven."
        ),
        allowed_tools=("mcp-ast-explorer",),
        output_contract="claim_packets",
        graph_node="entry_explainer",
    ),
    "verification": AgentRole(
        name="verification",
        mission=(
            "Adversarially verify high-risk claims by running minimal tests, and "
            "downgrade or contradict claims that evidence does not support."
        ),
        system_prompt=(
            "You are Wayfinder's verification agent. You are adversarial. For "
            "high-risk claims you select minimal pytest/jest targets via "
            "mcp-test-runner. A passing test upholds a claim; a failing test "
            "contradicts it; no test coverage downgrades it to unverified. You "
            "never accept a claim on prose alone."
        ),
        allowed_tools=("mcp-test-runner",),
        output_contract="challenge_outcomes",
        graph_node="verifier",
    ),
    "final_synthesizer": AgentRole(
        name="final_synthesizer",
        mission=(
            "Compose the grounded final answer from upheld claims, attach a "
            "provenance trace, and surface verified / unverified / contradicted "
            "counts honestly."
        ),
        system_prompt=(
            "You are Wayfinder's final synthesizer. Compose the answer only from "
            "claim packets and their challenge outcomes. Show which agent made "
            "which claim and how it was resolved. Community context is supporting "
            "only and can never make a code claim verified."
        ),
        allowed_tools=("tavily-mcp", "github-search-mcp"),
        output_contract="final_answer",
        graph_node="final_writer",
    ),
}


def get_agent_role(name: AgentRoleName) -> AgentRole:
    """Return the role contract for ``name`` or raise ``KeyError`` if unknown."""
    try:
        return AGENT_ROLES[name]
    except KeyError as exc:
        raise KeyError(f"unknown agent role: {name!r}") from exc


def worker_role_names() -> tuple[AgentRoleName, ...]:
    """Return the grounding worker roles a supervisor plan can fan out to."""
    return ("repo_cartographer", "symbol_investigator")
