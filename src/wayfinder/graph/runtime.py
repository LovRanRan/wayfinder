from collections.abc import Mapping

from wayfinder.graph.architecture import ArchitectureScanner, MCPArchitectureScanner
from wayfinder.graph.entry import EntryScanner, MCPEntryScanner
from wayfinder.graph.verifier import MCPTestRunner, TestRunner
from wayfinder.mcp.adapter import MCPAdapter, build_mcp_client
from wayfinder.mcp.models import MCPServerConfig
from wayfinder.mcp.project5 import build_project5_mcp_configs


def project5_repo_mapper_config() -> MCPServerConfig:
    for config in build_project5_mcp_configs():
        if config.name == "repo_mapper":
            return config

    raise RuntimeError("Project 5 repo_mapper MCP config is missing")


def project5_ast_explorer_config() -> MCPServerConfig:
    for config in build_project5_mcp_configs():
        if config.name == "ast_explorer":
            return config

    raise RuntimeError("Project 5 ast_explorer MCP config is missing")


def project5_test_runner_config() -> MCPServerConfig:
    for config in build_project5_mcp_configs():
        if config.name == "test_runner":
            return config

    raise RuntimeError("Project 5 test_runner MCP config is missing")


def build_project5_architecture_scanner() -> ArchitectureScanner:
    config = project5_repo_mapper_config()
    client = build_mcp_client([config])
    adapter = MCPAdapter(client)
    return MCPArchitectureScanner(adapter)


def build_project5_entry_scanner() -> EntryScanner:
    config = project5_ast_explorer_config()
    client = build_mcp_client([config])
    adapter = MCPAdapter(client)
    return MCPEntryScanner(adapter)


def build_project5_verifier_runner() -> TestRunner:
    config = project5_test_runner_config()
    client = build_mcp_client([config])
    adapter = MCPAdapter(client)
    return MCPTestRunner(adapter)


def architecture_scanner_from_env(
    env: Mapping[str, str] | None = None,
) -> ArchitectureScanner | None:
    mode = (env or {}).get("WAYFINDER_ARCHITECTURE_SCANNER", "placeholder").strip().lower()

    if mode in ("", "placeholder"):
        return None

    if mode == "mcp":
        return build_project5_architecture_scanner()

    raise ValueError(f"Unsupported architecture scanner mode: {mode}")


def entry_scanner_from_env(
    env: Mapping[str, str] | None = None,
) -> EntryScanner | None:
    mode = (env or {}).get("WAYFINDER_ENTRY_SCANNER", "placeholder").strip().lower()

    if mode in ("", "placeholder"):
        return None

    if mode == "mcp":
        return build_project5_entry_scanner()

    raise ValueError(f"Unsupported entry scanner mode: {mode}")


def verifier_runner_from_env(
    env: Mapping[str, str] | None = None,
) -> TestRunner | None:
    mode = (env or {}).get("WAYFINDER_VERIFIER_RUNNER", "placeholder").strip().lower()

    if mode in ("", "placeholder"):
        return None

    if mode == "mcp":
        return build_project5_verifier_runner()

    raise ValueError(f"Unsupported verifier runner mode: {mode}")
