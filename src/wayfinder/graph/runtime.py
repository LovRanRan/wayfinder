from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from wayfinder.graph.architecture import ArchitectureScanner, MCPArchitectureScanner
from wayfinder.graph.community_context import (
    CommunityContextProvider,
    MCPCommunityContextProvider,
)
from wayfinder.graph.entry import EntryScanner, MCPEntryScanner
from wayfinder.graph.llm import OpenAIResponsesClient
from wayfinder.graph.routing import LLMRouter, PromptedLLMRouter
from wayfinder.graph.synthesis import FinalSynthesizer, LLMFinalSynthesizer
from wayfinder.graph.verifier import MCPTestRunner, TestRunner
from wayfinder.mcp.adapter import MCPAdapter, build_mcp_client
from wayfinder.mcp.community import build_community_mcp_configs
from wayfinder.mcp.models import MCPServerConfig
from wayfinder.mcp.project5 import build_project5_mcp_configs, build_project5_mcp_http_configs
from wayfinder.sandbox.remote import RemoteSandboxTestRunner, check_sandbox_health

_TRUE_ENV_VALUES = {"1", "true", "yes", "on"}
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_OPENAI_MODEL = "gpt-5.5"


@dataclass(frozen=True)
class VerifierSandboxPolicy:
    status: str
    message: str


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


def project5_repo_mapper_http_config(env: Mapping[str, str] | None = None) -> MCPServerConfig:
    for config in build_project5_mcp_http_configs(env):
        if config.name == "repo_mapper":
            return config

    raise ValueError(
        "WAYFINDER_PROJECT5_REPO_MAPPER_MCP_URL is required when "
        "WAYFINDER_ARCHITECTURE_SCANNER=mcp_http"
    )


def project5_ast_explorer_http_config(env: Mapping[str, str] | None = None) -> MCPServerConfig:
    for config in build_project5_mcp_http_configs(env):
        if config.name == "ast_explorer":
            return config

    raise ValueError(
        "WAYFINDER_PROJECT5_AST_EXPLORER_MCP_URL is required when "
        "WAYFINDER_ENTRY_SCANNER=mcp_http"
    )


def build_project5_architecture_scanner() -> ArchitectureScanner:
    config = project5_repo_mapper_config()
    client = build_mcp_client([config])
    adapter = MCPAdapter(client)
    return MCPArchitectureScanner(adapter)


def build_project5_architecture_http_scanner(
    env: Mapping[str, str] | None = None,
) -> ArchitectureScanner:
    config = project5_repo_mapper_http_config(env)
    client = build_mcp_client([config])
    adapter = MCPAdapter(client)
    return MCPArchitectureScanner(adapter)


def build_project5_entry_scanner() -> EntryScanner:
    config = project5_ast_explorer_config()
    client = build_mcp_client([config])
    adapter = MCPAdapter(client)
    return MCPEntryScanner(adapter)


def build_project5_entry_http_scanner(
    env: Mapping[str, str] | None = None,
) -> EntryScanner:
    config = project5_ast_explorer_http_config(env)
    client = build_mcp_client([config])
    adapter = MCPAdapter(client)
    return MCPEntryScanner(adapter)


def build_project5_verifier_runner() -> TestRunner:
    config = project5_test_runner_config()
    client = build_mcp_client([config])
    adapter = MCPAdapter(client)
    return MCPTestRunner(adapter)


def build_community_context_provider(
    env: Mapping[str, str] | None = None,
) -> CommunityContextProvider:
    client = build_mcp_client(build_community_mcp_configs(env))
    adapter = MCPAdapter(client)
    return MCPCommunityContextProvider(adapter)


def build_openai_responses_client(
    env: Mapping[str, str],
) -> OpenAIResponsesClient:
    api_key = env.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for OpenAI LLM mode")

    model = env.get("WAYFINDER_OPENAI_MODEL", _DEFAULT_OPENAI_MODEL).strip()
    return OpenAIResponsesClient(api_key=api_key, model=model)


