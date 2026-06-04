from wayfinder.graph.community_context import community_context_summary
from wayfinder.graph.llm import LLMCallError, extract_response_text
from wayfinder.graph.nodes import build_final_writer_node
from wayfinder.graph.state import CommunityContextItem, WayfinderState


class FakeSynthesizer:
    def __init__(self, output: str = "LLM grounded answer") -> None:
        self.output = output
        self.calls: list[tuple[WayfinderState, str]] = []

    def synthesize(
        self,
        *,
        state: WayfinderState,
        deterministic_output: str,
    ) -> str:
        self.calls.append((state, deterministic_output))
        return self.output


class FailingSynthesizer:
    def synthesize(
        self,
        *,
        state: WayfinderState,
        deterministic_output: str,
    ) -> str:
        del state, deterministic_output
        raise LLMCallError("model timed out")


class FakeCommunityProvider:
    def __init__(self, items: list[CommunityContextItem]) -> None:
        self.items = items
        self.calls: list[WayfinderState] = []

    def collect(self, state: WayfinderState) -> list[CommunityContextItem]:
        self.calls.append(state)
        return self.items


def test_final_writer_uses_injected_llm_synthesizer() -> None:
    synthesizer = FakeSynthesizer()
    node = build_final_writer_node(synthesizer=synthesizer)

    result = node(
        {
            "repo_url": "repo",
            "query": "Explain architecture",
            "partial_summaries": {"architect_mapper": "Repository facts"},
        }
    )

    assert result["final_output"] == "LLM grounded answer"
    assert synthesizer.calls
    _, deterministic_output = synthesizer.calls[0]
    assert deterministic_output == (
        "Architecture overview for repo: Explain architecture\n\nRepository facts"
    )


def test_final_writer_falls_back_when_llm_synthesis_fails() -> None:
    node = build_final_writer_node(synthesizer=FailingSynthesizer())

    result = node(
        {
            "repo_url": "repo",
            "query": "Explain architecture",
            "partial_summaries": {"architect_mapper": "Repository facts"},
        }
    )

    assert result["final_output"] == (
        "Architecture overview for repo: Explain architecture\n\nRepository facts"
    )
    assert result["errors"][0]["error_type"] == "llm_synthesis_unavailable"


def test_final_writer_collects_community_context_as_supporting_context_only() -> None:
    context_items: list[CommunityContextItem] = [
        {
            "source": "tavily_search",
            "title": "External docs",
            "snippet": "Community explanation",
            "url": "https://example.com",
        }
    ]
    provider = FakeCommunityProvider(context_items)
    synthesizer = FakeSynthesizer()
    node = build_final_writer_node(
        synthesizer=synthesizer,
        community_context_provider=provider,
    )

    result = node(
        {
            "repo_url": "https://github.com/LovRanRan/wayfinder",
            "query": "Explain architecture",
            "partial_summaries": {"architect_mapper": "Repository facts"},
            "verified_claims": [],
        }
    )

    captured_state, _ = synthesizer.calls[0]
    assert captured_state["community_context"] == context_items
    assert "supporting only" in captured_state["partial_summaries"]["community_context"]
    assert result["final_output"] == "LLM grounded answer"
    assert result.get("verified_claims") is None


def test_community_context_summary_labels_supporting_context() -> None:
    summary = community_context_summary(
        [
            {
                "source": "search_code",
                "title": "issue",
                "snippet": "external snippet",
                "url": None,
            }
        ]
    )

    assert summary.startswith("Community context (supporting only")


def test_extract_response_text_supports_output_text_and_content_items() -> None:
    assert extract_response_text({"output_text": "direct text"}) == "direct text"
    assert (
        extract_response_text(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "nested text"},
                        ],
                    }
                ]
            }
        )
        == "nested text"
    )
