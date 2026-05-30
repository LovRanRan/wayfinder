import importlib
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from wayfinder.graph import build_graph


@contextmanager
def _sqlite_checkpointer(db_path: Path) -> Iterator[BaseCheckpointSaver[Any]]:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    sqlite_module = importlib.import_module("langgraph.checkpoint.sqlite")
    sqlite_saver_factory = cast(
        Callable[[sqlite3.Connection], BaseCheckpointSaver[Any]],
        vars(sqlite_module)["SqliteSaver"],
    )

    try:
        yield sqlite_saver_factory(conn)
    finally:
        conn.close()


def test_supervisor_graph_routes_architecture_query_to_placeholder_output() -> None:
    graph = build_graph()

    result = graph.invoke(
        {"repo_url": "https://github.com/langchain-ai/langchain", "query": "Explain architecture"}
    )

    assert "intent" in result
    assert "route_decision" in result
    assert "partial_summaries" in result
    assert "final_output" in result

    assert result["intent"] == "architectural"
    assert result["route_decision"]["next_agent"] == "architect_mapper"
    assert result["partial_summaries"]["architect_mapper"].startswith(
        "Placeholder architecture summary"
    )
    assert result["final_output"] == (
        "Placeholder final output for https://github.com/langchain-ai/langchain: "
        "Explain architecture"
    )


def test_graph_checkpoint_isolates_state_by_thread_id() -> None:
    checkpointer = InMemorySaver()
    graph = build_graph(checkpointer=checkpointer)

    thread_a: RunnableConfig = {"configurable": {"thread_id": "thread-a"}}
    thread_b: RunnableConfig = {"configurable": {"thread_id": "thread-b"}}

    result_a = graph.invoke(
        {"repo_url": "repo-a", "query": "Explain architecture"},
        config=thread_a,
    )
    result_b = graph.invoke(
        {"repo_url": "repo-b", "query": "Debug failing tests"},
        config=thread_b,
    )

    assert "intent" in result_a
    assert "intent" in result_b
    assert result_a["intent"] == "architectural"
    assert result_b["intent"] == "debug"

    snapshot_a = graph.get_state(thread_a)
    snapshot_b = graph.get_state(thread_b)

    assert snapshot_a.values["repo_url"] == "repo-a"
    assert snapshot_b.values["repo_url"] == "repo-b"


def test_mixed_or_missing_query() -> None:
    checkpointer = InMemorySaver()
    graph = build_graph(checkpointer=checkpointer)

    thread_a: RunnableConfig = {"configurable": {"thread_id": "thread-a"}}
    thread_b: RunnableConfig = {"configurable": {"thread_id": "thread-b"}}

    result_a = graph.invoke(
        {"repo_url": "repo-x", "query": "Help me understand this repo"},
        config=thread_a,
    )
    result_b = graph.invoke(
        {},
        config=thread_b,
    )

    assert "intent" in result_a
    assert "intent" in result_b
    assert "route_decision" in result_a
    assert "partial_summaries" in result_a
    assert "final_output" in result_a
    assert "route_decision" in result_b
    assert "partial_summaries" in result_b
    assert "final_output" in result_b
    assert result_a["intent"] == "mixed"
    assert result_b["intent"] == "mixed"

    assert result_a["route_decision"]["needs_human_review"] is True
    assert result_a["route_decision"]["next_agent"] == "architect_mapper"

    assert result_b["route_decision"]["needs_human_review"] is True
    assert result_b["route_decision"]["next_agent"] == "architect_mapper"
    assert result_b["final_output"] == "Placeholder final output for unknown repo: "

    assert result_a["partial_summaries"]["architect_mapper"].startswith(
        "Placeholder architecture summary"
    )
    assert result_b["partial_summaries"]["architect_mapper"].startswith(
        "Placeholder architecture summary"
    )


def test_sqlite_checkpoint_persists_state_across_graph_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "checkpoints.sqlite"
    thread_config: RunnableConfig = {"configurable": {"thread_id": "sqlite-thread"}}

    with _sqlite_checkpointer(db_path) as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        result = graph.invoke(
            {"repo_url": "repo-sqlite", "query": "Explain architecture"},
            config=thread_config,
        )

    assert "intent" in result
    assert result["intent"] == "architectural"

    with _sqlite_checkpointer(db_path) as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        snapshot = graph.get_state(thread_config)

    assert snapshot.values["repo_url"] == "repo-sqlite"
    assert snapshot.values["intent"] == "architectural"
