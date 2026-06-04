from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from wayfinder.api.main import app
from wayfinder.graph.architecture import ArchitectureScanner
from wayfinder.graph.entry import EntryScanner
from wayfinder.graph.state import WayfinderState


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


def test_explain_status_and_refine_flow() -> None:
    client = TestClient(app)

    explain_response = client.post(
        "/explain",
        json={"repo_url": "https://github.com/langchain-ai/langchain", "query": "Map the repo"},
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
    assert "langchain-ai/langchain" in status_payload["final_output"]
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
    ) -> FakeApiGraph:
        del checkpointer, architecture_scanner, entry_scanner, verifier_runner
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
    ) -> FakeApiGraph:
        del checkpointer, architecture_scanner, entry_scanner, verifier_runner
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
    ) -> FakeApiGraph:
        del checkpointer, architecture_scanner, entry_scanner, verifier_runner
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
    ) -> FakeApiGraph:
        del checkpointer, verifier_runner
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
