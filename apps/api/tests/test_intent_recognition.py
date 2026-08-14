from __future__ import annotations

from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, Intent, RouteDecision, RouteStatus, Scene
from app.services.intent_plan import IntentPlanCompiler
from app.services.intent_recognition import IntentRecognitionService


def request(
    text: str,
    intent: Intent = Intent.UNKNOWN,
    options: dict[str, object] | None = None,
) -> AgentRequest:
    return AgentRequest(
        session_id="session_intent",
        user_id="user_intent",
        scene=Scene.LEARNING,
        course_id="UNKNOWN",
        intent=intent,
        canonical_input={"text": text},
        options=options or {},
    )


def test_recognizes_research_frontier_as_workflow() -> None:
    result = IntentRecognitionService().recognize(
        request("近三年柔性电子器件的关键进展是什么？")
    )

    assert result.task_family == "research"
    assert result.intent == "academic_search"
    assert result.route_mode == "workflow"
    assert result.needs_external_retrieval is True
    assert result.parallelizable is True
    assert "academic-frontier" in result.selected_skills


def test_recognizes_chinese_numeral_research_variant() -> None:
    result = IntentRecognitionService().recognize(
        request(
            "\u8fd1\u4e24\u5e74\u67d4\u6027\u57fa\u5e95\u4e0a\u7684\u795e\u7ecf\u5f62\u6001\u5668\u4ef6\u6709\u54ea\u4e9b\u503c\u5f97\u5173\u6ce8\u7684\u6280\u672f\u65b9\u5411\uff1f"
        )
    )

    assert result.intent == "academic_search"
    assert result.needs_external_retrieval is True


def test_recognizes_short_research_follow_up_from_session_context() -> None:
    follow_up_request = request(
        "接着提供一些额外的论文信息",
        options={
            "previous_agent": "RESEARCH_01_ACADEMIC_SEARCH_V1",
            "previous_answer_summary": "上一轮已经完成科研前沿检索并返回论文证据。",
        },
    )
    result = IntentRecognitionService().recognize(follow_up_request)
    decision = TaskRouter(AgentRegistry()).route(follow_up_request)

    assert result.intent == "academic_search"
    assert "session_continuity" in result.reason_codes
    assert result.needs_external_retrieval is True
    assert decision.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    assert decision.intent == "academic_search"
    assert decision.route_trace[0]["intent"] == "academic_search"


def test_writing_request_with_source_restriction_is_not_research_search() -> None:
    result = IntentRecognitionService().recognize(
        request("帮我写一个论文摘要，来源仅限下面文字。")
    )
    decision = TaskRouter(AgentRegistry()).route(
        request("帮我写一个论文摘要，来源仅限下面文字。")
    )

    assert result.intent == "academic_writing"
    assert result.needs_external_retrieval is False
    assert decision.agent_id == "RESEARCH_02_ACADEMIC_WRITING_V1"


def test_conflicting_workflow_request_uses_general_clarification_path() -> None:
    request_text = "既要教案又要论文润色。"
    result = IntentRecognitionService().recognize(request(request_text))
    decision = TaskRouter(AgentRegistry()).route(request(request_text))

    assert result.intent == "general_qa"
    assert decision.agent_id == "GENERAL_QUESTION_V1"


def test_analysis_then_writing_request_keeps_analysis_as_primary_intent() -> None:
    request_text = "先分析这些实验数据，然后把结果写成论文段落。"
    result = IntentRecognitionService().recognize(request(request_text))
    decision = TaskRouter(AgentRegistry()).route(request(request_text))

    assert result.intent == "data_analysis"
    assert decision.agent_id == "RESEARCH_03_DATA_ANALYSIS_V1"


def test_writing_request_with_missing_data_notice_stays_academic_writing() -> None:
    request_text = (
        "\u8bf7\u5c06\u201c\u5b9e\u9a8c\u8bf4\u660e\u6ee4\u6ce2\u5668\u6548\u679c\u5f88\u597d\u201d"
        "\u6539\u5199\u4e3a\u4e25\u8c28\u5b66\u672f\u8868\u8fbe\uff1b"
        "\u6ca1\u6709\u63d0\u4f9b\u5b9e\u9a8c\u6570\u636e\u3002"
    )
    result = IntentRecognitionService().recognize(request(request_text))
    decision = TaskRouter(AgentRegistry()).route(request(request_text))

    assert result.intent == "academic_writing"
    assert decision.agent_id == "RESEARCH_02_ACADEMIC_WRITING_V1"


