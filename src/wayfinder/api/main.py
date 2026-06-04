"""FastAPI entrypoint for the Wayfinder scaffold."""

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import cast
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, status
from langgraph.checkpoint.memory import InMemorySaver

from wayfinder.api.observability import (
    finish_trace_metadata,
    runnable_config_for_trace,
    start_trace_context,
)
from wayfinder.api.schemas import ExplainRequest, RefineRequest, RunError, RunSummary
from wayfinder.graph import build_graph
from wayfinder.graph.app import WayfinderGraph
from wayfinder.graph.runtime import (
    architecture_scanner_from_env,
    entry_scanner_from_env,
    verifier_runner_from_env,
)
from wayfinder.graph.state import WayfinderState
from wayfinder.ingestion.models import RepoHandle, RepoSizePolicy, RepoSource
from wayfinder.ingestion.resolver import (
    assess_repo_size,
    parse_github_repo_ref,
    resolve_repo_source,
)

app = FastAPI(
    title="wayfinder",
    version="0.1.0",
    description="Verifier-backed codebase onboarding copilot.",
)

_CHECKPOINTER = InMemorySaver()
_TRUE_ENV_VALUES = {"1", "true", "yes", "on"}
_DEFAULT_GITHUB_ALLOWLIST = "langchain-ai/langchain,lovranran/wayfinder"


