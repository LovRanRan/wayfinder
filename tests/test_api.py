from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from wayfinder.api.auth import AuthenticatedUser
from wayfinder.api.main import app
from wayfinder.api.run_store import InMemoryRunStore, SQLiteRunStore
from wayfinder.api.schemas import ExplainRequest
from wayfinder.graph.architecture import ArchitectureScanner
from wayfinder.graph.entry import EntryScanner
from wayfinder.graph.state import WayfinderState
from wayfinder.ingestion.models import RepoHandle, RepoSource


class FakeApiArchitectureScanner:
    def scan_repo(self, repo_path: str) -> dict[str, object]:
        return {"root": repo_path}


class FakeApiEntryScanner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def explain_symbol(self, repo_path: str, symbol: str) -> dict[str, object]:
        self.calls.append((repo_path, symbol))
        return {
            "status": "found",
            "symbol": symbol,
            "definition": {
                "found": True,
                "symbol": symbol,
                "kind": "function",
                "location": {"relative_path": "app/service.py", "line": 2},
            },
            "signature": {
                "found": True,
                "symbol": symbol,
                "signature": "create_user(name: str) -> dict[str, str]",
            },
            "references": {
                "found": True,
                "symbol": symbol,
                "references": [
                    {"location": {"relative_path": "tests/test_service.py", "line": 5}},
                ],
            },
            "call_chain": {
                "found": True,
                "symbol": symbol,
                "callers": [{"symbol": "app.api:create_user_route"}],
            },
            "limitations": [],
        }


class FakeApiGraph:
    def __init__(
        self,
        *,
        inputs: list[WayfinderState] | None = None,
        configs: list[dict[str, Any] | None] | None = None,
        should_raise: bool = False,
    ) -> None:
        self.inputs = inputs
        self.configs = configs
        self.should_raise = should_raise

    def invoke(
        self,
        input: WayfinderState,
        config: dict[str, Any] | None = None,
    ) -> WayfinderState:
        if self.inputs is not None:
            self.inputs.append(input)
        if self.configs is not None:
            self.configs.append(config)
        if self.should_raise:
            raise RuntimeError("graph exploded")

        return {
            "final_output": f"fake output for {input.get('query', '')}",
            "partial_summaries": {"architect_mapper": "fake architecture summary"},
            "verified_claims": [],
            "unverified_claims": [],
            "contradicted_claims": [],
        }


def test_health() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "wayfinder"}


def test_explain_status_and_refine_flow(tmp_path: Path) -> None:
    client = TestClient(app)
    (tmp_path / "app.py").write_text("print('hello')\n")

    explain_response = client.post(
        "/explain",
        json={"repo_url": str(tmp_path), "query": "Map the repo"},
    )

    assert explain_response.status_code == 202
    payload = explain_response.json()
    assert payload["status"] == "queued"
    assert payload["current_node"] == "queued"

    status_response = client.get(f"/status/{payload['job_id']}")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["job_id"] == payload["job_id"]
    assert status_payload["status"] == "completed"
    assert status_payload["verified_count"] == 0
    assert status_payload["contradicted_count"] == 0
    assert str(tmp_path) in status_payload["final_output"]
    assert status_payload["trace_metadata"]["thread_id"] == payload["job_id"]

    refine_response = client.post(
        f"/refine/{payload['job_id']}",
        json={"correction": "Focus on runtime entry points"},
    )
    assert refine_response.status_code == 202
    assert "runtime entry points" in refine_response.json()["query"]
    assert refine_response.json()["user_corrections"] == ["Focus on runtime entry points"]

    refined_status_response = client.get(f"/status/{payload['job_id']}")
    assert refined_status_response.status_code == 200
    refined_payload = refined_status_response.json()
    assert refined_payload["status"] == "completed"
    assert refined_payload["trace_metadata"]["phase"] == "refine"
    assert refined_payload["trace_metadata"]["thread_id"] == payload["job_id"]