def architecture_scanner_from_env(
    env: Mapping[str, str] | None = None,
) -> ArchitectureScanner | None:
    mode = (env or {}).get("WAYFINDER_ARCHITECTURE_SCANNER", "placeholder").strip().lower()

    if mode in ("", "placeholder"):
        return None

    if mode == "mcp":
        return build_project5_architecture_scanner()

    if mode == "mcp_http":
        return build_project5_architecture_http_scanner(env)

    raise ValueError(f"Unsupported architecture scanner mode: {mode}")


def entry_scanner_from_env(
    env: Mapping[str, str] | None = None,
) -> EntryScanner | None:
    mode = (env or {}).get("WAYFINDER_ENTRY_SCANNER", "placeholder").strip().lower()

    if mode in ("", "placeholder"):
        return None

    if mode == "mcp":
        return build_project5_entry_scanner()

    if mode == "mcp_http":
        return build_project5_entry_http_scanner(env)

    raise ValueError(f"Unsupported entry scanner mode: {mode}")


def verifier_runner_from_env(
    env: Mapping[str, str] | None = None,
) -> TestRunner | None:
    active_env = env or {}
    mode = active_env.get("WAYFINDER_VERIFIER_RUNNER", "placeholder").strip().lower()

    if mode in ("", "placeholder"):
        return None

    if mode == "mcp":
        return build_project5_verifier_runner()

    if mode == "sandboxed_mcp":
        policy = verifier_sandbox_policy_from_env(active_env)
        if policy.status != "enabled":
            return None
        return RemoteSandboxTestRunner(
            _sandbox_url(active_env),
            token=_sandbox_token(active_env),
            request_timeout_seconds=_sandbox_request_timeout_seconds(active_env),
            max_output_bytes=_sandbox_max_output_bytes(active_env),
        )

    raise ValueError(f"Unsupported verifier runner mode: {mode}")


def verifier_sandbox_policy_from_env(
    env: Mapping[str, str] | None = None,
) -> VerifierSandboxPolicy:
    active_env = env or {}
    mode = active_env.get("WAYFINDER_VERIFIER_RUNNER", "placeholder").strip().lower()

    if mode in ("", "placeholder"):
        return VerifierSandboxPolicy(
            status="disabled",
            message=(
                "Executable test verification is disabled; AST/repository evidence can "
                "still verify code facts."
            ),
        )

    if mode == "mcp":
        return VerifierSandboxPolicy(
            status="enabled",
            message="Local Project 5 test runner is enabled for trusted local development only.",
        )

    if mode == "sandboxed_mcp":
        sandbox_url = active_env.get("WAYFINDER_TEST_SANDBOX_URL", "").strip()
        if not sandbox_url:
            return VerifierSandboxPolicy(
                status="unavailable",
                message=(
                    "Sandboxed verifier requested but WAYFINDER_TEST_SANDBOX_URL is "
                    "not configured."
                ),
            )
        health = check_sandbox_health(
            sandbox_url,
            token=_sandbox_token(active_env),
            timeout_seconds=_sandbox_health_timeout_seconds(active_env),
        )
        if not health.ok:
            return VerifierSandboxPolicy(
                status="unavailable",
                message=(
                    "Sandboxed verifier requested but the worker is unhealthy: "
                    f"{health.message}"
                ),
            )
        return VerifierSandboxPolicy(
            status="enabled",
            message=(
                "Sandboxed verifier is enabled; executable claims run through the "
                "separate sandbox worker."
            ),
        )

    return VerifierSandboxPolicy(
        status="unavailable",
        message=f"Unsupported verifier runner mode: {mode}",
    )


