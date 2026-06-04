import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def start_api_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "deploy" / "start_api.py"
    spec = importlib.util.spec_from_file_location("wayfinder_deploy_start_api", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_reader_mcp_sidecars_are_opt_in(
    start_api_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WAYFINDER_START_PROJECT5_HTTP_MCP", raising=False)

    assert start_api_module._start_reader_mcp_sidecars() is False

    monkeypatch.setenv("WAYFINDER_START_PROJECT5_HTTP_MCP", "1")

    assert start_api_module._start_reader_mcp_sidecars() is True


def test_reader_mcp_env_defaults_use_localhost_urls(
    start_api_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "WAYFINDER_ARCHITECTURE_SCANNER",
        "WAYFINDER_ENTRY_SCANNER",
        "WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL",
        "WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    start_api_module._apply_reader_mcp_env_defaults()

    assert start_api_module.os.environ["WAYFINDER_ARCHITECTURE_SCANNER"] == "mcp_http"
    assert start_api_module.os.environ["WAYFINDER_ENTRY_SCANNER"] == "mcp_http"
    assert (
        start_api_module.os.environ["WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL"]
        == "http://127.0.0.1:8101/mcp"
    )
    assert (
        start_api_module.os.environ["WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL"]
        == "http://127.0.0.1:8102/mcp"
    )


def test_reader_mcp_env_defaults_do_not_override_explicit_values(
    start_api_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WAYFINDER_ARCHITECTURE_SCANNER", "placeholder")

    start_api_module._apply_reader_mcp_env_defaults()

    assert start_api_module.os.environ["WAYFINDER_ARCHITECTURE_SCANNER"] == "placeholder"