def test_runs_lists_recent_jobs() -> None:
    client = TestClient(app)
    response = client.post(
        "/explain",
        json={"repo_url": "local", "query": "Map architecture"},
    )
    job_id = response.json()["job_id"]

    runs_response = client.get("/runs?limit=10")

    assert runs_response.status_code == 200
    job_ids = [run["job_id"] for run in runs_response.json()]
    assert job_id in job_ids


def test_auth_required_blocks_anonymous_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("wayfinder.api.main._RUNS", InMemoryRunStore())
    monkeypatch.setenv("WAYFINDER_REQUIRE_AUTH", "1")

    client = TestClient(app)
    response = client.get("/runs")

    assert response.status_code == 401
    assert response.json()["detail"] == "login required"


def test_workspace_auth_scopes_runs_to_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("wayfinder.api.main._RUNS", InMemoryRunStore())
    monkeypatch.setenv("WAYFINDER_REQUIRE_AUTH", "1")

    client = TestClient(app)
    alice_register = client.post(
        "/auth/register",
        json={
            "workspace_id": "alice",
            "password": "correct-horse",
            "display_name": "Alice",
        },
    )
    bob_register = client.post(
        "/auth/register",
        json={
            "workspace_id": "bob",
            "password": "correct-horse",
            "display_name": "Bob",
        },
    )

    assert alice_register.status_code == 201
    assert bob_register.status_code == 201
    alice_token = alice_register.json()["token"]
    bob_token = bob_register.json()["token"]

    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    me_response = client.get("/auth/me", headers=alice_headers)
    assert me_response.status_code == 200
    assert me_response.json()["workspace_id"] == "alice"

    explain_response = client.post(
        "/explain",
        json={"repo_url": "local", "query": "Map architecture"},
        headers=alice_headers,
    )
    assert explain_response.status_code == 202
    job_id = explain_response.json()["job_id"]
    assert explain_response.json()["user_id"] == alice_register.json()["user"]["user_id"]

    alice_runs = client.get("/runs", headers=alice_headers).json()
    bob_runs = client.get("/runs", headers=bob_headers).json()
    assert [run["job_id"] for run in alice_runs] == [job_id]
    assert bob_runs == []

    bob_status = client.get(f"/status/{job_id}", headers=bob_headers)
    assert bob_status.status_code == 404


def test_workspace_settings_defaults_to_safe_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("wayfinder.api.main._RUNS", InMemoryRunStore())
    monkeypatch.setenv("WAYFINDER_OPENAI_MODEL", "chat-latest")
    monkeypatch.setenv("WAYFINDER_LLM_ROUTING", "openai")
    monkeypatch.setenv("WAYFINDER_FINAL_WRITER", "openai")
    monkeypatch.setenv("WAYFINDER_VERIFIER_RUNNER", "placeholder")

    client = TestClient(app)
    response = client.get("/workspace/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspace_id"] == "local-dev"
    assert payload["openai_key_configured"] is False
    assert payload["openai_key_label"] is None
    assert payload["openai_model"] == "chat-latest"
    assert payload["llm_routing"] == "openai"
    assert payload["final_writer"] == "openai"
    assert payload["verifier_runner"] == "placeholder"
    assert payload["sandbox_status"] == "disabled"


def test_workspace_settings_requires_encryption_secret_for_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("wayfinder.api.main._RUNS", InMemoryRunStore())
    monkeypatch.delenv("WAYFINDER_KEY_ENCRYPTION_SECRET", raising=False)

    client = TestClient(app)
    response = client.put(
        "/workspace/settings",
        json={"openai_api_key": "sk-test-owned-key"},
    )

    assert response.status_code == 500
    assert "WAYFINDER_KEY_ENCRYPTION_SECRET" in response.json()["detail"]


