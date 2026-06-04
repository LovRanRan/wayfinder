"""FastAPI entrypoint for the Wayfinder scaffold."""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, cast
from urllib.parse import urlparse

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, status
from langgraph.checkpoint.memory import InMemorySaver

from wayfinder.api.auth import AuthenticatedUser, issue_session_token
from wayfinder.api.observability import (
    finish_trace_metadata,
    runnable_config_for_trace,
    start_trace_context,
)
from wayfinder.api.run_store import InMemoryRunStore, SQLiteRunStore
from wayfinder.api.schemas import (
    AuthRequest,
    AuthResponse,
    ExplainRequest,
    RefineRequest,
    RunSummary,
    UserProfile,
)
from wayfinder.graph import build_graph
from wayfinder.graph.app import WayfinderGraph
from wayfinder.graph.runtime import (
    architecture_scanner_from_env,
    community_context_provider_from_env,
    entry_scanner_from_env,
    env_with_local_dotenv,
    final_synthesizer_from_env,
    llm_router_from_env,
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
_DEFAULT_DEV_USER = AuthenticatedUser(
    user_id="local-dev",
    workspace_id="local-dev",
    display_name="Local developer",
)


def _run_store_from_env(env: Mapping[str, str]) -> InMemoryRunStore | SQLiteRunStore:
    store_mode = env.get("WAYFINDER_RUN_STORE", "").strip().lower()
    sqlite_path = env.get("WAYFINDER_RUN_STORE_PATH", "").strip()
    if store_mode == "sqlite" or sqlite_path:
        return SQLiteRunStore(Path(sqlite_path or ".wayfinder/runs.sqlite").expanduser())
    return InMemoryRunStore()


_RUNS = _run_store_from_env(env_with_local_dotenv(os.environ))


def _current_user(request: Request) -> AuthenticatedUser:
    token = _bearer_token_from_request(request)
    if token is not None:
        user = _RUNS.user_for_token(token)
        if user is not None:
            return user

    if _auth_required(_runtime_env()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login required")

    return AuthenticatedUser(
        user_id=os.getenv("WAYFINDER_DEV_USER_ID", _DEFAULT_DEV_USER.user_id),
        workspace_id=os.getenv("WAYFINDER_DEV_WORKSPACE_ID", _DEFAULT_DEV_USER.workspace_id),
        display_name=os.getenv("WAYFINDER_DEV_DISPLAY_NAME", _DEFAULT_DEV_USER.display_name),
    )


def _auth_required(env: Mapping[str, str]) -> bool:
    return env.get("WAYFINDER_REQUIRE_AUTH", "").strip().lower() in _TRUE_ENV_VALUES


def _bearer_token_from_request(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if separator and scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return None


def _auth_response_for_user(user: AuthenticatedUser) -> AuthResponse:
    session = issue_session_token(ttl_days=_session_ttl_days(_runtime_env()))
    _RUNS.create_session(user_id=user.user_id, session=session)
    return AuthResponse(user=_profile_for_user(user), token=session.token)


def _profile_for_user(user: AuthenticatedUser) -> UserProfile:
    return UserProfile(
        user_id=user.user_id,
        workspace_id=user.workspace_id,
        display_name=user.display_name,
    )


def _session_ttl_days(env: Mapping[str, str]) -> int:
    raw = env.get("WAYFINDER_SESSION_TTL_DAYS", "30").strip()
    try:
        ttl_days = int(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WAYFINDER_SESSION_TTL_DAYS must be an integer.",
        ) from exc
    if ttl_days < 1:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WAYFINDER_SESSION_TTL_DAYS must be positive.",
        )
    return ttl_days


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "wayfinder"}


@app.get("/runs", response_model=list[RunSummary])
def list_runs(
    user: Annotated[AuthenticatedUser, Depends(_current_user)],
    limit: int = Query(default=10, ge=1, le=50),
) -> list[RunSummary]:
    return _RUNS.list_recent(user_id=user.user_id, limit=limit)


@app.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(request: AuthRequest) -> AuthResponse:
    try:
        user = _RUNS.create_user(
            workspace_id=request.workspace_id,
            password=request.password,
            display_name=request.display_name,
        )
    except ValueError as exc:
        status_code = (
            status.HTTP_409_CONFLICT
            if str(exc) == "workspace already exists"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    return _auth_response_for_user(user)


@app.post("/auth/login", response_model=AuthResponse)
def login(request: AuthRequest) -> AuthResponse:
    try:
        user = _RUNS.authenticate_user(
            workspace_id=request.workspace_id,
            password=request.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    return _auth_response_for_user(user)


@app.get("/auth/me", response_model=UserProfile)
def me(user: Annotated[AuthenticatedUser, Depends(_current_user)]) -> UserProfile:
    return _profile_for_user(user)


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> None:
    token = _bearer_token_from_request(request)
    if token is not None:
        _RUNS.delete_session(token)


@app.post("/explain", response_model=RunSummary, status_code=status.HTTP_202_ACCEPTED)
def explain(
    request: ExplainRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[AuthenticatedUser, Depends(_current_user)],
) -> RunSummary:
    graph_input = _graph_input_from_request(request)
    run = _RUNS.create(user=user, request=request, graph_input=graph_input)
    background_tasks.add_task(_execute_job, run.job_id, "explain")
    return run


def _graph_input_from_request(request: ExplainRequest) -> WayfinderState:
    graph_input: dict[str, object] = {
        "repo_url": request.repo_url,
        "query": request.query,
    }
    repo_handle = _repo_handle_from_ref(request.repo_url, _runtime_env())
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
def get_status(
    job_id: str,
    user: Annotated[AuthenticatedUser, Depends(_current_user)],
) -> RunSummary:
    try:
        return _RUNS.get_for_user(user_id=user.user_id, job_id=job_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found") from exc


@app.post(
    "/refine/{job_id}",
    response_model=RunSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
def refine(
    job_id: str,
    request: RefineRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[AuthenticatedUser, Depends(_current_user)],
) -> RunSummary:
    try:
        updated = _RUNS.queue_refine(
            user_id=user.user_id,
            job_id=job_id,
            correction=request.correction,
        )
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
    env = _runtime_env()
    trace_context = start_trace_context(
        job_id=job_id,
        phase=phase,
        state=graph_input,
        env=env,
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
    env = _runtime_env()
    architecture_scanner = architecture_scanner_from_env(env)
    entry_scanner = entry_scanner_from_env(env)
    verifier_runner = verifier_runner_from_env(env)
    llm_router = llm_router_from_env(env)
    final_synthesizer = final_synthesizer_from_env(env)
    community_context_provider = community_context_provider_from_env(env)
    return build_graph(
        checkpointer=_CHECKPOINTER,
        architecture_scanner=architecture_scanner,
        entry_scanner=entry_scanner,
        verifier_runner=verifier_runner,
        llm_router=llm_router,
        final_synthesizer=final_synthesizer,
        community_context_provider=community_context_provider,
    )


def _runtime_env() -> dict[str, str]:
    return env_with_local_dotenv(os.environ)
