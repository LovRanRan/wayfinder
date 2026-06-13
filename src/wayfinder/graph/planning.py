"""Supervisor multi-worker planning (Commit 23 slice 2, pure logic).

The supervisor can plan more than one worker for a single question. This module
is the pure planning policy: intent -> ordered worker plan. It is additive and
does not touch the compiled graph, so existing routing tests are unaffected.
The graph wiring that consumes a plan is a separate, gate-validated step.
"""

from collections.abc import Sequence

from wayfinder.graph.agents import AGENT_ROLES, AgentRoleName
from wayfinder.graph.state import Intent

# Grounding workers a plan may fan out to, in deterministic order.
_CARTOGRAPHER: AgentRoleName = "repo_cartographer"
_INVESTIGATOR: AgentRoleName = "symbol_investigator"


def plan_workers_for_intent(intent: Intent) -> tuple[AgentRoleName, ...]:
    """Return the ordered worker plan for an intent.

    Single intents map to one specialist; ``mixed`` fans out to both grounding
    workers (architecture first, then symbols) so one broad question is answered
    by more than one agent.
    """
    if intent == "architectural":
        return (_CARTOGRAPHER,)
    if intent in ("runtime", "behavioral", "debug"):
        return (_INVESTIGATOR,)
    return (_CARTOGRAPHER, _INVESTIGATOR)


def is_multi_worker_plan(plan: Sequence[AgentRoleName]) -> bool:
    """Return True if the plan fans out to more than one worker."""
    return len(plan) > 1


def plan_as_graph_nodes(plan: Sequence[AgentRoleName]) -> tuple[str, ...]:
    """Translate a worker-role plan into the compiled-graph node names.

    Used by the wiring step to drive the existing ``architect_mapper`` /
    ``entry_explainer`` nodes from a role-level plan. Raises ``ValueError`` if a
    role in the plan has no graph node yet.
    """
    nodes: list[str] = []
    for role in plan:
        graph_node = AGENT_ROLES[role].graph_node
        if graph_node is None:
            raise ValueError(f"agent role {role!r} has no graph node to execute")
        nodes.append(graph_node)
    return tuple(nodes)
