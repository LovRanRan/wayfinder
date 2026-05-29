import asyncio
import json
import os
import shutil
from pathlib import Path

import pytest

from wayfinder.mcp.adapter import MCPAdapter, build_mcp_client
from wayfinder.mcp.models import MCPServerConfig, MCPToolCall
from wayfinder.mcp.project5 import build_project5_mcp_configs

pytestmark = pytest.mark.integration

PROJECT5_INTEGRATION_ENABLED = (
    os.getenv("WAYFINDER_RUN_PROJECT5_MCP_INTEGRATION") == "1"
)


def _config_by_name(name: str) -> MCPServerConfig:
    for config in build_project5_mcp_configs():
        if config.name == name:
            return config

    raise AssertionError(f"Missing Project 5 MCP config: {name}")


def _skip_if_integration_disabled() -> None:
    if not PROJECT5_INTEGRATION_ENABLED:
        pytest.skip("set WAYFINDER_RUN_PROJECT5_MCP_INTEGRATION=1 to run real MCP tests")


def _skip_if_command_missing(config: MCPServerConfig) -> None:
    if config.command is None:
        pytest.skip(f"{config.name} does not use a local command")

    if shutil.which(config.command) is None:
        pytest.skip(f"Project 5 MCP command is not installed: {config.command}")


def _write_fixture_repo(tmp_path: Path) -> Path:
    package_dir = tmp_path / "sample_app"
    tests_dir = tmp_path / "tests"
    package_dir.mkdir()
    tests_dir.mkdir()

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "sample-app"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "main.py").write_text(
        "def greet(name: str) -> str:\n"
        '    return f"hello {name}"\n',
        encoding="utf-8",
    )
    (tests_dir / "test_main.py").write_text(
        "from sample_app.main import greet\n\n"
        "def test_greet() -> None:\n"
        '    assert greet("wayfinder") == "hello wayfinder"\n',
        encoding="utf-8",
    )

    return tmp_path


def _arguments_for_tool(tool_name: str, repo_path: Path) -> dict[str, object]:
    if tool_name == "scan_repo":
        return {"path": str(repo_path)}

    if tool_name == "find_definition":
        return {
            "path": str(repo_path),
            "symbol": "greet",
            "language": "python",
        }

    if tool_name == "parse_test_output":
        return {
            "stdout": json.dumps(
                {
                    "summary": {"passed": 1, "failed": 0, "skipped": 0},
                    "tests": [],
                }
            ),
            "framework": "pytest",
        }

    raise AssertionError(f"Unsupported happy-path tool: {tool_name}")


@pytest.mark.parametrize(
    ("server_name", "expected_tool"),
    [
        ("repo_mapper", "scan_repo"),
        ("ast_explorer", "find_definition"),
        ("test_runner", "parse_test_output"),
    ],
)
def test_project5_mcp_server_lists_and_calls_happy_path_tool(
    tmp_path: Path,
    server_name: str,
    expected_tool: str,
) -> None:
    _skip_if_integration_disabled()

    config = _config_by_name(server_name)
    _skip_if_command_missing(config)

    repo_path = _write_fixture_repo(tmp_path)
    adapter = MCPAdapter(build_mcp_client([config]))

    descriptors = asyncio.run(adapter.list_tools())
    assert expected_tool in {descriptor.name for descriptor in descriptors}

    result = asyncio.run(
        adapter.call_tool(
            MCPToolCall(
                tool_name=expected_tool,
                arguments=_arguments_for_tool(expected_tool, repo_path),
            )
        )
    )

    assert result.tool_name == expected_tool
    assert result.content is not None
