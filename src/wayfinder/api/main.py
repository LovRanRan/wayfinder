"""FastAPI entrypoint for the Wayfinder scaffold."""

import os
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, cast
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
    RuntimeFinalWriter,
    RuntimeLLMRouting,
    SandboxStatus,
    UserProfile,
    WorkspaceRuntimeSettings,
    WorkspaceSettingsRequest,
    WorkspaceSettingsResponse,
)
from wayfinder.api.secret_box import decrypt_secret, encrypt_secret
from wayfinder.graph import build_graph
from wayfinder.graph.app import WayfinderGraph
from wayfinder.graph.runtime import (
    architecture_scanner_from_env,
    community_context_provider_from_env,
    entry_scanner_from_env,
    env_with_local_dotenv,
    final_synthesizer_from_env,
    llm_router_from_env,
    verifier_approval_decision_from_env,
    verifier_runner_from_env,
    verifier_sandbox_policy_from_env,
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
_DEFAULT_OPENAI_MODEL = "gpt-5.5"
_DEFAULT_JOB_TIMEOUT_SECONDS = 240.0
_DEFAULT_RUNTIME_BUILD_TIMEOUT_SECONDS = 15.0
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
    env = _runtime_env()
    return {
        "status": "ok",
        "service": "wayfinder",
        "commit": _deployment_commit(env),
        "job_timeout_seconds": f"{_job_timeout_seconds(env):g}",
        "runtime_build_timeout_seconds": f"{_runtime_build_timeout_seconds(env):g}",
        "graph_node_timeout_seconds": env.get("WAYFINDER_GRAPH_NODE_TIMEOUT_SECONDS", "30"),
    }


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


@app.get("/workspace/settings", response_model=WorkspaceSettingsResponse)
def get_workspace_settings(
    user: Annotated[AuthenticatedUser, Depends(_current_user)],
) -> WorkspaceSettingsResponse:
    return _workspace_settings_response(user=user, env=_runtime_env())


@app.put("/workspace/settings", response_model=WorkspaceSettingsResponse)
def update_workspace_settings(
    request: WorkspaceSettingsRequest,
    user: Annotated[AuthenticatedUser, Depends(_current_user)],
) -> WorkspaceSettingsResponse:
    env = _runtime_env()
    settings = _RUNS.workspace_settings(user_id=user.user_id)
    updates: dict[str, object] = {}

    if request.clear_openai_api_key:
        updates["openai_api_key_encrypted"] = None
        updates["openai_api_key_label"] = None

    if request.openai_api_key is not None:
        api_key = request.openai_api_key.strip()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="openai_api_key is empty",
            )
        key_material = _key_encryption_secret(env)
        updates["openai_api_key_encrypted"] = encrypt_secret(api_key, key_material)
        updates["openai_api_key_label"] = _masked_secret_label(api_key)

    if request.openai_model is not None:
        updates["openai_model"] = request.openai_model.strip()
    if request.llm_routing is not None:
        updates["llm_routing"] = request.llm_routing
    if request.final_writer is not None:
        updates["final_writer"] = request.final_writer

    updated_settings = settings.model_copy(update=updates)
    _RUNS.update_workspace_settings(user_id=user.user_id, settings=updated_settings)
    return _workspace_settings_response(user=user, env=env)


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
        run = _RUNS.get_for_user(user_id=user.user_id, job_id=job_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found") from exc
    return _mark_stale_running_run_failed(run, env=_runtime_env())


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
    current_node = "runtime_setup"
    run = _RUNS.get(job_id)
    graph_input = _RUNS.graph_input(job_id)
    _RUNS.mark_running(job_id, current_node=current_node)
    env = _runtime_env_for_user(run.user_id)
    graph_input = _graph_input_for_runtime(graph_input, env)
    trace_context = start_trace_context(
        job_id=job_id,
        phase=phase,
        state=graph_input,
        env=env,
    )

    try:
        started_at = time.monotonic()
        graph = _build_runtime_graph_with_timeout(
            env,
            timeout_seconds=min(
                _runtime_build_timeout_seconds(env),
                _job_timeout_seconds(env),
            ),
        )
        elapsed_seconds = time.monotonic() - started_at
        remaining_timeout_seconds = _job_timeout_seconds(env) - elapsed_seconds
        if remaining_timeout_seconds <= 0:
            raise JobExecutionTimeout(
                f"Wayfinder job exceeded {_job_timeout_seconds(env):g}s timeout."
            )
        current_node = "supervisor"
        _RUNS.mark_running(job_id, current_node=current_node)
        result = _run_runtime_graph_with_timeout(
            graph,
            graph_input,
            config=runnable_config_for_trace(trace_context),
            timeout_seconds=remaining_timeout_seconds,
        )
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


class JobExecutionTimeout(RuntimeError):
    """Raised when a graph run exceeds the API job timeout."""


def _run_runtime_graph_with_timeout(
    graph: WayfinderGraph,
    graph_input: WayfinderState,
    *,
    config: Any,
    timeout_seconds: float,
) -> WayfinderState:
    return _invoke_graph_with_timeout(
        graph,
        graph_input,
        config=config,
        timeout_seconds=timeout_seconds,
    )


def _build_runtime_graph_with_timeout(
    env: Mapping[str, str],
    *,
    timeout_seconds: float,
) -> WayfinderGraph:
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wayfinder-job")
    future = executor.submit(_build_runtime_graph, env)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        future.cancel()
        raise JobExecutionTimeout(
            f"Wayfinder runtime setup exceeded {timeout_seconds:g}s timeout."
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _invoke_graph_with_timeout(
    graph: WayfinderGraph,
    graph_input: WayfinderState,
    *,
    config: Any,
    timeout_seconds: float,
) -> WayfinderState:
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wayfinder-job")
    future = executor.submit(graph.invoke, graph_input, config=config)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        future.cancel()
        raise JobExecutionTimeout(
            f"Wayfinder job exceeded {timeout_seconds:g}s timeout."
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _build_runtime_graph(env: Mapping[str, str] | None = None) -> WayfinderGraph:
    active_env = env or _runtime_env()
    architecture_scanner = architecture_scanner_from_env(active_env)
    entry_scanner = entry_scanner_from_env(active_env)
    verifier_runner = verifier_runner_from_env(active_env)
    llm_router = llm_router_from_env(active_env)
    final_synthesizer = final_synthesizer_from_env(active_env)
    community_context_provider = community_context_provider_from_env(active_env)
    return build_graph(
        checkpointer=_CHECKPOINTER,
        architecture_scanner=architecture_scanner,
        entry_scanner=entry_scanner,
        verifier_runner=verifier_runner,
        llm_router=llm_router,
        final_synthesizer=final_synthesizer,
        community_context_provider=community_context_provider,
    )


def _graph_input_for_runtime(
    graph_input: WayfinderState,
    env: Mapping[str, str],
) -> WayfinderState:
    approval_decision = verifier_approval_decision_from_env(env)
    if approval_decision is None:
        return graph_input

    runtime_input = graph_input.copy()
    runtime_input["verifier_approval_decision"] = approval_decision
    return runtime_input


def _runtime_env() -> dict[str, str]:
    return env_with_local_dotenv(os.environ)


def _runtime_env_for_user(user_id: str) -> dict[str, str]:
    env = _runtime_env()
    settings = _RUNS.workspace_settings(user_id=user_id)
    if _auth_required(env):
        env.pop("OPENAI_API_KEY", None)

    _apply_workspace_runtime_settings(env, settings)
    return env


def _job_timeout_seconds(env: Mapping[str, str]) -> float:
    raw = env.get("WAYFINDER_JOB_TIMEOUT_SECONDS", str(_DEFAULT_JOB_TIMEOUT_SECONDS)).strip()
    try:
        timeout_seconds = float(raw)
    except ValueError:
        return _DEFAULT_JOB_TIMEOUT_SECONDS
    if timeout_seconds <= 0:
        return _DEFAULT_JOB_TIMEOUT_SECONDS
    return timeout_seconds


def _runtime_build_timeout_seconds(env: Mapping[str, str]) -> float:
    raw = env.get(
        "WAYFINDER_RUNTIME_BUILD_TIMEOUT_SECONDS",
        str(_DEFAULT_RUNTIME_BUILD_TIMEOUT_SECONDS),
    ).strip()
    try:
        timeout_seconds = float(raw)
    except ValueError:
        return _DEFAULT_RUNTIME_BUILD_TIMEOUT_SECONDS
    if timeout_seconds <= 0:
        return _DEFAULT_RUNTIME_BUILD_TIMEOUT_SECONDS
    return timeout_seconds


def _deployment_commit(env: Mapping[str, str]) -> str:
    for key in (
        "WAYFINDER_BUILD_COMMIT",
        "RAILWAY_GIT_COMMIT_SHA",
        "SOURCE_COMMIT",
        "GIT_COMMIT",
        "VERCEL_GIT_COMMIT_SHA",
    ):
        value = env.get(key, "").strip()
        if value:
            return value[:12]
    return "unknown"


def _mark_stale_running_run_failed(run: RunSummary, *, env: Mapping[str, str]) -> RunSummary:
    if run.status != "running":
        return run

    timeout_seconds = _job_timeout_seconds(env)
    elapsed_seconds = (datetime.now(UTC) - run.updated_at.astimezone(UTC)).total_seconds()
    if elapsed_seconds <= timeout_seconds:
        return run

    try:
        return _RUNS.mark_failed(
            run.job_id,
            exc=JobExecutionTimeout(
                f"Wayfinder job exceeded {timeout_seconds:.0f}s timeout."
            ),
            current_node=run.current_node or "graph",
            trace_metadata={
                **run.trace_metadata,
                "timeout_seconds": timeout_seconds,
                "elapsed_seconds": round(elapsed_seconds, 3),
            },
        )
    except KeyError:
        return run


def _apply_workspace_runtime_settings(
    env: dict[str, str],
    settings: WorkspaceRuntimeSettings,
) -> None:
    if settings.openai_api_key_encrypted is not None:
        key_material = env.get("WAYFINDER_KEY_ENCRYPTION_SECRET", "").strip()
        if not key_material:
            raise ValueError(
                "WAYFINDER_KEY_ENCRYPTION_SECRET is required to decrypt workspace API keys"
            )
        env["OPENAI_API_KEY"] = decrypt_secret(settings.openai_api_key_encrypted, key_material)

    if settings.openai_model is not None:
        env["WAYFINDER_OPENAI_MODEL"] = settings.openai_model
    if settings.llm_routing is not None:
        env["WAYFINDER_LLM_ROUTING"] = settings.llm_routing
    if settings.final_writer is not None:
        env["WAYFINDER_FINAL_WRITER"] = settings.final_writer


def _workspace_settings_response(
    *,
    user: AuthenticatedUser,
    env: Mapping[str, str],
) -> WorkspaceSettingsResponse:
    settings = _RUNS.workspace_settings(user_id=user.user_id)
    policy = verifier_sandbox_policy_from_env(env)
    return WorkspaceSettingsResponse(
        workspace_id=user.workspace_id,
        display_name=user.display_name,
        openai_key_configured=settings.openai_api_key_encrypted is not None,
        openai_key_label=settings.openai_api_key_label,
        openai_model=(
            settings.openai_model or env.get("WAYFINDER_OPENAI_MODEL", _DEFAULT_OPENAI_MODEL)
        ),
        llm_routing=settings.llm_routing or _llm_routing_from_env(env),
        final_writer=settings.final_writer or _final_writer_from_env(env),
        verifier_runner=(
            env.get("WAYFINDER_VERIFIER_RUNNER", "placeholder").strip().lower() or "placeholder"
        ),
        sandbox_status=cast(SandboxStatus, policy.status),
        sandbox_message=policy.message,
    )


def _key_encryption_secret(env: Mapping[str, str]) -> str:
    key_material = env.get("WAYFINDER_KEY_ENCRYPTION_SECRET", "").strip()
    if not key_material:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WAYFINDER_KEY_ENCRYPTION_SECRET is required to store workspace API keys.",
        )
    return key_material


def _masked_secret_label(secret: str) -> str:
    if len(secret) <= 8:
        return "configured"
    return f"{secret[:3]}...{secret[-4:]}"


def _llm_routing_from_env(env: Mapping[str, str]) -> RuntimeLLMRouting:
    raw = env.get("WAYFINDER_LLM_ROUTING", "off").strip().lower()
    return "openai" if raw in ("openai", "llm") or raw in _TRUE_ENV_VALUES else "off"


def _final_writer_from_env(env: Mapping[str, str]) -> RuntimeFinalWriter:
    raw = env.get("WAYFINDER_FINAL_WRITER", "deterministic").strip().lower()
    return "openai" if raw in ("openai", "llm") or raw in _TRUE_ENV_VALUES else "deterministic"
