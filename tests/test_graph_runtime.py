from pathlib import Path

import pytest

from wayfinder.graph import build_graph
from wayfinder.graph.runtime import (
    architecture_scanner_from_env,
    build_openai_responses_client,
    build_project5_architecture_scanner,
    build_project5_entry_scanner,
    build_project5_verifier_runner,
    community_context_provider_from_env,
    entry_scanner_from_env,
    env_with_local_dotenv,
    final_synthesizer_from_env,
    llm_router_from_env,
    project5_ast_explorer_config,
    project5_ast_explorer_http_config,
    project5_repo_mapper_config,
    project5_repo_mapper_http_config,
    project5_test_runner_config,
    verifier_runner_from_env,
    verifier_sandbox_policy_from_env,
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


def test_project5_ast_explorer_config_selects_only_ast_explorer() -> None:
    config = project5_ast_explorer_config()

    assert config.name == "ast_explorer"
    assert config.command == "mcp-ast-explorer"
    assert config.transport == "stdio"


def test_project5_test_runner_config_selects_only_test_runner() -> None:
    config = project5_test_runner_config()

    assert config.name == "test_runner"
    assert config.command == "mcp-test-runner"
    assert config.transport == "stdio"


def test_project5_repo_mapper_http_config_selects_only_repo_mapper_url() -> None:
    config = project5_repo_mapper_http_config(
        {
            "WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL": "https://repo-mapper.example/mcp",
            "WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL": "https://ast-explorer.example/mcp",
        }
    )

    assert config.name == "repo_mapper"
    assert config.command is None
    assert config.transport == "streamable_http"
    assert config.url == "https://repo-mapper.example/mcp"


def test_project5_ast_explorer_http_config_selects_only_ast_explorer_url() -> None:
    config = project5_ast_explorer_http_config(
        {
            "WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL": "https://repo-mapper.example/mcp",
            "WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL": "https://ast-explorer.example/mcp",
        }
    )

    assert config.name == "ast_explorer"
    assert config.command is None
    assert config.transport == "streamable_http"
    assert config.url == "https://ast-explorer.example/mcp"


def test_build_project5_architecture_scanner_returns_scanner() -> None:
    scanner = build_project5_architecture_scanner()

    assert hasattr(scanner, "scan_repo")


def test_build_project5_entry_scanner_returns_scanner() -> None:
    scanner = build_project5_entry_scanner()

    assert hasattr(scanner, "explain_symbol")


def test_build_project5_verifier_runner_returns_runner() -> None:
    runner = build_project5_verifier_runner()

    assert hasattr(runner, "run_test")


def test_project5_architecture_scanner_can_be_injected_into_graph() -> None:
    scanner = build_project5_architecture_scanner()
    graph = build_graph(architecture_scanner=scanner)

    assert graph is not None


def test_project5_entry_scanner_can_be_injected_into_graph() -> None:
    scanner = build_project5_entry_scanner()
    graph = build_graph(entry_scanner=scanner)

    assert graph is not None


def test_project5_verifier_runner_can_be_injected_into_graph() -> None:
    runner = build_project5_verifier_runner()
    graph = build_graph(verifier_runner=runner)

    assert graph is not None


def test_architecture_scanner_from_env_defaults_to_placeholder() -> None:
    assert architecture_scanner_from_env({}) is None


def test_architecture_scanner_from_env_accepts_placeholder_mode() -> None:
    assert architecture_scanner_from_env({"WAYFINDER_ARCHITECTURE_SCANNER": "placeholder"}) is None


def test_architecture_scanner_from_env_builds_mcp_scanner() -> None:
    scanner = architecture_scanner_from_env({"WAYFINDER_ARCHITECTURE_SCANNER": "mcp"})

    assert scanner is not None
    assert hasattr(scanner, "scan_repo")


def test_architecture_scanner_from_env_builds_mcp_http_scanner() -> None:
    scanner = architecture_scanner_from_env(
        {
            "WAYFINDER_ARCHITECTURE_SCANNER": "mcp_http",
            "WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL": "https://repo-mapper.example/mcp",
        }
    )

    assert scanner is not None
    assert hasattr(scanner, "scan_repo")


def test_architecture_scanner_from_env_requires_mcp_http_url() -> None:
    with pytest.raises(ValueError, match="WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL"):
        architecture_scanner_from_env({"WAYFINDER_ARCHITECTURE_SCANNER": "mcp_http"})


def test_architecture_scanner_from_env_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unsupported architecture scanner mode"):
        architecture_scanner_from_env({"WAYFINDER_ARCHITECTURE_SCANNER": "banana"})


def test_entry_scanner_from_env_defaults_to_placeholder() -> None:
    assert entry_scanner_from_env({}) is None


def test_entry_scanner_from_env_accepts_placeholder_mode() -> None:
    assert entry_scanner_from_env({"WAYFINDER_ENTRY_SCANNER": "placeholder"}) is None


def test_entry_scanner_from_env_builds_mcp_scanner() -> None:
    scanner = entry_scanner_from_env({"WAYFINDER_ENTRY_SCANNER": "mcp"})

    assert scanner is not None
    assert hasattr(scanner, "explain_symbol")


def test_entry_scanner_from_env_builds_mcp_http_scanner() -> None:
    scanner = entry_scanner_from_env(
        {
            "WAYFINDER_ENTRY_SCANNER": "mcp_http",
            "WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL": "https://ast-explorer.example/mcp",
        }
    )

    assert scanner is not None
    assert hasattr(scanner, "explain_symbol")


def test_entry_scanner_from_env_requires_mcp_http_url() -> None:
    with pytest.raises(ValueError, match="WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL"):
        entry_scanner_from_env({"WAYFINDER_ENTRY_SCANNER": "mcp_http"})


def test_entry_scanner_from_env_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unsupported entry scanner mode"):
        entry_scanner_from_env({"WAYFINDER_ENTRY_SCANNER": "banana"})


def test_verifier_runner_from_env_defaults_to_placeholder() -> None:
    assert verifier_runner_from_env({}) is None


def test_verifier_runner_from_env_accepts_placeholder_mode() -> None:
    assert verifier_runner_from_env({"WAYFINDER_VERIFIER_RUNNER": "placeholder"}) is None


def test_verifier_runner_from_env_sandboxed_mcp_is_policy_gated() -> None:
    assert verifier_runner_from_env({"WAYFINDER_VERIFIER_RUNNER": "sandboxed_mcp"}) is None


def test_verifier_runner_from_env_builds_mcp_runner() -> None:
    runner = verifier_runner_from_env({"WAYFINDER_VERIFIER_RUNNER": "mcp"})

    assert runner is not None
    assert hasattr(runner, "run_test")


def test_verifier_runner_from_env_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unsupported verifier runner mode"):
        verifier_runner_from_env({"WAYFINDER_VERIFIER_RUNNER": "banana"})


def test_verifier_sandbox_policy_reports_disabled_default() -> None:
    policy = verifier_sandbox_policy_from_env({"WAYFINDER_VERIFIER_RUNNER": "placeholder"})

    assert policy.status == "disabled"
    assert "disabled" in policy.message


def test_verifier_sandbox_policy_requires_url_and_health_gate() -> None:
    missing_url = verifier_sandbox_policy_from_env({"WAYFINDER_VERIFIER_RUNNER": "sandboxed_mcp"})
    unhealthy = verifier_sandbox_policy_from_env(
        {
            "WAYFINDER_VERIFIER_RUNNER": "sandboxed_mcp",
            "WAYFINDER_TEST_SANDBOX_URL": "https://sandbox.example",
        }
    )
    adapter_missing = verifier_sandbox_policy_from_env(
        {
            "WAYFINDER_VERIFIER_RUNNER": "sandboxed_mcp",
            "WAYFINDER_TEST_SANDBOX_URL": "https://sandbox.example",
            "WAYFINDER_TEST_SANDBOX_HEALTH": "ok",
        }
    )

    assert missing_url.status == "unavailable"
    assert "URL" in missing_url.message
    assert unhealthy.status == "unavailable"
    assert "health" in unhealthy.message
    assert adapter_missing.status == "unavailable"
    assert "no remote sandbox adapter" in adapter_missing.message


def test_env_with_local_dotenv_loads_missing_values(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "OPENAI_API_KEY=sk-test-local\nWAYFINDER_FINAL_WRITER=openai\n",
        encoding="utf-8",
    )

    env = env_with_local_dotenv({"OPENAI_API_KEY": "sk-process"}, dotenv_path=dotenv_path)

    assert env["OPENAI_API_KEY"] == "sk-process"
    assert env["WAYFINDER_FINAL_WRITER"] == "openai"


def test_openai_client_from_env_uses_model_override() -> None:
    client = build_openai_responses_client(
        {
            "OPENAI_API_KEY": "sk-test",
            "WAYFINDER_OPENAI_MODEL": "test-model",
        }
    )

    assert client.model == "test-model"


def test_openai_client_from_env_requires_key() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_openai_responses_client({})


def test_llm_router_from_env_defaults_off() -> None:
    assert llm_router_from_env({}) is None


def test_llm_router_from_env_builds_openai_router() -> None:
    router = llm_router_from_env(
        {
            "WAYFINDER_LLM_ROUTING": "openai",
            "OPENAI_API_KEY": "sk-test",
        }
    )

    assert router is not None
    assert hasattr(router, "route")


def test_final_synthesizer_from_env_defaults_deterministic() -> None:
    assert final_synthesizer_from_env({}) is None


def test_final_synthesizer_from_env_builds_openai_synthesizer() -> None:
    synthesizer = final_synthesizer_from_env(
        {
            "WAYFINDER_FINAL_WRITER": "openai",
            "OPENAI_API_KEY": "sk-test",
        }
    )

    assert synthesizer is not None
    assert hasattr(synthesizer, "synthesize")


def test_community_context_provider_from_env_defaults_off() -> None:
    assert community_context_provider_from_env({}) is None


def test_community_context_provider_from_env_builds_mcp_provider() -> None:
    provider = community_context_provider_from_env(
        {
            "WAYFINDER_COMMUNITY_CONTEXT": "mcp",
            "TAVILY_API_KEY": "test-tavily",
            "GITHUB_PERSONAL_ACCESS_TOKEN": "test-github",
        }
    )

    assert provider is not None
    assert hasattr(provider, "collect")