def test_workspace_settings_are_scoped_and_redact_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("wayfinder.api.main._RUNS", InMemoryRunStore())
    monkeypatch.setenv("WAYFINDER_REQUIRE_AUTH", "1")
    monkeypatch.setenv("WAYFINDER_KEY_ENCRYPTION_SECRET", "unit-test-secret")
    client = TestClient(app)

    alice_token = client.post(
        "/auth/register",
        json={
            "workspace_id": "alice",
            "password": "correct-horse",
            "display_name": "Alice",
        },
    ).json()["token"]
    bob_token = client.post(
        "/auth/register",
        json={
            "workspace_id": "bob",
            "password": "correct-horse",
            "display_name": "Bob",
        },
    ).json()["token"]

    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    update_response = client.put(
        "/workspace/settings",
        json={
            "openai_api_key": "sk-test-alice-secret",
            "openai_model": "chat-latest",
            "llm_routing": "openai",
            "final_writer": "openai",
        },
        headers=alice_headers,
    )

    assert update_response.status_code == 200
    update_text = update_response.text
    assert "sk-test-alice-secret" not in update_text
    alice_settings = update_response.json()
    assert alice_settings["openai_key_configured"] is True
    assert alice_settings["openai_key_label"] == "sk-...cret"
    assert alice_settings["openai_model"] == "chat-latest"
    assert alice_settings["llm_routing"] == "openai"
    assert alice_settings["final_writer"] == "openai"

    bob_settings = client.get("/workspace/settings", headers=bob_headers).json()
    assert bob_settings["openai_key_configured"] is False
    assert bob_settings["openai_key_label"] is None

    clear_response = client.put(
        "/workspace/settings",
        json={"clear_openai_api_key": True},
        headers=alice_headers,
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["openai_key_configured"] is False
    assert clear_response.json()["openai_key_label"] is None


def test_workspace_key_is_decrypted_into_run_runtime_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("wayfinder.api.main._RUNS", InMemoryRunStore())
    monkeypatch.setenv("WAYFINDER_REQUIRE_AUTH", "1")
    monkeypatch.setenv("WAYFINDER_KEY_ENCRYPTION_SECRET", "unit-test-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-platform-key")
    captured_env: dict[str, str] = {}

    def fake_llm_router_from_env(env: Mapping[str, str] | None = None) -> None:
        captured_env.update(dict(env or {}))
        return None

    def fake_final_synthesizer_from_env(env: Mapping[str, str] | None = None) -> None:
        captured_env.update({f"final_{key}": value for key, value in dict(env or {}).items()})
        return None

    def fake_build_graph(
        checkpointer: object = None,
        *,
        architecture_scanner: ArchitectureScanner | None = None,
        entry_scanner: EntryScanner | None = None,
        verifier_runner: object | None = None,
        llm_router: object | None = None,
        final_synthesizer: object | None = None,
        community_context_provider: object | None = None,
    ) -> FakeApiGraph:
        del (
            checkpointer,
            architecture_scanner,
            entry_scanner,
            verifier_runner,
            llm_router,
            final_synthesizer,
            community_context_provider,
        )
        return FakeApiGraph()

    monkeypatch.setattr("wayfinder.api.main.llm_router_from_env", fake_llm_router_from_env)
    monkeypatch.setattr(
        "wayfinder.api.main.final_synthesizer_from_env",
        fake_final_synthesizer_from_env,
    )
    monkeypatch.setattr("wayfinder.api.main.build_graph", fake_build_graph)

    client = TestClient(app)
    token = client.post(
        "/auth/register",
        json={
            "workspace_id": "alice",
            "password": "correct-horse",
            "display_name": "Alice",
        },
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.put(
        "/workspace/settings",
        json={
            "openai_api_key": "sk-workspace-key",
            "openai_model": "chat-latest",
            "llm_routing": "openai",
            "final_writer": "openai",
        },
        headers=headers,
    )

    response = client.post(
        "/explain",
        json={"repo_url": "local", "query": "Map architecture"},
        headers=headers,
    )

    assert response.status_code == 202
    assert captured_env["OPENAI_API_KEY"] == "sk-workspace-key"
    assert captured_env["OPENAI_API_KEY"] != "sk-platform-key"
    assert captured_env["WAYFINDER_OPENAI_MODEL"] == "chat-latest"
    assert captured_env["WAYFINDER_LLM_ROUTING"] == "openai"
    assert captured_env["WAYFINDER_FINAL_WRITER"] == "openai"


def test_authenticated_openai_mode_requires_workspace_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("wayfinder.api.main._RUNS", InMemoryRunStore())
    monkeypatch.setenv("WAYFINDER_REQUIRE_AUTH", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-platform-key")
    monkeypatch.setenv("WAYFINDER_LLM_ROUTING", "openai")
    monkeypatch.setenv("WAYFINDER_FINAL_WRITER", "deterministic")

    client = TestClient(app)
    token = client.post(
        "/auth/register",
        json={
            "workspace_id": "alice",
            "password": "correct-horse",
            "display_name": "Alice",
        },
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/explain",
        json={"repo_url": "local", "query": "Map architecture"},
        headers=headers,
    )

    assert response.status_code == 202
    status_response = client.get(f"/status/{response.json()['job_id']}", headers=headers)
    payload = status_response.json()
    assert payload["status"] == "failed"
    assert "OPENAI_API_KEY is required" in payload["error"]


def test_sqlite_run_store_persists_user_run_history(tmp_path: Path) -> None:
    db_path = tmp_path / "runs.sqlite"
    user = AuthenticatedUser(
        user_id="user-1",
        workspace_id="alice",
        display_name="Alice",
    )
    store = SQLiteRunStore(db_path)
    run = store.create(
        user=user,
        request=ExplainRequest(repo_url="local", query="Map architecture"),
        graph_input={"repo_url": "local", "query": "Map architecture"},
    )
    store.mark_completed(
        run.job_id,
        result={
            "final_output": "done",
            "partial_summaries": {},
            "verified_claims": [],
            "unverified_claims": [],
            "contradicted_claims": [],
        },
        trace_metadata={"phase": "explain"},
    )

    reopened = SQLiteRunStore(db_path)
    runs = reopened.list_recent(user_id=user.user_id, limit=5)

    assert len(runs) == 1
    assert runs[0].job_id == run.job_id
    assert runs[0].final_output == "done"


def test_explain_rejects_github_url_when_ingestion_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WAYFINDER_ENABLE_GITHUB_INGESTION", raising=False)

    client = TestClient(app)
    response = client.post(
        "/explain",
        json={"repo_url": "https://github.com/langchain-ai/langchain", "query": "Map the repo"},
    )

    assert response.status_code == 403
    assert "GitHub URL ingestion is disabled" in response.json()["detail"]


def test_explain_resolves_allowed_github_url_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    inputs: list[WayfinderState] = []
    cache_root = tmp_path / "cache"
    repo_path = tmp_path / "cached-langchain"
    repo_path.mkdir()
    (repo_path / "README.md").write_text("# cached\n")
    captured: dict[str, object] = {}

    def fake_resolve_repo_source(
        source: RepoSource,
        cache_root: Path | None = None,
        git_runner: object | None = None,
    ) -> RepoHandle:
        del git_runner
        captured["source"] = source
        captured["cache_root"] = cache_root
        return RepoHandle(
            source=source,
            local_path=repo_path,
            cache_key="github.com__langchain-ai__langchain",
            clone_url="https://github.com/langchain-ai/langchain.git",
            file_count=1,
        )

    def fake_build_graph(
        checkpointer: object = None,
        *,
        architecture_scanner: ArchitectureScanner | None = None,
        entry_scanner: EntryScanner | None = None,
        verifier_runner: object | None = None,
        llm_router: object | None = None,
        final_synthesizer: object | None = None,
        community_context_provider: object | None = None,
    ) -> FakeApiGraph:
        del (
            checkpointer,
            architecture_scanner,
            entry_scanner,
            verifier_runner,
            llm_router,
            final_synthesizer,
            community_context_provider,
        )
        return FakeApiGraph(inputs=inputs)

    monkeypatch.setenv("WAYFINDER_ENABLE_GITHUB_INGESTION", "1")
    monkeypatch.setenv("WAYFINDER_GITHUB_REPO_ALLOWLIST", "langchain-ai/langchain")
    monkeypatch.setenv("WAYFINDER_GITHUB_CACHE_ROOT", str(cache_root))
    monkeypatch.setattr("wayfinder.api.main.resolve_repo_source", fake_resolve_repo_source)
    monkeypatch.setattr("wayfinder.api.main.build_graph", fake_build_graph)

    client = TestClient(app)
    response = client.post(
        "/explain",
        json={"repo_url": "https://github.com/langchain-ai/langchain", "query": "Map the repo"},
    )

    assert response.status_code == 202
    assert captured["cache_root"] == cache_root
    assert captured["source"] == RepoSource(
        kind="github",
        original_ref="https://github.com/langchain-ai/langchain",
    )
    assert inputs
    repo_handle = inputs[0]["repo_handle"]
    assert repo_handle.source.kind == "github"
    assert repo_handle.local_path == repo_path


def test_explain_rejects_github_repo_outside_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WAYFINDER_ENABLE_GITHUB_INGESTION", "1")
    monkeypatch.setenv("WAYFINDER_GITHUB_REPO_ALLOWLIST", "lovranran/wayfinder")

    client = TestClient(app)
    response = client.post(
        "/explain",
        json={"repo_url": "https://github.com/langchain-ai/langchain", "query": "Map the repo"},
    )

    assert response.status_code == 403
    assert "WAYFINDER_GITHUB_REPO_ALLOWLIST" in response.json()["detail"]


def test_explain_rejects_oversized_github_repo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cached-large"
    repo_path.mkdir()

    def fake_resolve_repo_source(
        source: RepoSource,
        cache_root: Path | None = None,
        git_runner: object | None = None,
    ) -> RepoHandle:
        del cache_root, git_runner
        return RepoHandle(
            source=source,
            local_path=repo_path,
            cache_key="github.com__langchain-ai__langchain",
            clone_url="https://github.com/langchain-ai/langchain.git",
            file_count=101,
        )

    monkeypatch.setenv("WAYFINDER_ENABLE_GITHUB_INGESTION", "1")
    monkeypatch.setenv("WAYFINDER_GITHUB_REPO_ALLOWLIST", "*")
    monkeypatch.setenv("WAYFINDER_GITHUB_MAX_FILES", "100")
    monkeypatch.setattr("wayfinder.api.main.resolve_repo_source", fake_resolve_repo_source)

    client = TestClient(app)
    response = client.post(
        "/explain",
        json={"repo_url": "https://github.com/langchain-ai/langchain", "query": "Map the repo"},
    )

    assert response.status_code == 413
    assert "exceeds the 100 file demo limit" in response.json()["detail"]


def test_missing_job_returns_404() -> None:
    client = TestClient(app)

    response = client.get("/status/missing")

    assert response.status_code == 404


def test_refine_reuses_thread_id_and_passes_user_corrections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs: list[WayfinderState] = []
    configs: list[dict[str, Any] | None] = []

    def fake_build_graph(
        checkpointer: object = None,
        *,
        architecture_scanner: ArchitectureScanner | None = None,
        entry_scanner: EntryScanner | None = None,
        verifier_runner: object | None = None,
        llm_router: object | None = None,
        final_synthesizer: object | None = None,
        community_context_provider: object | None = None,
    ) -> FakeApiGraph:
        del (
            checkpointer,
            architecture_scanner,
            entry_scanner,
            verifier_runner,
            llm_router,
            final_synthesizer,
            community_context_provider,
        )
        return FakeApiGraph(inputs=inputs, configs=configs)

    monkeypatch.setattr("wayfinder.api.main.build_graph", fake_build_graph)

    client = TestClient(app)
    explain_response = client.post(
        "/explain",
        json={"repo_url": "local", "query": "Map architecture"},
    )
    job_id = explain_response.json()["job_id"]

    refine_response = client.post(
        f"/refine/{job_id}",
        json={"correction": "intent=behavioral"},
    )

    assert refine_response.status_code == 202
    assert len(inputs) == 2
    assert inputs[0]["thread_id"] == job_id
    assert inputs[1]["thread_id"] == job_id
    assert inputs[1]["user_corrections"] == ["intent=behavioral"]
    assert configs[0] is not None
    assert configs[1] is not None
    assert configs[0]["configurable"]["thread_id"] == job_id
    assert configs[1]["configurable"]["thread_id"] == job_id


def test_refine_rejects_running_job(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_execute_job(job_id: str, phase: str) -> None:
        del job_id, phase

    monkeypatch.setattr("wayfinder.api.main._execute_job", fake_execute_job)

    client = TestClient(app)
    explain_response = client.post(
        "/explain",
        json={"repo_url": "local", "query": "Map architecture"},
    )

    assert explain_response.status_code == 202
    response = client.post(
        f"/refine/{explain_response.json()['job_id']}",
        json={"correction": "intent=behavioral"},
    )

    assert response.status_code == 409


def test_explain_serializes_graph_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_build_graph(
        checkpointer: object = None,
        *,
        architecture_scanner: ArchitectureScanner | None = None,
        entry_scanner: EntryScanner | None = None,
        verifier_runner: object | None = None,
        llm_router: object | None = None,
        final_synthesizer: object | None = None,
        community_context_provider: object | None = None,
    ) -> FakeApiGraph:
        del (
            checkpointer,
            architecture_scanner,
            entry_scanner,
            verifier_runner,
            llm_router,
            final_synthesizer,
            community_context_provider,
        )
        return FakeApiGraph(should_raise=True)

    monkeypatch.setattr("wayfinder.api.main.build_graph", fake_build_graph)

    client = TestClient(app)
    explain_response = client.post(
        "/explain",
        json={"repo_url": "local", "query": "Map architecture"},
    )

    assert explain_response.status_code == 202
    status_response = client.get(f"/status/{explain_response.json()['job_id']}")
    payload = status_response.json()
    assert payload["status"] == "failed"
    assert payload["error"] == "graph exploded"
    assert payload["errors"] == [
        {
            "node": "supervisor",
            "error_type": "RuntimeError",
            "message": "graph exploded",
            "retryable": False,
        }
    ]
    assert payload["trace_metadata"]["status"] == "failed"
    assert payload["trace_metadata"]["error_type"] == "RuntimeError"


def test_trace_metadata_hooks_are_passed_to_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    configs: list[dict[str, Any] | None] = []

    def fake_build_graph(
        checkpointer: object = None,
        *,
        architecture_scanner: ArchitectureScanner | None = None,
        entry_scanner: EntryScanner | None = None,
        verifier_runner: object | None = None,
        llm_router: object | None = None,
        final_synthesizer: object | None = None,
        community_context_provider: object | None = None,
    ) -> FakeApiGraph:
        del (
            checkpointer,
            architecture_scanner,
            entry_scanner,
            verifier_runner,
            llm_router,
            final_synthesizer,
            community_context_provider,
        )
        return FakeApiGraph(configs=configs)

    monkeypatch.setattr("wayfinder.api.main.build_graph", fake_build_graph)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_PROJECT", "wayfinder-test")

    client = TestClient(app)
    response = client.post(
        "/explain",
        json={"repo_url": "local", "query": "Map architecture"},
    )
    job_id = response.json()["job_id"]

    assert configs
    config = configs[0]
    assert config is not None
    assert config["configurable"]["thread_id"] == job_id
    assert config["metadata"]["thread_id"] == job_id
    assert config["metadata"]["langsmith_tracing"] is True
    assert config["metadata"]["langsmith_project"] == "wayfinder-test"
    for key in (
        "agent_name",
        "tool_name",
        "mcp_server",
        "tokens",
        "latency",
        "cost_usd",
        "claim_id",
    ):
        assert key in config["metadata"]


def test_explain_uses_architecture_scanner_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    architecture_scanner = FakeApiArchitectureScanner()
    entry_scanner = FakeApiEntryScanner()
    captured: dict[str, object] = {}

    def fake_architecture_scanner_from_env(
        env: Mapping[str, str] | None = None,
    ) -> ArchitectureScanner:
        captured["architecture_env"] = env
        return architecture_scanner

    def fake_entry_scanner_from_env(
        env: Mapping[str, str] | None = None,
    ) -> EntryScanner:
        captured["entry_env"] = env
        return entry_scanner

    def fake_build_graph(
        checkpointer: object = None,
        *,
        architecture_scanner: ArchitectureScanner | None = None,
        entry_scanner: EntryScanner | None = None,
        verifier_runner: object | None = None,
        llm_router: object | None = None,
        final_synthesizer: object | None = None,
        community_context_provider: object | None = None,
    ) -> FakeApiGraph:
        del (
            checkpointer,
            verifier_runner,
            llm_router,
            final_synthesizer,
            community_context_provider,
        )
        captured["architecture_scanner"] = architecture_scanner
        captured["entry_scanner"] = entry_scanner
        return FakeApiGraph()

    monkeypatch.setattr(
        "wayfinder.api.main.architecture_scanner_from_env",
        fake_architecture_scanner_from_env,
        raising=False,
    )
    monkeypatch.setattr(
        "wayfinder.api.main.entry_scanner_from_env",
        fake_entry_scanner_from_env,
        raising=False,
    )
    monkeypatch.setattr("wayfinder.api.main.build_graph", fake_build_graph)

    client = TestClient(app)
    response = client.post(
        "/explain",
        json={"repo_url": "local", "query": "Map architecture"},
    )

    assert response.status_code == 202
    assert captured["architecture_scanner"] is architecture_scanner
    assert captured["entry_scanner"] is entry_scanner


def test_explain_behavioral_query_uses_entry_scanner_on_local_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "service.py").write_text(
        "def create_user(name: str) -> dict[str, str]:\n"
        "    return {'name': name}\n"
    )
    entry_scanner = FakeApiEntryScanner()

    monkeypatch.setattr(
        "wayfinder.api.main.architecture_scanner_from_env",
        lambda env=None: None,
        raising=False,
    )
    monkeypatch.setattr(
        "wayfinder.api.main.entry_scanner_from_env",
        lambda env=None: entry_scanner,
        raising=False,
    )

    client = TestClient(app)
    response = client.post(
        "/explain",
        json={
            "repo_url": str(tmp_path),
            "query": "Explain the behavior and data flow through app.service.create_user",
        },
    )

    payload = response.json()
    assert response.status_code == 202
    assert payload["status"] == "queued"
    status_payload = client.get(f"/status/{payload['job_id']}").json()
    assert status_payload["status"] == "completed"
    assert entry_scanner.calls == [(str(tmp_path.resolve()), "app.service.create_user")]
    assert "Entry explanation evidence collected for app.service.create_user" in (
        status_payload["final_output"]
    )
    assert "Definition: app/service.py:2" in status_payload["final_output"]
    assert "Call chain: app.api:create_user_route -> app.service.create_user" in (
        status_payload["final_output"]
    )
