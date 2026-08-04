from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from app.contracts import (
    ExternalEvidenceItem,
    ExternalRetrievalResult,
    ExternalSourceScope,
    ExternalSourceType,
)
from app.providers.retrieval.web import JsonWebSearchProvider
from app.services.external_research_answer import (
    external_search_view,
    is_academic_search_request,
    is_academic_writing_source_follow_up,
    normalize_academic_search_query,
    render_external_search_answer,
)
from app.services.external_retrieval import (
    ExternalCitationValidator,
    ExternalContentFetcher,
    ExternalFetchError,
)


def test_academic_writing_follow_up_reuses_a_prior_paper() -> None:
    query = (
        "\u8bf7\u5c06\u4e0a\u9762\u7b2c1\u7bc7\u8bba\u6587\u6539\u5199\u6210\u4e2d\u6587\u6458\u8981"
    )

    assert is_academic_writing_source_follow_up(
        query,
        previous_agent="RESEARCH_01_ACADEMIC_SEARCH_V1",
    )
    assert not is_academic_writing_source_follow_up(
        query,
        previous_agent="RESEARCH_02_ACADEMIC_WRITING_V1",
    )


def _item(url: str = "https://example.org/paper") -> ExternalEvidenceItem:
    return ExternalEvidenceItem(
        evidence_id="web-example",
        source_type=ExternalSourceType.WEB_PAGE,
        provider="web_json",
        source_ref="external://web/web-example",
        title="Example",
        canonical_url=url,
        retrieved_at=datetime.now(UTC),
    )


async def test_web_json_provider_normalizes_gateway_result() -> None:
    payload = {
        "results": [
            {
                "title": "New knowledge",
                "url": "https://example.org/new",
                "content": "A short result.",
                "score": 0.8,
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query"] == "new knowledge"
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        provider = JsonWebSearchProvider(
            base_url="https://search.example.org/api",
            client=client,
        )
        result = await provider.search("new knowledge", limit=3)
    finally:
        await client.aclose()

    assert result[0].source_type == ExternalSourceType.WEB_PAGE
    assert result[0].content_excerpt == "A short result."
    assert result[0].relevance_score == 0.8


async def test_fetcher_strips_markup_and_marks_untrusted_content() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"<p>Useful text</p><script>ignore()</script>",
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = ExternalContentFetcher(
        client=client,
        resolver=lambda _host, _port: ["93.184.216.34"],
    )
    try:
        result = await fetcher.fetch(_item())
    finally:
        await client.aclose()

    assert result.content_excerpt == "Useful text"
    assert result.metadata["content_trust"] == "untrusted_external"
    assert len(result.content_hash) == 64


async def test_fetcher_rejects_private_redirect() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/internal"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = ExternalContentFetcher(
        client=client,
        resolver=lambda _host, _port: ["93.184.216.34"],
    )
    try:
        with pytest.raises(ExternalFetchError, match="private_address_rejected"):
            await fetcher.fetch(_item())
    finally:
        await client.aclose()


def test_external_citation_validator_requires_available_evidence() -> None:
    validator = ExternalCitationValidator()
    item = _item()
    valid = validator.validate("Conclusion [web-example]", [item])
    missing = validator.validate("Conclusion without a marker", [item])
    invalid = validator.validate("Conclusion [unknown-source]", [item])

    assert valid.valid is True
    assert missing.missing is True
    assert missing.valid is False
    assert invalid.invalid_ids == ("unknown-source",)


def test_academic_search_answer_exposes_link_and_abstract_view() -> None:
    item = _item("https://example.org/electronics-paper")
    item = item.model_copy(
        update={
            "evidence_id": "paper-example",
            "source_type": ExternalSourceType.ACADEMIC_PAPER,
            "title": "Electronics paper",
            "content_excerpt": "This paper studies a useful signal-processing method.",
            "published_at": datetime(2025, 1, 2, tzinfo=UTC),
        }
    )
    result = ExternalRetrievalResult(
        query="latest electronics papers",
        normalized_query="latest electronics papers",
        source_scopes=[ExternalSourceScope.ACADEMIC],
        items=[item],
    )

    view = external_search_view(result)
    answer = render_external_search_answer(result)

    assert view[0]["url"] == "https://example.org/electronics-paper"
    assert view[0]["abstract"].startswith("This paper")
    assert "[paper-example]" in answer
    assert "[直达链接]" in answer
    assert "https://example.org/electronics-paper" in answer
    assert "修改说明" not in answer
    assert "引用检查" not in answer
    assert is_academic_search_request("查找最新的电子信息论文") is True
    assert is_academic_search_request("把这段内容改写成论文摘要") is False
    assert normalize_academic_search_query(
        "帮我查找最新的电子信息领域相关论文，并提供链接和摘要"
    ) == "electronics engineering information technology"


def test_enabled_external_retrieval_preserves_async_sse_order(api, client, app) -> None:
    class FakeSearch:
        async def search(self, query: str, **_: object) -> ExternalRetrievalResult:
            item = _item()
            return ExternalRetrievalResult(
                query=query,
                normalized_query=query,
                source_scopes=[ExternalSourceScope.WEB],
                items=[item],
                provider_status={"fake": "completed"},
            )

    app.state.settings.external_retrieval_enabled = True
    app.state.knowledge_base.settings.external_retrieval_enabled = True
    app.state.task_runner.external_search = FakeSearch()
    app.state.task_runner.external_paper_reviewer = None
    session = api.create_session()
    payload = api.task_payload(session["id"], intent="unknown")
    payload["canonical_input"]["text"] = "帮我查找最新的电子信息相关论文并提供链接"
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    task = response.json()
    completed = api.wait_for_task(task["id"])
    assert completed["status"] == "completed"
    structured = completed["result_content"]["structured_result"]
    assert completed["agent_id"] == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    assert structured["external_search_view"][0]["url"] == "https://example.org/paper"
    assert structured["external_citation_validation"]["status"] == "passed"

    events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
    names = [event["event_type"] for event in events]
    assert "external_retrieval.started" in names, "|".join(names)
    started = names.index("external_retrieval.started")
    finished = names.index("external_retrieval.completed")
    assert names.index("agent.started") < started < finished
    assert finished < names.index("task.completed")
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))

    response = client.get(
        f"/api/v1/tasks/{task['id']}/stream",
        headers={"Last-Event-ID": str(events[started]["sequence"])},
    )
    assert "event: external_retrieval.completed" in response.text
    assert "event: external_retrieval.started" not in response.text
