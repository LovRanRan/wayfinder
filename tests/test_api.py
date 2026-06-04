from collections.abc import Mapping
from pathlib import Path

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
    def invoke(self, input: WayfinderState) -> WayfinderState:
        return {
            "final_output": f"fake output for {input.get('query', '')}",
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
    assert payload["status"] == "completed"
    assert payload["verified_count"] == 0
    assert payload["contradicted_count"] == 0
    assert "langchain-ai/langchain" in payload["final_output"]

    status_response = client.get(f"/status/{payload['job_id']}")
    assert status_response.status_code == 200
    assert status_response.json()["job_id"] == payload["job_id"]

    refine_response = client.post(
        f"/refine/{payload['job_id']}",
        json={"correction": "Focus on runtime entry points"},
    )
    assert refine_response.status_code == 200
    assert "runtime entry points" in refine_response.json()["query"]


def test_missing_job_returns_404() -> None:
    client = TestClient(app)

    response = client.get("/status/missing")

    assert response.status_code == 404


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
        *,
        architecture_scanner: ArchitectureScanner | None = None,
        entry_scanner: EntryScanner | None = None,
    ) -> FakeApiGraph:
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
    assert payload["status"] == "completed"
    assert entry_scanner.calls == [(str(tmp_path.resolve()), "app.service.create_user")]
    assert "Entry explanation evidence collected for app.service.create_user" in (
        payload["final_output"]
    )
    assert "Definition: app/service.py:2" in payload["final_output"]
    assert "Call chain: app.api:create_user_route -> app.service.create_user" in (
        payload["final_output"]
    )
