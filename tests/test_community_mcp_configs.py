import pytest

from wayfinder.mcp.community import (
    NPM_CACHE_DIR,
    build_community_mcp_configs,
    community_primary_tool_names,
    community_required_env_vars,
)


def test_community_configs_declare_external_mcp_entrypoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)

    configs = build_community_mcp_configs()

    assert [config.to_client_config() for config in configs] == [
        {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "tavily-mcp@latest"],
            "env": {
                "NPM_CONFIG_CACHE": NPM_CACHE_DIR,
                "npm_config_cache": NPM_CACHE_DIR,
            },
        },
        {
            "transport": "stdio",
            "command": "docker",
            "args": [
                "run",
                "-i",
                "--rm",
                "-e",
                "GITHUB_PERSONAL_ACCESS_TOKEN",
                "-e",
                "GITHUB_TOOLSETS=repos,issues,pull_requests",
                "-e",
                "GITHUB_READ_ONLY=1",
                "ghcr.io/github/github-mcp-server",
            ],
        },
    ]


def test_community_primary_tool_contract_is_declared() -> None:
    assert community_primary_tool_names() == {
        "tavily_search",
        "search_code",
        "search_issues",
        "search_pull_requests",
    }


def test_community_real_integration_env_requirements_are_documented() -> None:
    assert community_required_env_vars() == {
        "TAVILY_API_KEY",
        "GITHUB_PERSONAL_ACCESS_TOKEN",
    }


def test_community_configs_forward_available_real_integration_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "test-github-token")

    configs = {config.name: config for config in build_community_mcp_configs()}

    assert configs["tavily"].env == {
        "NPM_CONFIG_CACHE": NPM_CACHE_DIR,
        "npm_config_cache": NPM_CACHE_DIR,
        "TAVILY_API_KEY": "test-tavily-key",
    }
    assert configs["github_search"].env == {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "test-github-token",
    }