class RunStore:
    def __init__(self) -> None:
        self._runs: dict[str, RunSummary] = {}
        self._graph_inputs: dict[str, WayfinderState] = {}
        self._run_order: list[str] = []
        self._lock = RLock()

    def create(self, *, request: ExplainRequest, graph_input: WayfinderState) -> RunSummary:
        now = datetime.now(UTC)
        job_id = str(uuid4())
        graph_input["thread_id"] = job_id
        run = RunSummary(
            job_id=job_id,
            repo_url=request.repo_url,
            query=request.query,
            status="queued",
            current_node="queued",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._runs[job_id] = run
            self._graph_inputs[job_id] = _copy_graph_input(graph_input)
            self._run_order.insert(0, job_id)
        return run

    def get(self, job_id: str) -> RunSummary:
        with self._lock:
            return self._runs[job_id]

    def list_recent(self, *, limit: int) -> list[RunSummary]:
        with self._lock:
            return [self._runs[job_id] for job_id in self._run_order[:limit]]

    def graph_input(self, job_id: str) -> WayfinderState:
        with self._lock:
            return _copy_graph_input(self._graph_inputs[job_id])

    def mark_running(self, job_id: str, *, current_node: str) -> RunSummary:
        return self._update(
            job_id,
            status="running",
            current_node=current_node,
            updated_at=datetime.now(UTC),
        )

    def mark_completed(
        self,
        job_id: str,
        *,
        result: WayfinderState,
        trace_metadata: dict[str, str | int | float | bool | None],
    ) -> RunSummary:
        return self._update(
            job_id,
            status="completed",
            current_node=None,
            final_output=result.get("final_output"),
            error=None,
            partial_summaries=_partial_summaries_from_state(result),
            errors=_run_errors_from_state(result),
            verified_count=len(result.get("verified_claims", [])),
            unverified_count=len(result.get("unverified_claims", [])),
            contradicted_count=len(result.get("contradicted_claims", [])),
            trace_metadata=trace_metadata,
            updated_at=datetime.now(UTC),
        )

    def mark_failed(
        self,
        job_id: str,
        *,
        exc: Exception,
        current_node: str,
        trace_metadata: dict[str, str | int | float | bool | None],
    ) -> RunSummary:
        message = str(exc) or type(exc).__name__
        return self._update(
            job_id,
            status="failed",
            current_node=None,
            error=message,
            errors=[
                RunError(
                    node=current_node,
                    error_type=type(exc).__name__,
                    message=message,
                    retryable=False,
                )
            ],
            trace_metadata=trace_metadata,
            updated_at=datetime.now(UTC),
        )

    def queue_refine(self, job_id: str, correction: str) -> RunSummary:
        with self._lock:
            run = self._runs[job_id]
            if run.status in ("queued", "running"):
                raise ValueError("job is still running")

            query = f"{run.query}\n\nUser correction: {correction}"
            corrections = [*run.user_corrections, correction]
            graph_input = _copy_graph_input(self._graph_inputs[job_id])
            graph_input["query"] = query
            graph_input["user_corrections"] = corrections
            graph_input["thread_id"] = job_id
            self._graph_inputs[job_id] = graph_input

            updated = run.model_copy(
                update={
                    "query": query,
                    "status": "queued",
                    "current_node": "queued",
                    "user_corrections": corrections,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._runs[job_id] = updated
            return updated

    def _update(self, job_id: str, **updates: object) -> RunSummary:
        with self._lock:
            run = self._runs[job_id]
            updated = run.model_copy(update=updates)
            self._runs[job_id] = updated
            return updated


_RUNS = RunStore()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "wayfinder"}


@app.get("/runs", response_model=list[RunSummary])
def list_runs(limit: int = Query(default=10, ge=1, le=50)) -> list[RunSummary]:
    return _RUNS.list_recent(limit=limit)


@app.post("/explain", response_model=RunSummary, status_code=status.HTTP_202_ACCEPTED)
def explain(request: ExplainRequest, background_tasks: BackgroundTasks) -> RunSummary:
    graph_input = _graph_input_from_request(request)
    run = _RUNS.create(request=request, graph_input=graph_input)
    background_tasks.add_task(_execute_job, run.job_id, "explain")
    return run


def _graph_input_from_request(request: ExplainRequest) -> WayfinderState:
    graph_input: dict[str, object] = {
        "repo_url": request.repo_url,
        "query": request.query,
    }
    repo_handle = _repo_handle_from_ref(request.repo_url, os.environ)
    if repo_handle is not None:
        graph_input["repo_handle"] = repo_handle

    return cast(WayfinderState, graph_input)


def _repo_handle_from_ref(repo_ref: str, env: Mapping[str, str]) -> RepoHandle | None:
    local_handle = _local_repo_handle_from_ref(repo_ref)
    if local_handle is not None:
        return local_handle

    if _is_github_repo_url(repo_ref):
        return _github_repo_handle_from_ref(repo_ref, env)

    return None


def _local_repo_handle_from_ref(repo_ref: str) -> RepoHandle | None:
    candidate = Path(repo_ref).expanduser()
    if not candidate.exists():
        return None

    return resolve_repo_source(RepoSource(kind="local", original_ref=repo_ref))


def _github_repo_handle_from_ref(repo_ref: str, env: Mapping[str, str]) -> RepoHandle:
    if not _github_ingestion_enabled(env):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "GitHub URL ingestion is disabled. Set "
                "WAYFINDER_ENABLE_GITHUB_INGESTION=1 for trusted deploy demos."
            ),
        )

    source = RepoSource(kind="github", original_ref=repo_ref)
    try:
        github_ref = parse_github_repo_ref(source)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    repo_name = f"{github_ref.owner}/{github_ref.repo}".lower()
    allowed_repos = _github_allowlist(env)
    if allowed_repos is not None and repo_name not in allowed_repos:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"GitHub repo {github_ref.owner}/{github_ref.repo} is not in "
                "WAYFINDER_GITHUB_REPO_ALLOWLIST."
            ),
        )

    try:
        handle = resolve_repo_source(
            source,
            cache_root=_github_cache_root_from_env(env),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub repo clone failed.",
        ) from exc

    assessment = assess_repo_size(handle, RepoSizePolicy(max_files=_github_max_files(env)))
    if assessment.is_oversized:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"GitHub repo has {assessment.file_count} files, which exceeds "
                f"the {assessment.max_files} file demo limit."
            ),
        )

    return handle


def _is_github_repo_url(repo_ref: str) -> bool:
    parsed = urlparse(repo_ref)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == "github.com"


