"""Run and workspace persistence for the Wayfinder API."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Literal, cast
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
    ActiveRepoContext,
    ConversationThread,
    ExplainRequest,
    RunError,
    RunSummary,
    ThreadMessage,
    ThreadMessageRole,
    ThreadStatus,
    WorkspaceRuntimeSettings,
)

WayfinderState = dict[str, Any]


class InMemoryRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, RunSummary] = {}
        self._graph_inputs: dict[str, WayfinderState] = {}
        self._run_order: list[str] = []
        self._workspace_settings: dict[str, WorkspaceRuntimeSettings] = {}
        self._users_by_id: dict[str, tuple[AuthenticatedUser, str]] = {}
        self._workspace_to_user_id: dict[str, str] = {}
        self._sessions: dict[str, tuple[str, datetime]] = {}
        self._threads: dict[str, ConversationThread] = {}
        self._thread_order: list[str] = []
        self._thread_messages: dict[str, list[ThreadMessage]] = {}
        self._active_contexts: dict[str, ActiveRepoContext] = {}
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
        conversation_thread_id: str | None = None,
        source_message_id: str | None = None,
    ) -> RunSummary:
        now = datetime.now(UTC)
        job_id = str(uuid4())
        graph_input["thread_id"] = job_id
        graph_input["user_id"] = user.user_id
        if conversation_thread_id is not None:
            graph_input["conversation_thread_id"] = conversation_thread_id
        if source_message_id is not None:
            graph_input["source_message_id"] = source_message_id
        run = RunSummary(
            job_id=job_id,
            user_id=user.user_id,
            repo_url=request.repo_url,
            query=request.query,
            status="queued",
            current_node="queued",
            trace_metadata=_conversation_trace_metadata(
                conversation_thread_id=conversation_thread_id,
                source_message_id=source_message_id,
            ),
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._runs[job_id] = run
            self._graph_inputs[job_id] = _copy_graph_input(graph_input)
            self._run_order.insert(0, job_id)
            if conversation_thread_id is not None:
                self._set_thread_running(
                    thread_id=conversation_thread_id,
                    run_id=job_id,
                    updated_at=now,
                )
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
        existing = self.get(job_id)
        updated = self._update(
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
            claim_provenance=result.get("claim_provenance", []),
            trace_metadata={**existing.trace_metadata, **trace_metadata},
            updated_at=datetime.now(UTC),
        )
        self._record_thread_assistant_message_from_run(updated)
        return updated

    def mark_failed(
        self,
        job_id: str,
        *,
        exc: Exception,
        current_node: str,
        trace_metadata: dict[str, str | int | float | bool | None],
    ) -> RunSummary:
        message = str(exc) or type(exc).__name__
        existing = self.get(job_id)
        updated = self._update(
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
            trace_metadata={**existing.trace_metadata, **trace_metadata},
            updated_at=datetime.now(UTC),
        )
        self._record_thread_assistant_message_from_run(updated)
        return updated

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

    def create_thread(
        self,
        *,
        user: AuthenticatedUser,
        repo_url: str,
        title: str | None = None,
    ) -> ConversationThread:
        now = datetime.now(UTC)
        repo_name = _repo_name_from_ref(repo_url)
        thread = ConversationThread(
            thread_id=str(uuid4()),
            user_id=user.user_id,
            repo_url=repo_url,
            repo_name=repo_name,
            title=(title or repo_name).strip(),
            status="active",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._threads[thread.thread_id] = thread
            self._thread_messages[thread.thread_id] = []
            self._thread_order.insert(0, thread.thread_id)
        return thread

    def list_threads(self, *, user_id: str, limit: int) -> list[ConversationThread]:
        with self._lock:
            threads = [
                self._threads[thread_id]
                for thread_id in self._thread_order
                if self._threads[thread_id].user_id == user_id
                and self._threads[thread_id].status != "archived"
            ]
        return sorted(threads, key=lambda thread: thread.updated_at, reverse=True)[:limit]

    def get_thread_for_user(self, *, user_id: str, thread_id: str) -> ConversationThread:
        with self._lock:
            thread = self._threads[thread_id]
            if thread.user_id != user_id:
                raise KeyError(thread_id)
            return thread

    def messages_for_thread(self, *, user_id: str, thread_id: str) -> list[ThreadMessage]:
        self.get_thread_for_user(user_id=user_id, thread_id=thread_id)
        with self._lock:
            return list(self._thread_messages.get(thread_id, []))

    def runs_for_thread(self, *, user_id: str, thread_id: str) -> list[RunSummary]:
        self.get_thread_for_user(user_id=user_id, thread_id=thread_id)
        with self._lock:
            runs = [
                run
                for run in self._runs.values()
                if run.user_id == user_id
                and run.trace_metadata.get("conversation_thread_id") == thread_id
            ]
        return sorted(runs, key=lambda run: run.created_at)

    def archive_thread(self, *, user_id: str, thread_id: str) -> ActiveRepoContext:
        thread = self.get_thread_for_user(user_id=user_id, thread_id=thread_id)
        if thread.status == "running":
            raise ValueError("thread is running")

        now = datetime.now(UTC)
        with self._lock:
            self._threads[thread_id] = thread.model_copy(
                update={"status": "archived", "updated_at": now}
            )
            context = self._active_contexts.get(user_id)
            if context is not None and context.default_thread_id == thread_id:
                cleared = _empty_active_context(user_id=user_id)
                self._active_contexts[user_id] = cleared
                return cleared
        return self.active_context_for_user(user_id=user_id)

    def append_thread_message(
        self,
        *,
        user_id: str,
        thread_id: str,
        role: ThreadMessageRole,
        content: str,
        source_run_id: str | None = None,
        evidence_refs: list[str] | None = None,
        verified_count: int = 0,
        unverified_count: int = 0,
        contradicted_count: int = 0,
        trace_metadata: dict[str, str | int | float | bool | None] | None = None,
    ) -> ThreadMessage:
        self.get_thread_for_user(user_id=user_id, thread_id=thread_id)
        now = datetime.now(UTC)
        message = ThreadMessage(
            message_id=str(uuid4()),
            thread_id=thread_id,
            role=role,
            content=content,
            created_at=now,
            source_run_id=source_run_id,
            evidence_refs=evidence_refs or [],
            verified_count=verified_count,
            unverified_count=unverified_count,
            contradicted_count=contradicted_count,
            trace_metadata=trace_metadata or {},
        )
        with self._lock:
            self._thread_messages.setdefault(thread_id, []).append(message)
            thread = self._threads[thread_id]
            self._threads[thread_id] = thread.model_copy(
                update={
                    "updated_at": now,
                    "summary_memory": _summary_memory_from_messages(
                        self._thread_messages[thread_id]
                    ),
                }
            )
        return message

    def build_thread_memory_packet(
        self,
        *,
        user_id: str,
        thread_id: str,
        max_messages: int = 6,
        max_chars: int = 4000,
    ) -> str:
        thread = self.get_thread_for_user(user_id=user_id, thread_id=thread_id)
        messages = self.messages_for_thread(user_id=user_id, thread_id=thread_id)
        return _bounded_memory_packet(
            thread=thread,
            messages=messages,
            max_messages=max_messages,
            max_chars=max_chars,
        )

    def active_context_for_user(self, *, user_id: str) -> ActiveRepoContext:
        with self._lock:
            existing = self._active_contexts.get(user_id)
            if existing is not None:
                return existing
        latest_thread = next(
            (thread for thread in self.list_threads(user_id=user_id, limit=1)),
            None,
        )
        if latest_thread is None:
            return _empty_active_context(user_id=user_id)
        return _context_from_thread(latest_thread)

    def set_active_context(
        self,
        *,
        user_id: str,
        thread: ConversationThread,
        active_focus: str | None = None,
    ) -> ActiveRepoContext:
        context = _context_from_thread(thread, active_focus=active_focus)
        with self._lock:
            self._active_contexts[user_id] = context
        return context

    def clear_active_context(self, *, user_id: str) -> ActiveRepoContext:
        context = _empty_active_context(user_id=user_id)
        with self._lock:
            self._active_contexts[user_id] = context
        return context

    def update_active_focus(
        self,
        *,
        user_id: str,
        active_focus: str | None,
        selected_files: list[str] | None = None,
        selected_symbols: list[str] | None = None,
    ) -> ActiveRepoContext:
        context = self.active_context_for_user(user_id=user_id)
        updated = context.model_copy(
            update={
                "active_focus": active_focus,
                "selected_files": (
                    selected_files if selected_files is not None else context.selected_files
                ),
                "selected_symbols": (
                    selected_symbols if selected_symbols is not None else context.selected_symbols
                ),
                "updated_at": datetime.now(UTC),
            }
        )
        with self._lock:
            self._active_contexts[user_id] = updated
        return updated

    def _set_thread_running(
        self,
        *,
        thread_id: str,
        run_id: str,
        updated_at: datetime,
    ) -> None:
        thread = self._threads.get(thread_id)
        if thread is None:
            return
        self._threads[thread_id] = thread.model_copy(
            update={
                "status": "running",
                "last_run_id": run_id,
                "updated_at": updated_at,
            }
        )

    def _record_thread_assistant_message_from_run(self, run: RunSummary) -> None:
        thread_id = _string_trace_value(run.trace_metadata.get("conversation_thread_id"))
        if thread_id is None:
            return
        with self._lock:
            thread = self._threads.get(thread_id)
            if thread is None or thread.user_id != run.user_id:
                return
            if _message_for_run_exists(self._thread_messages.get(thread_id, []), run.job_id):
                return
        role: ThreadMessageRole = "assistant" if run.status == "completed" else "system"
        content = (
            run.final_output
            if run.status == "completed" and run.final_output
            else f"Wayfinder run failed: {run.error or 'unknown error'}"
        )
        self.append_thread_message(
            user_id=run.user_id,
            thread_id=thread_id,
            role=role,
            content=content,
            source_run_id=run.job_id,
            evidence_refs=_evidence_refs_from_run(run),
            verified_count=run.verified_count,
            unverified_count=run.unverified_count,
            contradicted_count=run.contradicted_count,
            trace_metadata=run.trace_metadata,
        )
        with self._lock:
            thread = self._threads[thread_id]
            self._threads[thread_id] = thread.model_copy(
                update={
                    "status": "active" if run.status == "completed" else "failed",
                    "last_run_id": run.job_id,
                    "updated_at": run.updated_at,
                }
            )

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
                CREATE TABLE IF NOT EXISTS conversation_threads (
                    thread_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    repo_url TEXT NOT NULL,
                    repo_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_run_id TEXT,
                    summary_memory TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_conversation_threads_user_updated
                    ON conversation_threads(user_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS thread_messages (
                    message_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL REFERENCES conversation_threads(thread_id),
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_run_id TEXT,
                    evidence_refs_json TEXT NOT NULL,
                    verified_count INTEGER NOT NULL,
                    unverified_count INTEGER NOT NULL,
                    contradicted_count INTEGER NOT NULL,
                    trace_metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_thread_messages_thread_created
                    ON thread_messages(thread_id, created_at ASC);
                CREATE TABLE IF NOT EXISTS active_repo_contexts (
                    user_id TEXT PRIMARY KEY REFERENCES users(user_id),
                    context_json TEXT NOT NULL,
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
        conversation_thread_id: str | None = None,
        source_message_id: str | None = None,
    ) -> RunSummary:
        now = datetime.now(UTC)
        job_id = str(uuid4())
        graph_input["thread_id"] = job_id
        graph_input["user_id"] = user.user_id
        if conversation_thread_id is not None:
            graph_input["conversation_thread_id"] = conversation_thread_id
        if source_message_id is not None:
            graph_input["source_message_id"] = source_message_id
        run = RunSummary(
            job_id=job_id,
            user_id=user.user_id,
            repo_url=request.repo_url,
            query=request.query,
            status="queued",
            current_node="queued",
            trace_metadata=_conversation_trace_metadata(
                conversation_thread_id=conversation_thread_id,
                source_message_id=source_message_id,
            ),
            created_at=now,
            updated_at=now,
        )
        self._write_run(run=run, graph_input=graph_input)
        if conversation_thread_id is not None:
            self._set_thread_running(
                thread_id=conversation_thread_id,
                run_id=job_id,
                updated_at=now,
            )
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

    def create_thread(
        self,
        *,
        user: AuthenticatedUser,
        repo_url: str,
        title: str | None = None,
    ) -> ConversationThread:
        now = datetime.now(UTC)
        repo_name = _repo_name_from_ref(repo_url)
        thread = ConversationThread(
            thread_id=str(uuid4()),
            user_id=user.user_id,
            repo_url=repo_url,
            repo_name=repo_name,
            title=(title or repo_name).strip(),
            status="active",
            created_at=now,
            updated_at=now,
        )
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO conversation_threads (
                    thread_id,
                    user_id,
                    repo_url,
                    repo_name,
                    title,
                    status,
                    last_run_id,
                    summary_memory,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thread.thread_id,
                    thread.user_id,
                    thread.repo_url,
                    thread.repo_name,
                    thread.title,
                    thread.status,
                    thread.last_run_id,
                    thread.summary_memory,
                    _datetime_to_text(thread.created_at),
                    _datetime_to_text(thread.updated_at),
                ),
            )
        return thread

    def list_threads(self, *, user_id: str, limit: int) -> list[ConversationThread]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM conversation_threads
                WHERE user_id = ? AND status != 'archived'
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [_thread_from_row(row) for row in rows]

    def get_thread_for_user(self, *, user_id: str, thread_id: str) -> ConversationThread:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM conversation_threads WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()
        if row is None:
            raise KeyError(thread_id)
        thread = _thread_from_row(row)
        if thread.user_id != user_id:
            raise KeyError(thread_id)
        return thread

    def messages_for_thread(self, *, user_id: str, thread_id: str) -> list[ThreadMessage]:
        self.get_thread_for_user(user_id=user_id, thread_id=thread_id)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT *
                FROM thread_messages
                WHERE thread_id = ?
                ORDER BY created_at ASC
                """,
                (thread_id,),
            ).fetchall()
        return [_message_from_row(row) for row in rows]

    def runs_for_thread(self, *, user_id: str, thread_id: str) -> list[RunSummary]:
        self.get_thread_for_user(user_id=user_id, thread_id=thread_id)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT run_json
                FROM runs
                WHERE user_id = ?
                ORDER BY created_at ASC
                """,
                (user_id,),
            ).fetchall()
        runs = [RunSummary.model_validate_json(str(row["run_json"])) for row in rows]
        return [
            run
            for run in runs
            if run.trace_metadata.get("conversation_thread_id") == thread_id
        ]

    def archive_thread(self, *, user_id: str, thread_id: str) -> ActiveRepoContext:
        thread = self.get_thread_for_user(user_id=user_id, thread_id=thread_id)
        if thread.status == "running":
            raise ValueError("thread is running")

        now = datetime.now(UTC)
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE conversation_threads
                SET status = ?, updated_at = ?
                WHERE thread_id = ?
                """,
                ("archived", _datetime_to_text(now), thread_id),
            )
            row = self._connection.execute(
                "SELECT context_json FROM active_repo_contexts WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is not None:
                context = ActiveRepoContext.model_validate_json(str(row["context_json"]))
                if context.default_thread_id == thread_id:
                    cleared = _empty_active_context(user_id=user_id)
                    self._connection.execute(
                        """
                        INSERT OR REPLACE INTO active_repo_contexts (
                            user_id,
                            context_json,
                            updated_at
                        )
                        VALUES (?, ?, ?)
                        """,
                        (
                            user_id,
                            cleared.model_dump_json(),
                            _datetime_to_text(cleared.updated_at),
                        ),
                    )
                    return cleared
        return self.active_context_for_user(user_id=user_id)

    def append_thread_message(
        self,
        *,
        user_id: str,
        thread_id: str,
        role: ThreadMessageRole,
        content: str,
        source_run_id: str | None = None,
        evidence_refs: list[str] | None = None,
        verified_count: int = 0,
        unverified_count: int = 0,
        contradicted_count: int = 0,
        trace_metadata: dict[str, str | int | float | bool | None] | None = None,
    ) -> ThreadMessage:
        self.get_thread_for_user(user_id=user_id, thread_id=thread_id)
        now = datetime.now(UTC)
        message = ThreadMessage(
            message_id=str(uuid4()),
            thread_id=thread_id,
            role=role,
            content=content,
            created_at=now,
            source_run_id=source_run_id,
            evidence_refs=evidence_refs or [],
            verified_count=verified_count,
            unverified_count=unverified_count,
            contradicted_count=contradicted_count,
            trace_metadata=trace_metadata or {},
        )
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO thread_messages (
                    message_id,
                    thread_id,
                    role,
                    content,
                    source_run_id,
                    evidence_refs_json,
                    verified_count,
                    unverified_count,
                    contradicted_count,
                    trace_metadata_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    message.thread_id,
                    message.role,
                    message.content,
                    message.source_run_id,
                    json.dumps(message.evidence_refs, sort_keys=True),
                    message.verified_count,
                    message.unverified_count,
                    message.contradicted_count,
                    json.dumps(message.trace_metadata, sort_keys=True),
                    _datetime_to_text(message.created_at),
                ),
            )
            rows = self._connection.execute(
                """
                SELECT *
                FROM thread_messages
                WHERE thread_id = ?
                ORDER BY created_at ASC
                """,
                (thread_id,),
            ).fetchall()
            summary_memory = _summary_memory_from_messages([_message_from_row(row) for row in rows])
            self._connection.execute(
                """
                UPDATE conversation_threads
                SET updated_at = ?, summary_memory = ?
                WHERE thread_id = ?
                """,
                (_datetime_to_text(now), summary_memory, thread_id),
            )
        return message

    def build_thread_memory_packet(
        self,
        *,
        user_id: str,
        thread_id: str,
        max_messages: int = 6,
        max_chars: int = 4000,
    ) -> str:
        thread = self.get_thread_for_user(user_id=user_id, thread_id=thread_id)
        messages = self.messages_for_thread(user_id=user_id, thread_id=thread_id)
        return _bounded_memory_packet(
            thread=thread,
            messages=messages,
            max_messages=max_messages,
            max_chars=max_chars,
        )

    def active_context_for_user(self, *, user_id: str) -> ActiveRepoContext:
        with self._lock:
            row = self._connection.execute(
                "SELECT context_json FROM active_repo_contexts WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is not None:
            return ActiveRepoContext.model_validate_json(str(row["context_json"]))

        latest = next((thread for thread in self.list_threads(user_id=user_id, limit=1)), None)
        if latest is None:
            return _empty_active_context(user_id=user_id)
        return _context_from_thread(latest)

    def set_active_context(
        self,
        *,
        user_id: str,
        thread: ConversationThread,
        active_focus: str | None = None,
    ) -> ActiveRepoContext:
        context = _context_from_thread(thread, active_focus=active_focus)
        self._write_active_context(user_id=user_id, context=context)
        return context

    def clear_active_context(self, *, user_id: str) -> ActiveRepoContext:
        context = _empty_active_context(user_id=user_id)
        self._write_active_context(user_id=user_id, context=context)
        return context

    def update_active_focus(
        self,
        *,
        user_id: str,
        active_focus: str | None,
        selected_files: list[str] | None = None,
        selected_symbols: list[str] | None = None,
    ) -> ActiveRepoContext:
        context = self.active_context_for_user(user_id=user_id)
        updated = context.model_copy(
            update={
                "active_focus": active_focus,
                "selected_files": (
                    selected_files if selected_files is not None else context.selected_files
                ),
                "selected_symbols": (
                    selected_symbols if selected_symbols is not None else context.selected_symbols
                ),
                "updated_at": datetime.now(UTC),
            }
        )
        self._write_active_context(user_id=user_id, context=updated)
        return updated

    def _write_active_context(self, *, user_id: str, context: ActiveRepoContext) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO active_repo_contexts (
                    user_id,
                    context_json,
                    updated_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    user_id,
                    context.model_dump_json(),
                    _datetime_to_text(context.updated_at),
                ),
            )

    def _set_thread_running(
        self,
        *,
        thread_id: str,
        run_id: str,
        updated_at: datetime,
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE conversation_threads
                SET status = ?, last_run_id = ?, updated_at = ?
                WHERE thread_id = ?
                """,
                ("running", run_id, _datetime_to_text(updated_at), thread_id),
            )

    def _record_thread_assistant_message_from_run(self, run: RunSummary) -> None:
        thread_id = _string_trace_value(run.trace_metadata.get("conversation_thread_id"))
        if thread_id is None:
            return
        with self._lock:
            thread_row = self._connection.execute(
                "SELECT user_id FROM conversation_threads WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()
            if thread_row is None or str(thread_row["user_id"]) != run.user_id:
                return
            existing = self._connection.execute(
                """
                SELECT 1
                FROM thread_messages
                WHERE thread_id = ? AND source_run_id = ?
                LIMIT 1
                """,
                (thread_id, run.job_id),
            ).fetchone()
            if existing is not None:
                return
        role: ThreadMessageRole = "assistant" if run.status == "completed" else "system"
        content = (
            run.final_output
            if run.status == "completed" and run.final_output
            else f"Wayfinder run failed: {run.error or 'unknown error'}"
        )
        self.append_thread_message(
            user_id=run.user_id,
            thread_id=thread_id,
            role=role,
            content=content,
            source_run_id=run.job_id,
            evidence_refs=_evidence_refs_from_run(run),
            verified_count=run.verified_count,
            unverified_count=run.unverified_count,
            contradicted_count=run.contradicted_count,
            trace_metadata=run.trace_metadata,
        )
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE conversation_threads
                SET status = ?, last_run_id = ?, updated_at = ?
                WHERE thread_id = ?
                """,
                (
                    "active" if run.status == "completed" else "failed",
                    run.job_id,
                    _datetime_to_text(run.updated_at),
                    thread_id,
                ),
            )


