from collections.abc import Mapping

from wayfinder.graph.architecture import ArchitectureScanner, MCPArchitectureScanner
from wayfinder.mcp.adapter import MCPAdapter, build_mcp_client
from wayfinder.mcp.models import MCPServerConfig
from wayfinder.mcp.project5 import build_project5_mcp_configs


def project5_repo_mapper_config() -> MCPServerConfig:
    for config in build_project5_mcp_configs():
        if config.name == "repo_mapper":
            return config

    raise RuntimeError("Project 5 repo_mapper MCP config is missing")

def build_project5_architecture_scanner() -> ArchitectureScanner:
    config = project5_repo_mapper_config()
    client = build_mcp_client([config])
    adapter = MCPAdapter(client)
    return MCPArchitectureScanner(adapter)


def architecture_scanner_from_env(
    env: Mapping[str, str] | None = None,
) -> ArchitectureScanner | None:
    mode = (env or {}).get("WAYFINDER_ARCHITECTURE_SCANNER", "placeholder").strip().lower()

    if mode in ("", "placeholder"):
        return None

    if mode == "mcp":
        return build_project5_architecture_scanner()

    raise ValueError(f"Unsupported architecture scanner mode: {mode}")