def test_statistical_result_then_writing_request_is_a_pipeline() -> None:
    request_text = "分析AUC结果后，再写成学术摘要。"
    result = IntentRecognitionService().recognize(request(request_text))
    decision = TaskRouter(AgentRegistry()).route(request(request_text))

    assert result.intent == "data_analysis"
    assert decision.agent_id == "RESEARCH_03_DATA_ANALYSIS_V1"
    assert decision.requires_pipeline is True


def test_explicit_learning_intent_stays_single_agent() -> None:
    result = IntentRecognitionService().recognize(
        request("解释戴维南定理", intent=Intent.EXPLAIN_CONCEPT)
    )

    assert result.intent == Intent.EXPLAIN_CONCEPT.value
    assert result.route_mode == "single_agent"
    assert result.needs_subagents is False


def test_concept_explanation_with_circuit_terms_uses_knowledge_route() -> None:
    text = (
        "\u8bf7\u7528\u57fa\u5c14\u970d\u592b\u7535\u6d41\u5b9a\u5f8b\u8bf4\u660e\u8282\u70b9\u7535\u6d41\u5173\u7cfb\uff0c"
        "\u5e76\u7ed9\u51fa\u4e00\u4e2a\u7b80\u5355\u516c\u5f0f\u4f8b\u5b50\u3002"
    )

    result = IntentRecognitionService().recognize(request(text))
    decision = TaskRouter(AgentRegistry()).route(
        request(text).model_copy(update={"course_id": "CT"})
    )

    assert result.intent == "explain_concept"
    assert decision.agent_id == "LEARN_01_LOCAL_RETRIEVAL_V1"
    assert decision.intent == "explain_concept"


def test_explicit_circuit_calculation_stays_solver_route() -> None:
    text = (
        "\u5df2\u77e5\u7535\u963b 2\u03a9 \u548c 3\u03a9 \u4e32\u8054\uff0c"
        "\u8bf7\u8ba1\u7b97\u603b\u7535\u963b\u3002"
    )

    result = IntentRecognitionService().recognize(request(text))

    assert result.intent == "solve_problem"


def test_router_attaches_structured_intent_context() -> None:
    decision = TaskRouter(AgentRegistry()).route(
        request("近三年柔性电子器件的关键进展是什么？")
    )

    assert decision.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    assert decision.intent_recognition["intent"] == "academic_search"
    assert "evidence_synthesis" in decision.capabilities
    assert decision.route_mode == "workflow"
    assert decision.needs_subagents is True


def test_plan_compiler_creates_bounded_research_dag() -> None:
    decision = TaskRouter(AgentRegistry()).route(
        request("近三年柔性电子器件的关键进展是什么？")
    )
    plan = IntentPlanCompiler().compile(request("研究柔性电子"), decision)

    assert plan.mode == "workflow"
    assert [node.node_id for node in plan.nodes] == [
        "research.retrieve",
        "research.review",
        "research.compose",
    ]
    assert plan.nodes[1].depends_on == ["research.retrieve"]
    assert plan.nodes[0].parallel_group == "research_sources"
    assert plan.max_parallelism == 4


def test_plan_compiler_has_safe_primary_fallback() -> None:
    decision = RouteDecision(
        agent_id="GENERAL_QUESTION_V1",
        scene="learning",
        course_id="UNKNOWN",
        intent="general_qa",
        route_status=RouteStatus.SELECTED,
        reason="test",
        retrieval_required=False,
        provider_required=False,
    )
    plan = IntentPlanCompiler().compile(request("你好"), decision)

    assert plan.mode == "single_agent"
    assert plan.nodes[0].target_id == "GENERAL_QUESTION_V1"
    assert plan.max_parallelism == 1