def _user_from_row(row: sqlite3.Row) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=str(row["user_id"]),
        workspace_id=str(row["workspace_id"]),
        display_name=str(row["display_name"]),
    )


def _thread_from_row(row: sqlite3.Row) -> ConversationThread:
    return ConversationThread(
        thread_id=str(row["thread_id"]),
        user_id=str(row["user_id"]),
        repo_url=str(row["repo_url"]),
        repo_name=str(row["repo_name"]),
        title=str(row["title"]),
        status=cast(ThreadStatus, str(row["status"])),
        created_at=_datetime_from_text(str(row["created_at"])),
        updated_at=_datetime_from_text(str(row["updated_at"])),
        last_run_id=_optional_text(row["last_run_id"]),
        summary_memory=_optional_text(row["summary_memory"]),
    )


def _message_from_row(row: sqlite3.Row) -> ThreadMessage:
    return ThreadMessage(
        message_id=str(row["message_id"]),
        thread_id=str(row["thread_id"]),
        role=cast(ThreadMessageRole, str(row["role"])),
        content=str(row["content"]),
        created_at=_datetime_from_text(str(row["created_at"])),
        source_run_id=_optional_text(row["source_run_id"]),
        evidence_refs=_json_string_list(str(row["evidence_refs_json"])),
        verified_count=int(row["verified_count"]),
        unverified_count=int(row["unverified_count"]),
        contradicted_count=int(row["contradicted_count"]),
        trace_metadata=_json_trace_metadata(str(row["trace_metadata_json"])),
    )


