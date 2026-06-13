"""Tests for supervisor multi-worker planning (Commit 23 slice 2, pure logic)."""

from wayfinder.graph.planning import (
    is_multi_worker_plan,
    plan_as_graph_nodes,
    plan_workers_for_intent,
)


def test_architectural_intent_plans_single_cartographer() -> None:
    plan = plan_workers_for_intent("architectural")
    assert plan == ("repo_cartographer",)
    assert is_multi_worker_plan(plan) is False


def test_behavioral_intents_plan_single_investigator() -> None:
    for intent in ("runtime", "behavioral", "debug"):
        plan = plan_workers_for_intent(intent)  # type: ignore[arg-type]
        assert plan == ("symbol_investigator",)
        assert is_multi_worker_plan(plan) is False


def test_mixed_intent_fans_out_to_both_workers() -> None:
    plan = plan_workers_for_intent("mixed")
    assert plan == ("repo_cartographer", "symbol_investigator")
    assert is_multi_worker_plan(plan) is True


def test_plan_as_graph_nodes_translates_roles() -> None:
    plan = plan_workers_for_intent("mixed")
    assert plan_as_graph_nodes(plan) == ("architect_mapper", "entry_explainer")


def test_plan_as_graph_nodes_single() -> None:
    assert plan_as_graph_nodes(("repo_cartographer",)) == ("architect_mapper",)
