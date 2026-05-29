from wayfinder.graph import build_graph


def test_graph_scaffold_compiles_and_returns_contract_fields() -> None:
    graph = build_graph()

    result = graph.invoke(
        {"repo_url": "https://github.com/langchain-ai/langchain", "query": "Explain architecture"}
    )

    assert result["intent"] == "mixed"
    assert result["verified_claims"] == []
    assert result["unverified_claims"] == []
    assert result["contradicted_claims"] == []
    assert result["final_output"] is not None
