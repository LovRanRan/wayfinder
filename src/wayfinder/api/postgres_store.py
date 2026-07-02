"""PostgreSQL-backed run store for horizontally scaled deployments.

SQLite is file-local, so multiple API replicas cannot share run/thread state.
This backend points every replica at one Postgres database instead. It reuses
the exact method bodies of :class:`SQLiteRunStore` — the only differences between
the two engines here are the parameter placeholder style and the upsert syntax,
both of which are handled by a thin connection adapter (:class:`_PgConnection`)
that translates each statement on the way through. Keeping one set of SQL avoids
the two dialects drifting apart.

``psycopg`` is an optional dependency; importing this module without it succeeds,
but constructing :class:`PostgresRunStore` raises a clear error.
"""

from __future__ import annotations

import re
import sqlite3
from threading import RLock
from typing import TYPE_CHECKING, Any, Literal

from wayfinder.api.run_store import SCHEMA_DDL, SQLiteRunStore

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence


_OR_REPLACE = re.compile(
    r"INSERT\s+OR\s+REPLACE\s+INTO\s+(\w+)\s*\(([^)]*)\)\s*VALUES\s*\(([^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)


def translate_sql(sql: str) -> str:
    """Rewrite SQLite SQL into the Postgres dialect.

    Two transforms: SQLite's ``INSERT OR REPLACE`` becomes an
    ``ON CONFLICT (pk) DO UPDATE`` upsert (every such statement in the store
    conflicts on its first/primary-key column), then ``?`` placeholders become
    ``%s``. Applied in that order so the placeholders inside a rewritten upsert
    are converted too.
    """

    def _rewrite_upsert(match: re.Match[str]) -> str:
        table = match.group(1)
        columns = [column.strip() for column in match.group(2).split(",") if column.strip()]
        values = match.group(3).strip()
        conflict_column = columns[0]
        update_columns = [column for column in columns[1:]]
        assignments = ", ".join(f"{column}=EXCLUDED.{column}" for column in update_columns)
        insert = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({values})"
        if not assignments:
            return f"{insert} ON CONFLICT ({conflict_column}) DO NOTHING"
        return f"{insert} ON CONFLICT ({conflict_column}) DO UPDATE SET {assignments}"

    return _OR_REPLACE.sub(_rewrite_upsert, sql).replace("?", "%s")


class _PgConnection:
    """Adapter presenting a psycopg connection with the sqlite3 surface used here.

    The store calls ``connection.execute(sql, params)`` and uses
    ``with connection:`` as a transaction. This adapter translates the SQL,
    executes it on a cursor, and maps a Postgres unique-violation to
    :class:`sqlite3.IntegrityError` so the store's existing ``except`` clause
    (written for SQLite) works unchanged.
    """

    def __init__(self, dsn: str) -> None:
        import psycopg
        from psycopg.rows import dict_row

        self._psycopg = psycopg
        self._conn = psycopg.connect(dsn, autocommit=False, row_factory=dict_row)

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        cursor = self._conn.cursor()
        try:
            cursor.execute(translate_sql(sql), params if params is not None else None)
        except self._psycopg.errors.UniqueViolation as exc:
            raise sqlite3.IntegrityError(str(exc)) from exc
        return cursor

    def executescript(self, script: str) -> None:
        for statement in _split_statements(script):
            self._conn.execute(statement)

    def ping(self) -> None:
        self._conn.execute("SELECT 1")

    def __enter__(self) -> _PgConnection:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Literal[False]:
        # Mirror sqlite3's ``with connection:`` semantics: commit/rollback the
        # transaction but keep the connection open. (psycopg3's own connection
        # context manager would close the connection here instead.)
        if exc_type is not None:
            self._conn.rollback()
        else:
            self._conn.commit()
        return False

    def close(self) -> None:
        self._conn.close()


def _split_statements(script: str) -> list[str]:
    return [statement.strip() for statement in script.split(";") if statement.strip()]


class PostgresRunStore(SQLiteRunStore):
    """Run store backed by PostgreSQL via ``psycopg``.

    Deliberately does not call ``SQLiteRunStore.__init__`` (which opens a SQLite
    file); it wires a Postgres-backed connection adapter into the same
    ``self._connection`` / ``self._lock`` contract the inherited methods use.
    """

    def __init__(self, dsn: str) -> None:
        try:
            self._connection: Any = _PgConnection(dsn)
        except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError(
                "PostgresRunStore requires the 'psycopg' package. Install the "
                "'postgres' extra: uv sync --extra postgres."
            ) from exc
        self._lock = RLock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(SCHEMA_DDL)

    def ping(self) -> bool:
        with self._lock, self._connection:
            self._connection.ping()
        return True