def _empty_active_context(*, user_id: str) -> ActiveRepoContext:
    return ActiveRepoContext(
        context_id=f"active:{user_id}",
        user_id=user_id,
        updated_at=datetime.now(UTC),
    )


def _context_from_thread(
    thread: ConversationThread,
    *,
    active_focus: str | None = None,
) -> ActiveRepoContext:
    return ActiveRepoContext(
        context_id=f"active:{thread.user_id}",
        user_id=thread.user_id,
        repo_url=thread.repo_url,
        repo_name=thread.repo_name,
        default_thread_id=thread.thread_id,
        last_run_id=thread.last_run_id,
        status=_context_status_from_thread(thread.status),
        summary_memory=thread.summary_memory,
        active_focus=active_focus,
        selected_files=[active_focus] if active_focus is not None and "/" in active_focus else [],
        selected_symbols=(
            [active_focus] if active_focus is not None and "/" not in active_focus else []
        ),
        updated_at=thread.updated_at,
    )


def _context_status_from_thread(
    status: ThreadStatus,
) -> Literal["empty", "ready", "running", "failed"]:
    if status == "running":
        return "running"
    if status == "failed":
        return "failed"
    return "ready"


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


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
    return copied


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
        if key == "repo_handle" and _is_repo_handle(value):
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
        from wayfinder.ingestion.models import RepoHandle

        restored["repo_handle"] = RepoHandle.model_validate(repo_handle)
    return cast(WayfinderState, restored)


