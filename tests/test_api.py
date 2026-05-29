from fastapi.testclient import TestClient

from wayfinder.api.main import app


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
