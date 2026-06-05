"""Run and workspace persistence for the Wayfinder API."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import cast
from uuid import uuid4

from wayfinder.api.auth import (
    AuthenticatedUser,
    SessionToken,
    hash_password,
    hash_token,
    normalize_workspace_id,
    verify_password,
)
from wayfinder.api.schemas import (
    ExplainRequest,
    RunError,
    RunSummary,
    WorkspaceRuntimeSettings,
)
from wayfinder.graph.state import WayfinderState
from wayfinder.ingestion.models import RepoHandle


class InMemoryRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, RunSummary] = {}
        self._graph_inputs: dict[str, WayfinderState] = {}
        self._run_order: list[str] = []
        self._workspace_settings: dict[str, WorkspaceRuntimeSettings] = {}
        self._users_by_id: dict[str, tuple[AuthenticatedUser, str]] = {}
        self._workspace_to_user_id: dict[str, str] = {}
        self._sessions: dict[str, tuple[str, datetime]] = {}
        self._lock = RLock()

    def create_user(
        self,
        *,
        workspace_id: str,
        password: str,
        display_name: str | None,
    ) -> AuthenticatedUser:
        normalized_workspace_id = normalize_workspace_id(workspace_id)
        now = datetime.now(UTC)
        del now
        with self._lock:
            if normalized_workspace_id in self._workspace_to_user_id:
                raise ValueError("workspace already exists")
            user = AuthenticatedUser(
                user_id=str(uuid4()),
                workspace_id=normalized_workspace_id,
                display_name=display_name or normalized_workspace_id,
            )
            self._users_by_id[user.user_id] = (user, hash_password(password))
            self._workspace_to_user_id[normalized_workspace_id] = user.user_id
            return user

    def authenticate_user(self, *, workspace_id: str, password: str) -> AuthenticatedUser | None:
        normalized_workspace_id = normalize_workspace_id(workspace_id)
        with self._lock:
            user_id = self._workspace_to_user_id.get(normalized_workspace_id)
            if user_id is None:
                return None
            user, password_hash = self._users_by_id[user_id]
            return user if verify_password(password, password_hash) else None

    def create_session(self, *, user_id: str, session: SessionToken) -> None:
        with self._lock:
            self._sessions[session.token_hash] = (user_id, session.expires_at)

    def user_for_token(self, token: str) -> AuthenticatedUser | None:
        token_hash = hash_token(token)
        with self._lock:
            session = self._sessions.get(token_hash)
            if session is None:
                return None
            user_id, expires_at = session
            if expires_at <= datetime.now(UTC):
                del self._sessions[token_hash]
                return None
            user_record = self._users_by_id.get(user_id)
            return user_record[0] if user_record else None

    def delete_session(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(hash_token(token), None)

    def workspace_settings(self, *, user_id: str) -> WorkspaceRuntimeSettings:
        with self._lock:
            return self._workspace_settings.get(user_id, WorkspaceRuntimeSettings()).model_copy()

    def update_workspace_settings(
        self,
        *,
        user_id: str,
        settings: WorkspaceRuntimeSettings,
    ) -> WorkspaceRuntimeSettings:
        with self._lock:
            self._workspace_settings[user_id] = settings.model_copy()
            return self._workspace_settings[user_id].model_copy()

    def create(
        self,
        *,
        user: AuthenticatedUser,
        request: ExplainRequest,
        graph_input: WayfinderState,
    ) -> RunSummary:
        now = datetime.now(UTC)
        job_id = str(uuid4())
        graph_input["thread_id"] = job_id
        run = RunSummary(
            job_id=job_id,
            user_id=user.user_id,
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

    def get_for_user(self, *, user_id: str, job_id: str) -> RunSummary:
        with self._lock:
            run = self._runs[job_id]
            if run.user_id != user_id:
                raise KeyError(job_id)
            return run

    def list_recent(self, *, user_id: str, limit: int) -> list[RunSummary]:
        with self._lock:
            return [
                self._runs[job_id]
                for job_id in self._run_order
                if self._runs[job_id].user_id == user_id
            ][:limit]

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

    def queue_refine(self, *, user_id: str, job_id: str, correction: str) -> RunSummary:
        with self._lock:
            run = self._runs[job_id]
            if run.user_id != user_id:
                raise KeyError(job_id)
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


class SQLiteRunStore(InMemoryRunStore):
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._db_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = RLock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    run_json TEXT NOT NULL,
                    graph_input_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_runs_user_updated
                    ON runs(user_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS workspace_settings (
                    user_id TEXT PRIMARY KEY,
                    settings_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def create_user(
        self,
        *,
        workspace_id: str,
        password: str,
        display_name: str | None,
    ) -> AuthenticatedUser:
        normalized_workspace_id = normalize_workspace_id(workspace_id)
        now = datetime.now(UTC)
        user = AuthenticatedUser(
            user_id=str(uuid4()),
            workspace_id=normalized_workspace_id,
            display_name=display_name or normalized_workspace_id,
        )
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    """
                    INSERT INTO users (
                        user_id,
                        workspace_id,
                        display_name,
                        password_hash,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user.user_id,
                        user.workspace_id,
                        user.display_name,
                        hash_password(password),
                        _datetime_to_text(now),
                        _datetime_to_text(now),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("workspace already exists") from exc
        return user

    def authenticate_user(self, *, workspace_id: str, password: str) -> AuthenticatedUser | None:
        normalized_workspace_id = normalize_workspace_id(workspace_id)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT user_id, workspace_id, display_name, password_hash
                FROM users
                WHERE workspace_id = ?
                """,
                (normalized_workspace_id,),
            ).fetchone()
        if row is None or not verify_password(password, str(row["password_hash"])):
            return None
        return _user_from_row(row)

    def create_session(self, *, user_id: str, session: SessionToken) -> None:
        now = datetime.now(UTC)
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO sessions (token_hash, user_id, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    session.token_hash,
                    user_id,
                    _datetime_to_text(session.expires_at),
                    _datetime_to_text(now),
                ),
            )

    def user_for_token(self, token: str) -> AuthenticatedUser | None:
        with self._lock, self._connection:
            row = self._connection.execute(
                """
                SELECT users.user_id, users.workspace_id, users.display_name, sessions.expires_at
                FROM sessions
                JOIN users ON users.user_id = sessions.user_id
                WHERE sessions.token_hash = ?
                """,
                (hash_token(token),),
            ).fetchone()
            if row is None:
                return None
            expires_at = _datetime_from_text(str(row["expires_at"]))
            if expires_at <= datetime.now(UTC):
                self._connection.execute(
                    "DELETE FROM sessions WHERE token_hash = ?",
                    (hash_token(token),),
                )
                return None
        return _user_from_row(row)

    def delete_session(self, token: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM sessions WHERE token_hash = ?",
                (hash_token(token),),
            )

    def workspace_settings(self, *, user_id: str) -> WorkspaceRuntimeSettings:
        with self._lock:
            row = self._connection.execute(
                "SELECT settings_json FROM workspace_settings WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return WorkspaceRuntimeSettings()
        return WorkspaceRuntimeSettings.model_validate_json(str(row["settings_json"]))

    def update_workspace_settings(
        self,
        *,
        user_id: str,
        settings: WorkspaceRuntimeSettings,
    ) -> WorkspaceRuntimeSettings:
        now = datetime.now(UTC)
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO workspace_settings (
                    user_id,
                    settings_json,
                    updated_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    user_id,
                    settings.model_dump_json(exclude_none=True),
                    _datetime_to_text(now),
                ),
            )
        return settings.model_copy()

    def create(
        self,
        *,
        user: AuthenticatedUser,
        request: ExplainRequest,
        graph_input: WayfinderState,
    ) -> RunSummary:
        now = datetime.now(UTC)
        job_id = str(uuid4())
        graph_input["thread_id"] = job_id
        run = RunSummary(
            job_id=job_id,
            user_id=user.user_id,
            repo_url=request.repo_url,
            query=request.query,
            status="queued",
            current_node="queued",
            created_at=now,
            updated_at=now,
        )
        self._write_run(run=run, graph_input=graph_input)
        return run

    def get(self, job_id: str) -> RunSummary:
        run, _graph_input = self._read_run(job_id)
        return run

    def get_for_user(self, *, user_id: str, job_id: str) -> RunSummary:
        run, _graph_input = self._read_run(job_id)
        if run.user_id != user_id:
            raise KeyError(job_id)
        return run

    def list_recent(self, *, user_id: str, limit: int) -> list[RunSummary]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT run_json
                FROM runs
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [RunSummary.model_validate_json(str(row["run_json"])) for row in rows]

    def graph_input(self, job_id: str) -> WayfinderState:
        _run, graph_input = self._read_run(job_id)
        return graph_input

    def queue_refine(self, *, user_id: str, job_id: str, correction: str) -> RunSummary:
        run, graph_input = self._read_run(job_id)
        if run.user_id != user_id:
            raise KeyError(job_id)
        if run.status in ("queued", "running"):
            raise ValueError("job is still running")

        query = f"{run.query}\n\nUser correction: {correction}"
        corrections = [*run.user_corrections, correction]
        graph_input["query"] = query
        graph_input["user_corrections"] = corrections
        graph_input["thread_id"] = job_id
        updated = run.model_copy(
            update={
                "query": query,
                "status": "queued",
                "current_node": "queued",
                "user_corrections": corrections,
                "updated_at": datetime.now(UTC),
            }
        )
        self._write_run(run=updated, graph_input=graph_input)
        return updated

    def _update(self, job_id: str, **updates: object) -> RunSummary:
        run, graph_input = self._read_run(job_id)
        updated = run.model_copy(update=updates)
        self._write_run(run=updated, graph_input=graph_input)
        return updated

    def _write_run(self, *, run: RunSummary, graph_input: WayfinderState) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO runs (
                    job_id,
                    user_id,
                    run_json,
                    graph_input_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run.job_id,
                    run.user_id,
                    run.model_dump_json(),
                    json.dumps(_graph_input_to_jsonable(graph_input), sort_keys=True),
                    _datetime_to_text(run.created_at),
                    _datetime_to_text(run.updated_at),
                ),
            )

    def _read_run(self, job_id: str) -> tuple[RunSummary, WayfinderState]:
        with self._lock:
            row = self._connection.execute(
                "SELECT run_json, graph_input_json FROM runs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return (
            RunSummary.model_validate_json(str(row["run_json"])),
            _graph_input_from_jsonable(json.loads(str(row["graph_input_json"]))),
        )


def _user_from_row(row: sqlite3.Row) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=str(row["user_id"]),
        workspace_id=str(row["workspace_id"]),
        display_name=str(row["display_name"]),
    )


def _datetime_to_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _datetime_from_text(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


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


def _graph_input_to_jsonable(graph_input: WayfinderState) -> dict[str, object]:
    jsonable: dict[str, object] = {}
    for key, value in graph_input.items():
        if key == "repo_handle" and isinstance(value, RepoHandle):
            jsonable[key] = value.model_dump(mode="json")
        elif _is_json_scalar(value):
            jsonable[key] = value
        elif isinstance(value, Sequence) and not isinstance(value, str):
            jsonable[key] = list(value)
        elif isinstance(value, dict):
            jsonable[key] = value
    return jsonable


def _graph_input_from_jsonable(payload: object) -> WayfinderState:
    if not isinstance(payload, dict):
        return cast(WayfinderState, {})
    restored = dict(payload)
    repo_handle = restored.get("repo_handle")
    if isinstance(repo_handle, dict):
        restored["repo_handle"] = RepoHandle.model_validate(repo_handle)
    return cast(WayfinderState, restored)


def _is_json_scalar(value: object) -> bool:
    return value is None or isinstance(value, str | int | float | bool)
