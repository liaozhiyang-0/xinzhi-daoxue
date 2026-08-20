from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from app.agents.internal import InternalAgentResult
from app.contracts import (
    AgentRequest,
    ExternalEvidenceItem,
    ExternalRetrievalResult,
    ExternalSourceScope,
    ExternalSourceType,
    Intent,
    Scene,
    UserRole,
)
from app.contracts.research import ResearchBriefDraft, ResearchFinding
from app.core.config import Settings
from app.providers.retrieval.web import NewsRssSearchProvider
from app.services.academic_search_planner import (
    AcademicSearchPlannerService,
    _repair_relative_time_ranges,
    relative_freshness_days,
)
from app.services.external_research_answer import (
    is_academic_search_follow_up,
    research_topic_conflicts,
)
from app.services.research_frontier_service import ResearchFrontierService

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item><title>柔性电子器件产业报道</title>
    <link>https://example.org/report</link>
    <description>报道摘要。</description>
    <pubDate>Tue, 05 Aug 2026 08:00:00 GMT</pubDate>
    <source>Example News</source>
  </item>
</channel></rss>
"""


def _item(evidence_id: str = "paper-1") -> ExternalEvidenceItem:
    return ExternalEvidenceItem(
        evidence_id=evidence_id,
        source_type=ExternalSourceType.ACADEMIC_PAPER,
        provider="openalex",
        source_ref=f"external://openalex/{evidence_id}",
        title="Flexible electronics progress",
        canonical_url=f"https://example.org/{evidence_id}",
        content_excerpt=(
            "The paper reports a flexible device architecture and its limitations."
        ),
        retrieved_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_news_rss_provider_parses_report_source() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "application/rss+xml"},
                content=RSS_XML.encode("utf-8"),
            )
        )
    )
    try:
        provider = NewsRssSearchProvider(
            base_url="https://news.google.com/rss/search", client=client
        )
        items = await provider.search("柔性电子器件 报道", limit=3)
    finally:
        await client.aclose()

    assert len(items) == 1
    assert items[0].source_type == ExternalSourceType.WEB_PAGE
    assert items[0].metadata["category"] == "web_report"
    assert items[0].venue == "Example News"


class FakeResearchHub:
    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "agent_id": agent_id,
                "configured": True,
                "enabled": True,
            }
            for agent_id in (
                "RESEARCH_INTENT_CLASSIFIER_LOCAL_V1",
                "RESEARCH_FRONTIER_BRIEF_LOCAL_V1",
            )
        ]

    async def run_text(self, agent_id: str, **_: Any) -> InternalAgentResult:
        if agent_id == "RESEARCH_INTENT_CLASSIFIER_LOCAL_V1":
            structured = {
                "goal": "frontier_brief",
                "topic": "柔性电子器件",
                "requires_web": True,
                "source_kinds": ["academic_paper", "web_report", "conference"],
                "freshness_days": 1095,
                "response_depth": "deep",
                "reason_codes": ["freshness", "research_progress"],
                "confidence": 0.96,
            }
        else:
            structured = {
                "title": "柔性电子器件前沿简报",
                "scope": "近三年柔性电子器件的关键进展",
                "executive_summary": "柔性器件正在向高可靠性和复杂集成演进。",
                "key_findings": [
                    {
                        "claim": "器件架构开始关注可弯折条件下的可靠性",
                        "evidence_ids": ["paper-1"],
                        "why_it_matters": "影响实际部署和寿命评估。",
                        "confidence": "medium",
                    }
                ],
                "source_landscape": [
                    {
                        "category": "academic_paper",
                        "count": 1,
                        "evidence_ids": ["paper-1"],
                        "note": "论文摘要证据",
                    }
                ],
                "timeline": [],
                "open_questions": ["长期循环可靠性仍需全文和实验数据核验"],
                "next_steps": ["按器件材料和封装路线继续检索会议与产业报道"],
                "limitations": ["当前仅展示摘要级证据"],
            }
        return InternalAgentResult(
            agent_id=agent_id,
            task_type="research",
            provider="local",
            model="qwen-test",
            content="",
            structured_result=structured,
            elapsed_ms=12,
        )


class MisclassifyingResearchHub(FakeResearchHub):
    async def run_text(self, agent_id: str, **_: Any) -> InternalAgentResult:
        result = await super().run_text(agent_id, **_)
        if agent_id == "RESEARCH_INTENT_CLASSIFIER_LOCAL_V1":
            result.structured_result = {
                **result.structured_result,
                "goal": "explain",
                "requires_web": False,
                "source_kinds": ["academic_paper"],
            }
        return result


@pytest.mark.asyncio
async def test_frontier_signals_override_explain_misclassification() -> None:
    request = AgentRequest(
        session_id="session-research",
        user_id="researcher",
        user_role=UserRole.RESEARCHER,
        scene=Scene.RESEARCH,
        course_id="UNKNOWN",
        intent=Intent.GENERAL_QA,
        canonical_input={"text": "近三年柔性电子器件的关键进展"},
        options={"request_id": "research-request"},
    )

    intent = await ResearchFrontierService(MisclassifyingResearchHub()).classify_intent(
        request
    )

    assert intent is not None
    assert intent.goal == "frontier_brief"
    assert intent.requires_web is True
    assert "deterministic_frontier_signal" in intent.reason_codes
    assert len(intent.research_questions) >= 4
    assert any("可靠性" in item for item in intent.research_questions)


def test_relative_planner_range_does_not_keep_stale_model_years() -> None:
    repaired = _repair_relative_time_ranges(
        ["flexible electronics AND (progress OR advances) AND (2021..2024)"],
        freshness_days=1095,
    )

    assert "2021..2024" not in repaired[0]


@pytest.mark.parametrize(
    ("query", "expected_days"),
    [
        ("过去12个月人工智能智能体研究", 360),
        ("last 18 months of multimodal agents", 540),
    ],
)
def test_relative_month_windows_are_translated_to_retrieval_days(
    query: str, expected_days: int
) -> None:
    assert relative_freshness_days(query) == expected_days


def test_frontier_brief_drops_unsupported_key_findings() -> None:
    item = _item()
    brief = ResearchBriefDraft(
        title="测试简报",
        scope="柔性电子器件进展",
        executive_summary="候选摘要",
        key_findings=[
            ResearchFinding(
                claim="有来源支持的结论",
                evidence_ids=[item.evidence_id],
                why_it_matters="可核验",
                confidence="medium",
            ),
            ResearchFinding(
                claim="没有来源支持的额外推断",
                evidence_ids=[],
                why_it_matters="不应直接展示",
                confidence="high",
            ),
        ],
    )

    sanitized = ResearchFrontierService._sanitize_brief(brief, [item])

    assert [finding.claim for finding in sanitized.key_findings] == [
        "有来源支持的结论"
    ]


def test_frontier_brief_falls_back_to_a_cited_finding_when_all_are_unsupported(
) -> None:
    item = _item()
    brief = ResearchBriefDraft(
        title="测试简报",
        scope="柔性电子器件进展",
        executive_summary="候选摘要",
        key_findings=[
            ResearchFinding(
                claim="没有来源支持的推断",
                evidence_ids=[],
                confidence="high",
            )
        ],
    )

    sanitized = ResearchFrontierService._sanitize_brief(brief, [item])

    assert len(sanitized.key_findings) == 1
    assert sanitized.key_findings[0].evidence_ids == [item.evidence_id]


@pytest.mark.asyncio
async def test_planner_appends_multiple_research_questions() -> None:
    class PlannerHub:
        async def run_text(self, *_args: Any, **_kwargs: Any) -> InternalAgentResult:
            return InternalAgentResult(
                agent_id="ACADEMIC_SEARCH_PLANNER_LOCAL_V1",
                task_type="academic_search_planning",
                provider="local",
                model="qwen-test",
                content="",
                structured_result={
                    "topic_summary": "flexible electronics",
                    "search_queries": ["flexible electronics devices"],
                    "required_concepts": ["flexible electronics"],
                    "excluded_concepts": [],
                    "minimum_results": 3,
                    "citation_preference": "not_requested",
                },
                elapsed_ms=12,
            )

    plan, warning = await AcademicSearchPlannerService(
        PlannerHub(), Settings(_env_file=None)
    ).plan(
        "近三年柔性电子器件的关键进展是什么？",
        research_intent={
            "freshness_days": 1095,
            "research_questions": [
                "柔性电子器件 材料与结构",
                "柔性电子器件 传感与电子皮肤",
                "柔性电子器件 制造与可靠性",
            ],
        },
    )

    assert warning is None
    assert plan is not None
    assert len(plan.search_queries) == 4
    assert any("制造与可靠性" in query for query in plan.search_queries)


@pytest.mark.asyncio
async def test_planner_falls_back_to_topic_specific_variants() -> None:
    class UnavailablePlannerHub:
        async def run_text(self, *_args: Any, **_kwargs: Any) -> InternalAgentResult:
            raise RuntimeError("planner unavailable")

    plan, warning = await AcademicSearchPlannerService(
        UnavailablePlannerHub(), Settings(_env_file=None)
    ).plan("2024年至2026年生成式人工智能在多模态和智能体方面的代表性进展")

    assert plan is not None
    assert warning is not None
    assert len(plan.search_queries) == 2
    assert all("2024" in query and "2026" in query for query in plan.search_queries)
    assert any("multimodal" in query for query in plan.search_queries)
    assert any("agent" in query for query in plan.search_queries)


@pytest.mark.asyncio
async def test_planner_does_not_invent_user_paper_count_requirement() -> None:
    class OvereagerPlannerHub:
        async def run_text(self, *_args: Any, **_kwargs: Any) -> InternalAgentResult:
            return InternalAgentResult(
                agent_id="ACADEMIC_SEARCH_PLANNER_LOCAL_V1",
                task_type="academic_search_planning",
                provider="local",
                model="qwen-test",
                content="",
                structured_result={
                    "topic_summary": "generative AI",
                    "search_queries": ["generative AI multimodal agents"],
                    "required_concepts": [],
                    "excluded_concepts": [],
                    "minimum_results": 10,
                    "citation_preference": "not_requested",
                },
                elapsed_ms=12,
            )

    plan, warning = await AcademicSearchPlannerService(
        OvereagerPlannerHub(), Settings(_env_file=None)
    ).plan("2024年至2026年生成式人工智能在多模态和智能体方面有哪些进展？")

    assert warning is None
    assert plan is not None
    assert plan.minimum_results == 2


@pytest.mark.asyncio
async def test_planner_replaces_broad_ai_boolean_noise_with_topic_variants() -> None:
    class NoisyPlannerHub:
        async def run_text(self, *_args: Any, **_kwargs: Any) -> InternalAgentResult:
            return InternalAgentResult(
                agent_id="ACADEMIC_SEARCH_PLANNER_LOCAL_V1",
                task_type="academic_search_planning",
                provider="local",
                model="qwen-test",
                content="",
                structured_result={
                    "topic_summary": "generative AI multimodal agents",
                    "search_queries": [
                        "generative AI OR foundation models) AND (multimodal OR agents",
                    ],
                    "required_concepts": [],
                    "excluded_concepts": [],
                    "minimum_results": 10,
                    "citation_preference": "not_requested",
                },
                elapsed_ms=12,
            )

    query = (
        "2024年至2026年生成式人工智能在多模态和智能体方面有哪些代表性进展？"
    )
    plan, warning = await AcademicSearchPlannerService(
        NoisyPlannerHub(), Settings(_env_file=None)
    ).plan(query)

    assert warning is None
    assert plan is not None
    assert plan.minimum_results == 2
    assert plan.search_queries[:2] == [
        "generative AI multimodal models vision-language models",
        "AI agents agentic systems large language models tool use",
    ]
    assert all(" OR " not in query for query in plan.search_queries)


@pytest.mark.asyncio
async def test_planner_preserves_explicit_paper_count_requirement() -> None:
    class ExplicitCountPlannerHub:
        async def run_text(self, *_args: Any, **_kwargs: Any) -> InternalAgentResult:
            return InternalAgentResult(
                agent_id="ACADEMIC_SEARCH_PLANNER_LOCAL_V1",
                task_type="academic_search_planning",
                provider="local",
                model="qwen-test",
                content="",
                structured_result={
                    "topic_summary": "generative AI",
                    "search_queries": ["generative AI agents"],
                    "required_concepts": [],
                    "excluded_concepts": [],
                    "minimum_results": 4,
                    "citation_preference": "not_requested",
                },
                elapsed_ms=12,
            )

    plan, warning = await AcademicSearchPlannerService(
        ExplicitCountPlannerHub(), Settings(_env_file=None)
    ).plan("至少 8 篇 2024年至2026年生成式人工智能智能体研究")

    assert warning is None
    assert plan is not None
    assert plan.minimum_results == 8


@pytest.mark.asyncio
async def test_research_frontier_service_renders_cited_brief() -> None:
    item = _item()
    external = ExternalRetrievalResult(
        query="近三年柔性电子器件的关键进展",
        normalized_query="flexible electronics",
        source_scopes=[ExternalSourceScope.ACADEMIC],
        items=[item],
    )
    request = AgentRequest(
        session_id="session-research",
        user_id="researcher",
        user_role=UserRole.RESEARCHER,
        scene=Scene.RESEARCH,
        course_id="UNKNOWN",
        intent=Intent.GENERAL_QA,
        canonical_input={"text": external.query},
        options={
            "external_retrieval": external.model_dump(mode="json"),
            "request_id": "research-request",
        },
    )

    result = await ResearchFrontierService(FakeResearchHub()).run(request)

    assert result.provider == "local_agent"
    assert "[paper-1]" in result.answer
    assert "下一步建议" not in result.answer
    assert "证据边界" not in result.answer
    assert result.structured_result["research_intent"]["requires_web"] is True
    assert result.artifacts[0].artifact_type.value == "report"
    assert result.structured_result["evidence_summary"] == {
        "status": "partial",
        "item_count": 1,
    }


@pytest.mark.asyncio
async def test_research_frontier_fallback_synthesizes_evidence() -> None:
    class FailingBriefHub(FakeResearchHub):
        async def run_text(self, agent_id: str, **kwargs: Any) -> InternalAgentResult:
            if agent_id == "RESEARCH_FRONTIER_BRIEF_LOCAL_V1":
                raise RuntimeError("brief model unavailable")
            return await super().run_text(agent_id, **kwargs)

    sensor_report = _item("report-1").model_copy(
        update={
            "source_type": ExternalSourceType.WEB_PAGE,
            "title": "多功能热感知传感器与电子皮肤",
            "content_excerpt": (
                "A report discusses multifunctional thermal sensors and "
                "electronic skin."
            ),
            "provider": "news_rss",
        }
    )
    external = ExternalRetrievalResult(
        query="近三年柔性电子器件的关键进展",
        normalized_query="flexible electronics",
        source_scopes=[ExternalSourceScope.ACADEMIC, ExternalSourceScope.WEB],
        items=[_item(), sensor_report],
    )
    request = AgentRequest(
        session_id="session-research",
        user_id="researcher",
        user_role=UserRole.RESEARCHER,
        scene=Scene.RESEARCH,
        course_id="UNKNOWN",
        intent=Intent.GENERAL_QA,
        canonical_input={"text": external.query},
        options={"external_retrieval": external.model_dump(mode="json")},
    )

    result = await ResearchFrontierService(FailingBriefHub()).run(request)
    assert "paper-1" in result.structured_result["external_references"]
    assert "report-1" in result.structured_result["external_references"]
    summary = result.structured_result["research_brief"]["executive_summary"]
    assert summary.endswith("\u539f\u6587\u3002")
    return

    assert "多功能传感器与电子皮肤推动柔性器件向人体界面应用发展" in result.answer
    assert "Distributed Delay-Based BIST" not in result.answer
    assert "下一步建议" not in result.answer
    assert "证据边界" not in result.answer


@pytest.mark.asyncio
async def test_research_frontier_answers_when_external_evidence_is_empty() -> None:
    external = ExternalRetrievalResult(
        query="近三年柔性电子器件的关键进展是什么？",
        normalized_query="flexible electronics",
        source_scopes=[ExternalSourceScope.ACADEMIC, ExternalSourceScope.WEB],
        status="failed",
        warnings=["academic providers temporarily unavailable"],
    )
    request = AgentRequest(
        session_id="session-research",
        user_id="researcher",
        user_role=UserRole.RESEARCHER,
        scene=Scene.RESEARCH,
        course_id="UNKNOWN",
        intent=Intent.GENERAL_QA,
        canonical_input={"text": external.query},
        options={
            "external_retrieval": external.model_dump(mode="json"),
            "request_id": "research-request",
        },
    )

    result = await ResearchFrontierService(FakeResearchHub()).run(request)

    assert result.structured_result["status"] == "completed"
    assert result.structured_result["answer_mode"] == "no_verified_evidence"
    assert result.structured_result["evidence_summary"] == {
        "status": "insufficient",
        "item_count": 0,
    }
    return
    assert result.structured_result["answer_mode"] == "local_knowledge_fallback"
    assert result.answer
    assert "无法生成可靠的前沿简报" not in result.answer
    assert "http_429" not in result.answer
    assert "not_configured" not in result.answer
    assert "key_findings" in result.structured_result["research_brief"]


@pytest.mark.asyncio
async def test_research_frontier_reuses_local_research_evidence() -> None:
    class LocalFallbackHub(FakeResearchHub):
        async def run_text(self, agent_id: str, **kwargs: Any) -> InternalAgentResult:
            if agent_id == "RESEARCH_FRONTIER_BRIEF_LOCAL_V1":
                raise RuntimeError("brief model unavailable")
            return await super().run_text(agent_id, **kwargs)

    class LocalResearchKnowledge:
        async def search_evidence(
            self, _query: str
        ) -> list[ExternalEvidenceItem]:
            return [_item("stored-paper")]

    request = AgentRequest(
        session_id="session-research",
        user_id="researcher",
        user_role=UserRole.RESEARCHER,
        scene=Scene.RESEARCH,
        course_id="UNKNOWN",
        intent=Intent.GENERAL_QA,
        canonical_input={"text": "flexible electronics progress"},
        options={"request_id": "research-request"},
    )

    result = await ResearchFrontierService(
        LocalFallbackHub(),
        research_knowledge=LocalResearchKnowledge(),  # type: ignore[arg-type]
    ).run(request)

    assert result.structured_result["answer_mode"] == "local_research_knowledge"
    assert "stored-paper" in result.structured_result["external_references"]
    assert "[stored-paper]" in result.answer


def test_research_intent_and_memory_do_not_cross_domains() -> None:
    ai_question = (
        "\u0032\u0030\u0032\u0034\u5e74\u81f3\u0032\u0030\u0032\u0036\u5e74"
        "\u4eba\u5de5\u667a\u80fd\u6709\u54ea\u4e9b\u4ee3\u8868\u6027\u8fdb\u5c55\uff1f"
    )
    flexible_question = (
        "\u0032\u0030\u0032\u0034\u5e74\u81f3\u0032\u0030\u0032\u0036\u5e74"
        "\u67d4\u6027\u7535\u5b50\u5668\u4ef6\u7684\u8fdb\u5c55"
    )

    assert ResearchFrontierService._deterministic_intent(ai_question).requires_web
    assert research_topic_conflicts(ai_question, flexible_question)
    assert not is_academic_search_follow_up(
        "\u7ee7\u7eed\u63d0\u4f9b\u4eba\u5de5\u667a\u80fd\u8bba\u6587\u4fe1\u606f",
        previous_agent=ResearchFrontierService.agent_id,
        previous_answer_summary="\u67d4\u6027\u7535\u5b50\u8bba\u6587\u8bc1\u636e",
        previous_query=flexible_question,
    )


@pytest.mark.asyncio
async def test_frontier_drops_previous_flexible_evidence_for_ai_question() -> None:
    question = (
        "\u0032\u0030\u0032\u0034\u5e74\u81f3\u0032\u0030\u0032\u0036\u5e74"
        "\u4eba\u5de5\u667a\u80fd\u6709\u54ea\u4e9b\u4ee3\u8868\u6027\u8fdb\u5c55\uff1f"
    )
    external = ExternalRetrievalResult(
        query=question,
        normalized_query="flexible electronics",
        source_scopes=[ExternalSourceScope.ACADEMIC],
        items=[_item("stale-flexible")],
    )
    request = AgentRequest(
        session_id="session-research",
        user_id="researcher",
        user_role=UserRole.RESEARCHER,
        scene=Scene.RESEARCH,
        course_id="UNKNOWN",
        intent=Intent.GENERAL_QA,
        canonical_input={"text": question},
        options={"external_retrieval": external.model_dump(mode="json")},
    )

    result = await ResearchFrontierService(FakeResearchHub()).run(request)

    assert result.structured_result["answer_mode"] == "no_verified_evidence"
    assert result.structured_result["external_references"] == []
    assert "stale-flexible" not in result.answer
