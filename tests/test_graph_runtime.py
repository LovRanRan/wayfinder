import pytest

from wayfinder.graph import build_graph
from wayfinder.graph.runtime import (
    architecture_scanner_from_env,
    build_project5_architecture_scanner,
    project5_repo_mapper_config,
)
from wayfinder.mcp.project5 import PROJECT5_MCP_SERVERS


def test_project5_repo_mapper_config_selects_only_repo_mapper() -> None:
    config = project5_repo_mapper_config()

    assert config.name == "repo_mapper"
    assert config.command == "mcp-repo-mapper"
    assert config.transport == "stdio"

    assert {server.name for server in PROJECT5_MCP_SERVERS} == {
        "repo_mapper",
        "ast_explorer",
        "test_runner",
    }


def test_build_project5_architecture_scanner_returns_scanner() -> None:
    scanner = build_project5_architecture_scanner()

    assert hasattr(scanner, "scan_repo")


def test_project5_architecture_scanner_can_be_injected_into_graph() -> None:
    scanner = build_project5_architecture_scanner()
    graph = build_graph(architecture_scanner=scanner)

    assert graph is not None


def test_architecture_scanner_from_env_defaults_to_placeholder() -> None:
    assert architecture_scanner_from_env({}) is None


def test_architecture_scanner_from_env_accepts_placeholder_mode() -> None:
    assert architecture_scanner_from_env({"WAYFINDER_ARCHITECTURE_SCANNER": "placeholder"}) is None


def test_architecture_scanner_from_env_builds_mcp_scanner() -> None:
    scanner = architecture_scanner_from_env({"WAYFINDER_ARCHITECTURE_SCANNER": "mcp"})

    assert scanner is not None
    assert hasattr(scanner, "scan_repo")


def test_architecture_scanner_from_env_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unsupported architecture scanner mode"):
        architecture_scanner_from_env({"WAYFINDER_ARCHITECTURE_SCANNER": "banana"})