def _is_repo_handle(value: object) -> bool:
    from wayfinder.ingestion.models import RepoHandle

    return isinstance(value, RepoHandle)


def _is_json_scalar(value: object) -> bool:
    return value is None or isinstance(value, str | int | float | bool)


def _conversation_trace_metadata(
    *,
    conversation_thread_id: str | None,
    source_message_id: str | None,
) -> dict[str, str | int | float | bool | None]:
    metadata: dict[str, str | int | float | bool | None] = {}
    if conversation_thread_id is not None:
        metadata["conversation_thread_id"] = conversation_thread_id
    if source_message_id is not None:
        metadata["source_message_id"] = source_message_id
    return metadata


def _string_trace_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _repo_name_from_ref(repo_ref: str) -> str:
    stripped = repo_ref.strip().rstrip("/")
    if not stripped:
        return "repo"
    if stripped.startswith("http://") or stripped.startswith("https://"):
        parts = [part for part in stripped.split("/") if part]
        if len(parts) >= 2:
            return "/".join(parts[-2:])
    path = Path(stripped)
    if path.name:
        return path.name
    parts = [part for part in stripped.split("/") if part]
    return parts[-1] if parts else stripped


def _message_for_run_exists(messages: list[ThreadMessage], run_id: str) -> bool:
    return any(message.source_run_id == run_id for message in messages)


