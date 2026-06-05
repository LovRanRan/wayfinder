from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wayfinder.graph.verifier import TestRunRequest as VerifierTestRunRequest
from wayfinder.sandbox.remote import RemoteSandboxTestRunner, check_sandbox_health
from wayfinder.sandbox.schemas import SandboxTestRequest
from wayfinder.sandbox.worker import SandboxWorkerConfig, create_app, run_sandboxed_test


def _repo_with_pytest(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname='sandbox-fixture'\n", encoding="utf-8")
    (tests_dir / "test_service.py").write_text(
        "import time\n\n"
        "def test_truth():\n"
        "    assert 1 + 1 == 2\n\n"
        "def test_failure():\n"
        "    assert False\n\n"
        "def test_timeout():\n"
        "    time.sleep(1)\n"
        "    assert True\n",
        encoding="utf-8",
    )
    return repo


def _request(repo: Path, test_filter: str) -> SandboxTestRequest:
    return SandboxTestRequest(
        test_ref="test-0",
        claim_refs=["claim-0"],
        framework="pytest",
        tool_name="run_single_test",
        path=str(repo),
        test_filter=test_filter,
        timeout_seconds=5,
        job_id="job-1",
        run_owner="user-1",
    )


def _config(tmp_path: Path) -> SandboxWorkerConfig:
    temp_root = tmp_path / "work"
    temp_root.mkdir(exist_ok=True)
    return SandboxWorkerConfig(
        allowed_roots=(tmp_path,),
        temp_root=temp_root,
        max_output_bytes=12000,
    )


def test_sandbox_worker_health_endpoint(tmp_path: Path) -> None:
    client = TestClient(create_app(_config(tmp_path)))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "wayfinder-test-sandbox"


def test_sandbox_worker_requires_token_when_configured(tmp_path: Path) -> None:
    repo = _repo_with_pytest(tmp_path)
    config = SandboxWorkerConfig(
        allowed_roots=(tmp_path,),
        temp_root=tmp_path / "work",
        token="secret-token",
    )
    config.temp_root.mkdir()
    client = TestClient(create_app(config))

    denied = client.post(
        "/run-test",
        json=_request(repo, "tests/test_service.py::test_truth").model_dump(),
    )
    allowed = client.post(
        "/run-test",
        json=_request(repo, "tests/test_service.py::test_truth").model_dump(),
        headers={"x-wayfinder-sandbox-token": "secret-token"},
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "passed"


def test_run_sandboxed_test_returns_passed_observation(tmp_path: Path) -> None:
    repo = _repo_with_pytest(tmp_path)

    observation = run_sandboxed_test(
        _request(repo, "tests/test_service.py::test_truth"),
        _config(tmp_path),
    )

    assert observation.status == "passed"
    assert observation.passed == 1
    assert observation.failed == 0
    assert "passed" in observation.output


def test_run_sandboxed_test_returns_failed_observation(tmp_path: Path) -> None:
    repo = _repo_with_pytest(tmp_path)

    observation = run_sandboxed_test(
        _request(repo, "tests/test_service.py::test_failure"),
        _config(tmp_path),
    )

    assert observation.status == "failed"
    assert observation.failed >= 1
    assert any("test_failure" in failure for failure in observation.failures)


def test_run_sandboxed_test_times_out(tmp_path: Path) -> None:
    repo = _repo_with_pytest(tmp_path)
    request = _request(repo, "tests/test_service.py::test_timeout").model_copy(
        update={"timeout_seconds": 0.1}
    )

    observation = run_sandboxed_test(request, _config(tmp_path))

    assert observation.status == "timed_out"
    assert "timed out" in observation.output


def test_run_sandboxed_test_denies_shell_and_package_install_filters(
    tmp_path: Path,
) -> None:
    repo = _repo_with_pytest(tmp_path)

    shell = run_sandboxed_test(
        _request(repo, "tests/test_service.py::test_truth; rm -rf /"),
        _config(tmp_path),
    )
    install = run_sandboxed_test(
        _request(repo, "tests/test_service.py::test_truth pip install malware"),
        _config(tmp_path),
    )

    assert shell.status == "tool_error"
    assert shell.denied_reason == "test filter contains shell metacharacters"
    assert install.status == "tool_error"
    assert install.denied_reason == "test filter contains denied command token"


def test_run_sandboxed_test_denies_path_outside_allowed_roots(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = _repo_with_pytest(tmp_path / "outside-parent")

    observation = run_sandboxed_test(
        _request(outside, "tests/test_service.py::test_truth"),
        SandboxWorkerConfig(allowed_roots=(allowed,), temp_root=allowed),
    )

    assert observation.status == "tool_error"
    assert observation.denied_reason == "repo path is outside sandbox allowed roots"


def test_run_sandboxed_test_truncates_output(tmp_path: Path) -> None:
    repo = _repo_with_pytest(tmp_path)
    request = _request(repo, "tests/test_service.py::test_failure").model_copy(
        update={"max_output_bytes": 256}
    )
    config = SandboxWorkerConfig(
        allowed_roots=(tmp_path,),
        temp_root=tmp_path / "work",
        max_output_bytes=256,
    )
    config.temp_root.mkdir()

    observation = run_sandboxed_test(request, config)

    assert observation.status == "failed"
    assert len(observation.output.encode("utf-8")) <= 320


def test_remote_sandbox_runner_maps_request_and_observation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_json_request(url: str, **kwargs: object) -> dict[str, object]:
        captured["url"] = url
        captured.update(kwargs)
        return {
            "test_ref": "test-0",
            "status": "passed",
            "output": "1 passed",
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "failures": [],
            "cleanup_done": True,
            "denied_reason": None,
        }

    monkeypatch.setattr("wayfinder.sandbox.remote._json_request", fake_json_request)
    runner = RemoteSandboxTestRunner(
        "https://sandbox.example/",
        token="secret-token",
        max_output_bytes=1000,
    )
    request = VerifierTestRunRequest(
        test_ref="test-0",
        claim_refs=("claim-0",),
        framework="pytest",
        tool_name="run_single_test",
        path=str(tmp_path),
        test_filter="tests/test_service.py::test_truth",
        timeout_seconds=10,
        estimated_runtime_seconds=10,
        max_output_bytes=12000,
        job_id="job-1",
        run_owner="user-1",
    )

    observation = runner.run_test(request)

    assert observation.status == "passed"
    assert observation.passed == 1
    assert captured["url"] == "https://sandbox.example/run-test"
    assert captured["token"] == "secret-token"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["max_output_bytes"] == 1000
    assert payload["job_id"] == "job-1"
    assert payload["run_owner"] == "user-1"


def test_check_sandbox_health_reads_worker_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_json_request(url: str, **kwargs: object) -> dict[str, object]:
        del url
        del kwargs
        return {"status": "ok", "service": "wayfinder-test-sandbox"}

    monkeypatch.setattr("wayfinder.sandbox.remote._json_request", fake_json_request)

    health = check_sandbox_health("https://sandbox.example", token="secret-token")

    assert health.ok is True
    assert "healthy" in health.message
