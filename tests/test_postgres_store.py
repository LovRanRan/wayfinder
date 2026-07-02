"""Tests for the PostgreSQL run store.

The SQL-translation tests run everywhere. The end-to-end store tests hit a real
database and are skipped unless ``WAYFINDER_RUN_POSTGRES_INTEGRATION=1`` and
``WAYFINDER_TEST_DATABASE_URL`` are set, mirroring the Project 5 MCP integration
gate. Each run creates its tables in the target database (idempotent DDL) and
uses unique workspace/thread ids so repeated runs do not collide.
"""

import os

import pytest

from wayfinder.api.postgres_store import translate_sql
from wayfinder.api.schemas import ExplainRequest

POSTGRES_INTEGRATION_ENABLED = os.getenv("WAYFINDER_RUN_POSTGRES_INTEGRATION") == "1"
TEST_DATABASE_URL = os.getenv("WAYFINDER_TEST_DATABASE_URL", "")


def test_translate_placeholders_and_upsert() -> None:
    translated = translate_sql(
        "INSERT OR REPLACE INTO runs (job_id, user_id, run_json) VALUES (?, ?, ?)"
    )
    assert "%s" in translated
    assert "?" not in translated
    assert (
        "ON CONFLICT (job_id) DO UPDATE SET user_id=EXCLUDED.user_id, run_json=EXCLUDED.run_json"
        in translated
    )


def test_translate_single_column_upsert_uses_do_nothing() -> None:
    translated = translate_sql("INSERT OR REPLACE INTO t (only_col) VALUES (?)")
    assert "ON CONFLICT (only_col) DO NOTHING" in translated


def test_translate_leaves_plain_select_untouched_except_placeholders() -> None:
    translated = translate_sql("SELECT * FROM runs WHERE user_id = ? LIMIT ?")
    assert translated == "SELECT * FROM runs WHERE user_id = %s LIMIT %s"


@pytest.mark.integration
@pytest.mark.skipif(
    not (POSTGRES_INTEGRATION_ENABLED and TEST_DATABASE_URL),
    reason="requires WAYFINDER_RUN_POSTGRES_INTEGRATION=1 and WAYFINDER_TEST_DATABASE_URL",
)
def test_postgres_store_round_trips_user_run_and_thread() -> None:
    from uuid import uuid4

    from wayfinder.api.postgres_store import PostgresRunStore

    store = PostgresRunStore(TEST_DATABASE_URL)
    assert store.ping() is True

    workspace = f"pg-{uuid4().hex[:12]}"
    user = store.create_user(workspace_id=workspace, password="hunter2xx", display_name="PG")

    with pytest.raises(ValueError, match="workspace already exists"):
        store.create_user(workspace_id=workspace, password="another11", display_name="Dup")

    authed = store.authenticate_user(workspace_id=workspace, password="hunter2xx")
    assert authed is not None and authed.user_id == user.user_id

    run = store.create(
        user=user,
        request=ExplainRequest(repo_url=".", query="map arch"),
        graph_input={"query": "map arch"},
    )
    running = store.mark_running(run.job_id, current_node="architect")
    assert running.status == "running"
    recent = store.list_recent(user_id=user.user_id, limit=5)
    assert any(item.job_id == run.job_id for item in recent)

    thread = store.create_thread(user=user, repo_url=".", title="onboarding")
    store.append_thread_message(
        user_id=user.user_id, thread_id=thread.thread_id, role="user", content="hi"
    )
    messages = store.messages_for_thread(user_id=user.user_id, thread_id=thread.thread_id)
    assert len(messages) == 1
    context = store.set_active_context(user_id=user.user_id, thread=thread)
    assert context.default_thread_id == thread.thread_id