def _github_ingestion_enabled(env: Mapping[str, str]) -> bool:
    return env.get("WAYFINDER_ENABLE_GITHUB_INGESTION", "").strip().lower() in _TRUE_ENV_VALUES


def _github_allowlist(env: Mapping[str, str]) -> frozenset[str] | None:
    raw = env.get("WAYFINDER_GITHUB_REPO_ALLOWLIST", _DEFAULT_GITHUB_ALLOWLIST)
    items = {item.strip().lower() for item in raw.split(",") if item.strip()}
    if "*" in items:
        return None

    return frozenset(items)


def _github_cache_root_from_env(env: Mapping[str, str]) -> Path | None:
    raw = env.get("WAYFINDER_GITHUB_CACHE_ROOT")
    return Path(raw).expanduser() if raw else None


def _github_max_files(env: Mapping[str, str]) -> int:
    raw = env.get("WAYFINDER_GITHUB_MAX_FILES", "10000").strip()
    try:
        max_files = int(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WAYFINDER_GITHUB_MAX_FILES must be an integer.",
        ) from exc

    if max_files < 1:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WAYFINDER_GITHUB_MAX_FILES must be positive.",
        )

    return max_files


@app.get("/status/{job_id}", response_model=RunSummary)
def get_status(job_id: str) -> RunSummary:
    try:
        return _RUNS.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found") from exc


@app.post(
    "/refine/{job_id}",
    response_model=RunSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
def refine(job_id: str, request: RefineRequest, background_tasks: BackgroundTasks) -> RunSummary:
    try:
        updated = _RUNS.queue_refine(job_id, request.correction)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    background_tasks.add_task(_execute_job, job_id, "refine")
    return updated


def _execute_job(job_id: str, phase: str) -> None:
    current_node = "supervisor"
    graph_input = _RUNS.graph_input(job_id)
    _RUNS.mark_running(job_id, current_node=current_node)
    trace_context = start_trace_context(
        job_id=job_id,
        phase=phase,
        state=graph_input,
        env=os.environ,
    )

    try:
        graph = _build_runtime_graph()
        result = graph.invoke(graph_input, config=runnable_config_for_trace(trace_context))
    except Exception as exc:  # pragma: no cover - defensive API boundary
        _RUNS.mark_failed(
            job_id,
            exc=exc,
            current_node=current_node,
            trace_metadata=finish_trace_metadata(trace_context, error=exc),
        )
        return

    _RUNS.mark_completed(
        job_id,
        result=result,
        trace_metadata=finish_trace_metadata(trace_context, state=result),
    )


def _build_runtime_graph() -> WayfinderGraph:
    architecture_scanner = architecture_scanner_from_env(os.environ)
    entry_scanner = entry_scanner_from_env(os.environ)
    verifier_runner = verifier_runner_from_env(os.environ)
    return build_graph(
        checkpointer=_CHECKPOINTER,
        architecture_scanner=architecture_scanner,
        entry_scanner=entry_scanner,
        verifier_runner=verifier_runner,
    )


def _copy_graph_input(graph_input: WayfinderState) -> WayfinderState:
    copied = dict(graph_input)
    corrections = copied.get("user_corrections")
    if isinstance(corrections, list):
        copied["user_corrections"] = list(corrections)
    return cast(WayfinderState, copied)


def _partial_summaries_from_state(state: WayfinderState) -> dict[str, str]:
    summaries = state.get("partial_summaries", {})
    return {key: value for key, value in summaries.items() if isinstance(value, str)}


def _run_errors_from_state(state: WayfinderState) -> list[RunError]:
    errors: list[RunError] = []
    for error in state.get("errors", []):
        errors.append(
            RunError(
                node=str(error.get("node", "graph")),
                error_type=str(error.get("error_type", "graph_error")),
                message=str(error.get("message", "")),
                retryable=bool(error.get("retryable", False)),
            )
        )
    return errors