def verifier_approval_decision_from_env(
    env: Mapping[str, str] | None = None,
) -> dict[str, object] | None:
    active_env = env or {}
    mode = active_env.get("WAYFINDER_VERIFIER_APPROVAL_MODE", "").strip().lower()

    if mode in ("interrupt", "manual", "hitl"):
        return None

    if mode in ("skip", "auto_skip"):
        return {
            "action": "skip",
            "reason": "verifier execution skipped by deployment policy",
        }

    if mode in ("approve", "auto_approve"):
        return {"action": "approve"}

    if mode in ("", "default"):
        runner_mode = active_env.get("WAYFINDER_VERIFIER_RUNNER", "placeholder").strip().lower()
        if runner_mode == "sandboxed_mcp":
            return {"action": "approve"}
        return None

    raise ValueError(f"Unsupported verifier approval mode: {mode}")


def llm_router_from_env(
    env: Mapping[str, str] | None = None,
) -> LLMRouter | None:
    active_env = env or {}
    mode = active_env.get("WAYFINDER_LLM_ROUTING", "off").strip().lower()

    if mode in ("", "off", "placeholder", "deterministic"):
        return None

    if mode in ("openai", "llm") or mode in _TRUE_ENV_VALUES:
        return PromptedLLMRouter(build_openai_responses_client(active_env))

    raise ValueError(f"Unsupported LLM routing mode: {mode}")


def final_synthesizer_from_env(
    env: Mapping[str, str] | None = None,
) -> FinalSynthesizer | None:
    active_env = env or {}
    mode = active_env.get("WAYFINDER_FINAL_WRITER", "deterministic").strip().lower()

    if mode in ("", "deterministic", "placeholder", "local"):
        return None

    if mode in ("openai", "llm") or mode in _TRUE_ENV_VALUES:
        return LLMFinalSynthesizer(build_openai_responses_client(active_env))

    raise ValueError(f"Unsupported final writer mode: {mode}")


def community_context_provider_from_env(
    env: Mapping[str, str] | None = None,
) -> CommunityContextProvider | None:
    active_env = env or {}
    mode = active_env.get("WAYFINDER_COMMUNITY_CONTEXT", "off").strip().lower()

    if mode in ("", "off", "placeholder", "none"):
        return None

    if mode == "mcp":
        return build_community_context_provider(active_env)

    raise ValueError(f"Unsupported community context mode: {mode}")


def env_with_local_dotenv(
    env: Mapping[str, str] | None = None,
    *,
    dotenv_path: Path | None = None,
) -> dict[str, str]:
    merged = dict(env or {})
    path = dotenv_path or (_PROJECT_ROOT / ".env")
    if not path.exists():
        return merged

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_dotenv_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        merged.setdefault(key, value)

    return merged


def _parse_dotenv_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export ") :].strip()
    if "=" not in line:
        return None

    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    if not key:
        return None

    return key, value


def _sandbox_url(env: Mapping[str, str]) -> str:
    return env.get("WAYFINDER_TEST_SANDBOX_URL", "").strip().rstrip("/")


def _sandbox_token(env: Mapping[str, str]) -> str | None:
    raw = env.get("WAYFINDER_TEST_SANDBOX_TOKEN", "").strip()
    return raw or None


def _sandbox_request_timeout_seconds(env: Mapping[str, str]) -> float:
    return _float_env(env, "WAYFINDER_TEST_SANDBOX_REQUEST_TIMEOUT_SECONDS", 30.0)


def _sandbox_health_timeout_seconds(env: Mapping[str, str]) -> float:
    return _float_env(env, "WAYFINDER_TEST_SANDBOX_HEALTH_TIMEOUT_SECONDS", 1.0)


def _sandbox_max_output_bytes(env: Mapping[str, str]) -> int:
    raw = env.get("WAYFINDER_TEST_SANDBOX_MAX_OUTPUT_BYTES", "12000").strip()
    try:
        value = int(raw)
    except ValueError:
        return 12000
    return max(256, min(value, 64000))


def _float_env(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(0.1, value)
