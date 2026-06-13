"""Tests for distinct agent role contracts (Commit 23, slice 1)."""

from typing import cast

import pytest

from wayfinder.graph.agents import (
    AGENT_ROLES,
    AgentRoleName,
    get_agent_role,
    worker_role_names,
)


def test_all_six_roles_exist() -> None:
    expected = {
        "conversation_memory",
        "supervisor",
        "repo_cartographer",
        "symbol_investigator",
        "verification",
        "final_synthesizer",
    }
    assert set(AGENT_ROLES) == expected


def test_system_prompts_are_distinct() -> None:
    prompts = [role.system_prompt for role in AGENT_ROLES.values()]
    assert len(prompts) == len(set(prompts))


def test_each_role_name_matches_its_key() -> None:
    for key, role in AGENT_ROLES.items():
        assert role.name == key


def test_graph_node_mapping_for_existing_workers() -> None:
    assert AGENT_ROLES["repo_cartographer"].graph_node == "architect_mapper"
    assert AGENT_ROLES["symbol_investigator"].graph_node == "entry_explainer"
    assert AGENT_ROLES["verification"].graph_node == "verifier"
    assert AGENT_ROLES["final_synthesizer"].graph_node == "final_writer"


def test_new_roles_have_no_graph_node_yet() -> None:
    assert AGENT_ROLES["conversation_memory"].graph_node is None
    assert AGENT_ROLES["supervisor"].graph_node == "supervisor"


def test_least_privilege_tools() -> None:
    assert AGENT_ROLES["repo_cartographer"].allowed_tools == ("mcp-repo-mapper",)
    assert AGENT_ROLES["symbol_investigator"].allowed_tools == ("mcp-ast-explorer",)
    assert AGENT_ROLES["verification"].allowed_tools == ("mcp-test-runner",)
    assert AGENT_ROLES["conversation_memory"].allowed_tools == ()


def test_get_agent_role_returns_contract() -> None:
    role = get_agent_role("verification")
    assert role.output_contract == "challenge_outcomes"


def test_get_agent_role_raises_on_unknown() -> None:
    with pytest.raises(KeyError):
        get_agent_role(cast(AgentRoleName, "does_not_exist"))


def test_worker_role_names_are_grounding_workers() -> None:
    assert worker_role_names() == ("repo_cartographer", "symbol_investigator")
