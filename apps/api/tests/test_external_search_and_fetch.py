from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import sleep
from types import SimpleNamespace

import httpx
import pytest
from app.contracts import (
    AgentRequest,
    ExternalEvidenceItem,
    ExternalRetrievalPolicy,
    ExternalRetrievalResult,
    ExternalSourceScope,
    ExternalSourceType,
)
from app.core.config import Settings
from app.providers.retrieval.web import (
    AliyunIqsSearchProvider,
    BochaSearchProvider,
    BraveSearchProvider,
    JsonWebSearchProvider,
    SearxngSearchProvider,
    SerpApiSearchProvider,
    TavilySearchProvider,
)
from app.services.external_research_answer import (
    external_search_view,
    filter_research_evidence,
    is_academic_search_follow_up,
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
from app.services.task_runner import TaskRunner
from pydantic import AnyHttpUrl


@pytest.mark.asyncio
async def test_external_retrieval_hard_deadline_does_not_wait_for_late_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = object.__new__(TaskRunner)
    object.__setattr__(
        runner,
        "knowledge_base",
        SimpleNamespace(
            settings=Settings(
                app_env="test",
                external_retrieval_timeout_seconds=0.02,
                _env_file=None,  # type: ignore[call-arg]
            )
        ),
    )
    object.__setattr__(runner, "_external_tasks", set())
    request = AgentRequest(
        task_id="task-hard-deadline",
        session_id="session-test",
        user_id="user-test",
        canonical_input={"text": "slow external query"},
        options={"external_retrieval_trace_id": "runtime:deadline:fetch"},
    )
    policy = ExternalRetrievalPolicy(
        enabled=True,
        source_scopes=[ExternalSourceScope.ACADEMIC],
        providers=["fixture"],
        timeout_seconds=1,
    )

    async def non_cooperative_retrieval(
        _request: AgentRequest,
        _policy: ExternalRetrievalPolicy,
        *,
        allow_degraded_review: bool = False,
    ) -> ExternalRetrievalResult:
        del allow_degraded_review
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            # Model/network clients occasionally acknowledge cancellation late.
            await asyncio.sleep(0.5)
        return ExternalRetrievalResult(
            query="slow external query",
            normalized_query="slow external query",
            status="failed",
        )

    monkeypatch.setattr(runner, "_retrieve_external", non_cooperative_retrieval)
    result = await asyncio.wait_for(
        runner._retrieve_external_with_deadline(request, policy),
        timeout=0.1,
    )

    assert result.status == "failed"
    assert result.warnings == ["external retrieval timed out"]
    assert result.retrieval_trace_id == "runtime:deadline:fetch"
    await asyncio.sleep(0.55)
    assert not runner._external_tasks  # type: ignore[attr-defined]


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


def test_academic_search_follow_up_understands_short_continuation() -> None:
    assert is_academic_search_follow_up(
        "接着提供一些额外的论文信息",
        previous_agent="RESEARCH_01_ACADEMIC_SEARCH_V1",
        previous_answer_summary="上一轮已经完成科研前沿检索并返回论文证据。",
    )


def _item(url: str = "https://example.org/paper") -> ExternalEvidenceItem:
    return ExternalEvidenceItem(
        evidence_id="web-example",
        source_type=ExternalSourceType.WEB_PAGE,
        provider="web_json",
        source_ref="external://web/web-example",
        title="Example",
        canonical_url=AnyHttpUrl(url),
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


async def test_searxng_provider_maps_q_and_parses_json_results() -> None:
    payload = {
        "results": [
            {
                "title": "Flexible electronics result",
                "url": "https://example.org/flexible",
                "content": "A SearXNG result.",
                "score": 0.7,
                "engine": "wikipedia",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "flexible electronics"
        assert request.url.params["format"] == "json"
        assert request.url.params["categories"] == "general"
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        provider = SearxngSearchProvider(
            base_url="http://127.0.0.1:8080/search",
            client=client,
            min_delay_seconds=0,
        )
        result = await provider.search("flexible electronics", limit=3)
    finally:
        await client.aclose()

    assert result[0].provider == "searxng"
    assert result[0].content_excerpt == "A SearXNG result."
    assert result[0].metadata["engine"] == "wikipedia"


@pytest.mark.parametrize(
    ("provider_factory", "expected_path"),
    [
        (
            lambda client: TavilySearchProvider(
                base_url="https://api.tavily.com/search",
                api_key="tvly-test",
                client=client,
                min_delay_seconds=0,
            ),
            "/search",
        ),
        (
            lambda client: BraveSearchProvider(
                base_url="https://api.search.brave.com/res/v1/web/search",
                api_key="brave-test",
                client=client,
                min_delay_seconds=0,
            ),
            "/res/v1/web/search",
        ),
        (
            lambda client: SerpApiSearchProvider(
                base_url="https://serpapi.com/search.json",
                api_key="serp-test",
                client=client,
                min_delay_seconds=0,
            ),
            "/search.json",
        ),
    ],
)
async def test_configured_web_provider_adapters_normalize_results(
    provider_factory, expected_path
) -> None:
    payloads = {
        "/search": {
            "results": [
                {
                    "title": "Tavily result",
                    "url": "https://example.org/tavily",
                    "content": "Tavily excerpt",
                    "score": 0.9,
                }
            ]
        },
        "/res/v1/web/search": {
            "web": {
                "results": [
                    {
                        "title": "Brave result",
                        "url": "https://example.org/brave",
                        "description": "Brave excerpt",
                    }
                ]
            }
        },
        "/search.json": {
            "organic_results": [
                {
                    "title": "SerpApi result",
                    "link": "https://example.org/serpapi",
                    "snippet": "SerpApi excerpt",
                }
            ]
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == expected_path
        if expected_path == "/search":
            assert request.method == "POST"
            assert request.headers["authorization"] == "Bearer tvly-test"
            assert request.content
        elif expected_path == "/res/v1/web/search":
            assert request.method == "GET"
            assert request.headers["x-subscription-token"] == "brave-test"
            assert request.url.params["count"] == "5"
        else:
            assert request.url.params["api_key"] == "serp-test"
            assert request.url.params["engine"] == "google"
        return httpx.Response(200, json=payloads[expected_path])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        provider = provider_factory(client)
        result = await provider.search("flexible electronics", limit=5)
    finally:
        await client.aclose()

    assert len(result) == 1
    assert result[0].source_type == ExternalSourceType.WEB_PAGE
    assert result[0].canonical_url.host == "example.org"


async def test_domestic_web_provider_adapters_map_official_response_shapes() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host or "")
        if request.url.host == "cloud-iqs.aliyuncs.com":
            return httpx.Response(
                200,
                json={
                    "requestId": "request-1",
                    "pageItems": [
                        {
                            "title": "Alibaba result",
                            "link": "https://example.org/aliyun",
                            "snippet": "Alibaba excerpt",
                            "publishedTime": "2025-01-02T00:00:00+08:00",
                            "rerankScore": 0.88,
                        }
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "webPages": {
                        "value": [
                            {
                                "name": "Bocha result",
                                "url": "https://example.org/bocha",
                                "snippet": "Bocha excerpt",
                            }
                        ]
                    }
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        aliyun = AliyunIqsSearchProvider(
            base_url="https://cloud-iqs.aliyuncs.com/search/unified",
            api_key="aliyun-test",
            client=client,
            min_delay_seconds=0,
        )
        bocha = BochaSearchProvider(
            base_url="https://api.bochaai.com/v1/web-search",
            api_key="bocha-test",
            client=client,
            min_delay_seconds=0,
        )
        aliyun_items = await aliyun.search("柔性电子器件", limit=5)
        bocha_items = await bocha.search("柔性电子器件", limit=5)
    finally:
        await client.aclose()

    assert calls == ["cloud-iqs.aliyuncs.com", "api.bochaai.com"]
    assert aliyun_items[0].title == "Alibaba result"
    assert aliyun_items[0].relevance_score == 0.88
    assert bocha_items[0].title == "Bocha result"
    assert bocha_items[0].content_excerpt == "Bocha excerpt"


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
    assert is_academic_search_request("近三年柔性电子器件的关键进展是什么？") is True
    assert is_academic_search_request("把这段内容改写成论文摘要") is False
    assert normalize_academic_search_query(
        "帮我查找最新的电子信息领域相关论文，并提供链接和摘要"
    ) == "electronics engineering information technology"


def test_electronics_course_research_filters_cross_discipline_evidence() -> None:
    direct = _item("https://example.org/electronics-education-paper").model_copy(
        update={
            "evidence_id": "electronics-education",
            "title": "AI tutoring in electrical engineering education",
            "content_excerpt": (
                "This study evaluates an intelligent tutoring system in an "
                "electrical engineering course with circuit design exercises."
            ),
        }
    )
    unrelated = _item("https://example.org/nursing-education-paper").model_copy(
        update={
            "evidence_id": "nursing-education",
            "title": "ChatGPT in nursing education",
            "content_excerpt": (
                "This review studies large language models in nursing education "
                "and clinical training."
            ),
        }
    )

    filtered = filter_research_evidence(
        "请检索电子信息课程智能辅导效果的近期研究",
        [direct, unrelated],
    )

    assert [item.evidence_id for item in filtered] == ["electronics-education"]


def test_active_learning_engineering_education_filters_degraded_candidates() -> None:
    direct = _item("https://example.org/engineering-active-learning").model_copy(
        update={
            "evidence_id": "engineering-active-learning",
            "title": "Active learning in engineering education",
            "content_excerpt": (
                "This study evaluates problem-based learning activities in "
                "an engineering "
                "course and reports learning outcomes."
            ),
        }
    )
    unrelated = _item("https://example.org/nursing-active-learning").model_copy(
        update={
            "evidence_id": "nursing-active-learning",
            "title": "Active learning in nursing education",
            "content_excerpt": (
                "This study evaluates active learning in nursing education and "
                "clinical training."
            ),
        }
    )

    filtered = filter_research_evidence(
        "Find recent academic evidence on the effects of active learning in "
        "engineering education.",
        [direct, unrelated],
    )

    assert [item.evidence_id for item in filtered] == ["engineering-active-learning"]


def test_active_learning_drops_unsupported_topics() -> None:
    adjacent = _item("https://example.org/engineering-ai").model_copy(
        update={
            "evidence_id": "engineering-ai",
            "title": "Generative AI in engineering classrooms",
            "content_excerpt": (
                "This engineering education paper discusses generative AI but "
                "focuses on prompt design and does not evaluate a teaching "
                "intervention or student learning outcomes."
            ),
        }
    )

    filtered = filter_research_evidence(
        "Find recent academic evidence on the effects of active learning in "
        "engineering education.",
        [adjacent],
    )

    assert filtered == []


def test_compound_topic_requires_each_explicit_topic_term() -> None:
    item = _item("https://example.org/quantum-education").model_copy(
        update={
            "evidence_id": "quantum-education",
            "title": "Quantum computing education",
            "content_excerpt": (
                "This paper studies active learning in engineering education, "
                "but it focuses on quantum computing rather than the requested topic."
            ),
        }
    )

    filtered = filter_research_evidence(
        "Find evidence on active learning in quantum coral engineering education.",
        [item],
    )

    assert filtered == []


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
    assert structured["external_retrieval"]["items"][0]["canonical_url"] == (
        "https://example.org/paper"
    )
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


def test_research_knowledge_ingest_does_not_block_task_completion(
    api, client, app
) -> None:
    class FakeSearch:
        async def search(self, query: str, **_: object) -> ExternalRetrievalResult:
            return ExternalRetrievalResult(
                query=query,
                normalized_query=query,
                source_scopes=[ExternalSourceScope.WEB],
                items=[_item()],
                provider_status={"fake": "completed"},
            )

    class SlowResearchKnowledge:
        started = False
        finished = False

        async def ingest(self, result, *, query: str, task_id: str):
            del result, query, task_id
            self.started = True
            # Keep the background window longer than the local task's
            # provider/fallback path so this checks scheduling semantics,
            # not a race between two short sleeps.
            await asyncio.sleep(1.5)
            self.finished = True
            return {"stored": 1}

    slow = SlowResearchKnowledge()
    app.state.settings.external_retrieval_enabled = True
    app.state.knowledge_base.settings.external_retrieval_enabled = True
    app.state.task_runner.external_search = FakeSearch()
    app.state.task_runner.external_paper_reviewer = None
    app.state.task_runner.research_knowledge = slow

    session = api.create_session()
    payload = api.task_payload(session["id"], intent="unknown")
    payload["canonical_input"]["text"] = (
        "\u8fd1\u4e09\u5e74\u67d4\u6027\u7535\u5b50\u5668\u4ef6\u7684"
        "\u5173\u952e\u8fdb\u5c55\u662f\u4ec0\u4e48\uff1f"
    )
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    completed = api.wait_for_task(response.json()["id"])

    assert completed["status"] == "completed"
    assert slow.started is True
    assert slow.finished is False
    sleep(1.6)
    assert slow.finished is True
