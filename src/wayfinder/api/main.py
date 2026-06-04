"""FastAPI entrypoint for the Wayfinder scaffold."""

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status

from wayfinder.api.schemas import ExplainRequest, RefineRequest, RunSummary
from wayfinder.graph import build_graph
from wayfinder.graph.runtime import architecture_scanner_from_env, entry_scanner_from_env
from wayfinder.graph.state import WayfinderState
from wayfinder.ingestion.models import RepoHandle, RepoSource
from wayfinder.ingestion.resolver import resolve_repo_source

app = FastAPI(
    title="wayfinder",
    version="0.1.0",
    description="Verifier-backed codebase onboarding copilot.",
)

_RUNS: dict[str, RunSummary] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "wayfinder"}


@app.post("/explain", response_model=RunSummary, status_code=status.HTTP_202_ACCEPTED)
def explain(request: ExplainRequest) -> RunSummary:
    now = datetime.now(UTC)
    job_id = str(uuid4())
    run = RunSummary(
        job_id=job_id,
        repo_url=request.repo_url,
        query=request.query,
        status="running",
        current_node="bootstrap",
        created_at=now,
        updated_at=now,
    )
    _RUNS[job_id] = run

    try:
        architecture_scanner = architecture_scanner_from_env(os.environ)
        entry_scanner = entry_scanner_from_env(os.environ)
        graph = build_graph(
            architecture_scanner=architecture_scanner,
            entry_scanner=entry_scanner,
        )
        graph_input = _graph_input_from_request(request)
        typed_result = graph.invoke(graph_input)
        completed = run.model_copy(
            update={
                "status": "completed",
                "current_node": None,
                "final_output": typed_result.get("final_output"),
                "verified_count": len(typed_result.get("verified_claims", [])),
                "unverified_count": len(typed_result.get("unverified_claims", [])),
                "contradicted_count": len(typed_result.get("contradicted_claims", [])),
                "updated_at": datetime.now(UTC),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive API boundary
        completed = run.model_copy(
            update={"status": "failed", "error": str(exc), "updated_at": datetime.now(UTC)}
        )

    _RUNS[job_id] = completed
    return completed


def _graph_input_from_request(request: ExplainRequest) -> WayfinderState:
    graph_input: dict[str, object] = {
        "repo_url": request.repo_url,
        "query": request.query,
    }
    repo_handle = _local_repo_handle_from_ref(request.repo_url)
    if repo_handle is not None:
        graph_input["repo_handle"] = repo_handle

    return cast(WayfinderState, graph_input)


def _local_repo_handle_from_ref(repo_ref: str) -> RepoHandle | None:
    candidate = Path(repo_ref).expanduser()
    if not candidate.exists():
        return None

    return resolve_repo_source(RepoSource(kind="local", original_ref=repo_ref))


@app.get("/status/{job_id}", response_model=RunSummary)
def get_status(job_id: str) -> RunSummary:
    try:
        return _RUNS[job_id]
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found") from exc


@app.post("/refine/{job_id}", response_model=RunSummary)
def refine(job_id: str, request: RefineRequest) -> RunSummary:
    try:
        run = _RUNS[job_id]
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found") from exc

    updated = run.model_copy(
        update={
            "query": f"{run.query}\n\nUser correction: {request.correction}",
            "updated_at": datetime.now(UTC),
        }
    )
    _RUNS[job_id] = updated
    return updated