def _evidence_refs_from_run(run: RunSummary) -> list[str]:
    refs = [f"run:{run.job_id}"]
    refs.extend(f"summary:{name}" for name in sorted(run.partial_summaries))
    if run.trace_url is not None:
        refs.append(f"trace:{run.trace_url}")
    return refs


def _summary_memory_from_messages(messages: list[ThreadMessage]) -> str | None:
    if not messages:
        return None
    lines = [
        f"{message.role}: {_single_line_excerpt(message.content, max_chars=180)}"
        for message in messages[-6:]
    ]
    return _truncate_text("\n".join(lines), max_chars=1200)


def _bounded_memory_packet(
    *,
    thread: ConversationThread,
    messages: list[ThreadMessage],
    max_messages: int,
    max_chars: int,
) -> str:
    recent_messages = messages[-max_messages:]
    lines = [
        "Wayfinder repo conversation memory:",
        f"Repo: {thread.repo_name} ({thread.repo_url})",
        "Memory source: bounded thread summary plus recent messages.",
        "Policy: memory can summarize prior discussion; new code facts must still be "
        "grounded in repo/AST/test evidence and labeled when unverified.",
    ]
    if recent_messages:
        lines.extend(["", f"Last {len(recent_messages)} messages:"])
        message_excerpt_chars = 220 if max_chars >= 1200 else 80
        for message in recent_messages:
            evidence = (
                f" [evidence: {', '.join(message.evidence_refs[:3])}]"
                if message.evidence_refs
                else ""
            )
            lines.append(
                f"- {message.role}: "
                f"{_single_line_excerpt(message.content, max_chars=message_excerpt_chars)}"
                f"{evidence}"
            )
    if thread.summary_memory:
        lines.extend(["", "Rolling summary:", _truncate_text(thread.summary_memory, max_chars=900)])
    return _truncate_text("\n".join(lines), max_chars=max_chars)


def _single_line_excerpt(text: str, *, max_chars: int) -> str:
    return _truncate_text(" ".join(text.split()), max_chars=max_chars)


def _truncate_text(text: str, *, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3]}..."


def _json_string_list(payload: str) -> list[str]:
    parsed = json.loads(payload)
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def _json_trace_metadata(payload: str) -> dict[str, str | int | float | bool | None]:
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        return {}
    metadata: dict[str, str | int | float | bool | None] = {}
    for key, value in parsed.items():
        if isinstance(key, str) and _is_json_scalar(value):
            metadata[key] = cast(str | int | float | bool | None, value)
    return metadata
