from __future__ import annotations

import html as html_lib
import re
from pathlib import Path

import pytest
from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, AgentResult, Intent
from app.services.response_depth import policy_for
from app.services.runtime_result_pipeline import RuntimeResultPipeline

_BUTTON_BLOCK = re.compile(r"<button\b(?P<body>.*?)</button>", re.DOTALL)
_DATA_ATTRIBUTE = re.compile(
    r'data-(?P<key>intent|prompt)="(?P<value>.*?)"', re.DOTALL
)
_EXPECTED_ROUTES = {
    "lesson_prep": ("TEACH_01_LESSON_PREP_V1", "lesson_prep"),
    "assignment_review": ("TEACH_02_ASSIGNMENT_REVIEW_V1", "assignment_review"),
    "learning_advice": (
        "LEARN_01_LOCAL_RETRIEVAL_V1",
        "learning_advice",
    ),
    "academic_search": ("RESEARCH_01_ACADEMIC_SEARCH_V1", "academic_search"),
    "summarize_knowledge": (
        "LEARN_01_LOCAL_RETRIEVAL_V1",
        "summarize_knowledge",
    ),
    "solve_problem": ("ACADEMIC_PROBLEM_SOLVER", "solve_problem"),
}


def _showcase_cases() -> dict[str, str]:
    root = Path(__file__).resolve().parents[3]
    source = (root / "apps/api/app/static/debug/workspace.html").read_text(
        encoding="utf-8"
    )
    cases: dict[str, str] = {}
    for match in _BUTTON_BLOCK.finditer(source):
        fields = {
            key: html_lib.unescape(value)
            for key, value in _DATA_ATTRIBUTE.findall(match.group("body"))
        }
        if fields.get("intent") in _EXPECTED_ROUTES:
            cases[fields["intent"]] = fields.get("prompt", "")
    return cases


def _request(
    text: str,
    *,
    course_id: str = "AUTO",
    intent: Intent = Intent.UNKNOWN,
    **options: object,
) -> AgentRequest:
    return AgentRequest(
        session_id="showcase-matrix",
        user_id="showcase-matrix-user",
        scene="dispatch",
        course_id=course_id,
        intent=intent,
        canonical_input={"text": text},
        options=dict(options),
    )


def test_workspace_includes_knowledge_qa_and_circuit_visualization_cases() -> None:
    root = Path(__file__).resolve().parents[3]
    source = (root / "apps/api/app/static/debug/workspace.html").read_text(
        encoding="utf-8"
    )
    buttons = {
        html_lib.unescape(match.group("capability")): match.group(0)
        for match in re.finditer(
            r'<button\b(?=[^>]*data-capability="(?P<capability>[^"]+)")[^>]*>',
            source,
        )
    }
    knowledge = buttons["course_qa"]
    circuit = [
        match.group(0)
        for match in re.finditer(
            r'<button\b(?=[^>]*data-capability="solve_problem")[^>]*data-circuit-visualization="true"[^>]*>',
            source,
        )
    ]
    assert 'data-intent="explain_concept"' in knowledge
    assert 'data-course="CT"' in knowledge
    assert len(re.findall(r"data-prompt=\"[^\"]+\"", knowledge)) == 1
    assert len(circuit) == 1
    assert 'data-intent="solve_problem"' in circuit[0]
    assert 'data-course="CT"' in circuit[0]


def test_added_showcase_requests_keep_their_backend_routes() -> None:
    knowledge = TaskRouter(AgentRegistry()).route(
        _request(
            "我在复习电路理论时总搞不清楚电容为什么不能突然改变电压。",
            course_id="CT",
            intent=Intent.EXPLAIN_CONCEPT,
            allow_cloud=False,
        )
    )
    circuit = TaskRouter(AgentRegistry()).route(
        _request(
            "请画出 12 V 电压源、R1=2 kΩ 和 R2=4 kΩ 串联分压电路，输出取 R2 两端。",
            course_id="CT",
            intent=Intent.SOLVE_PROBLEM,
            allow_cloud=False,
        )
    )
    assert (knowledge.agent_id, knowledge.intent) == (
        "LEARN_01_KNOWLEDGE_QA_V1",
        "explain_concept",
    )
    assert (circuit.agent_id, circuit.intent) == (
        "ACADEMIC_PROBLEM_SOLVER",
        "solve_problem",
    )


def test_six_showcase_prompts_route_to_their_declared_capabilities() -> None:
    cases = _showcase_cases()
    assert set(cases) == set(_EXPECTED_ROUTES)
    for capability, prompt in cases.items():
        assert prompt.strip(), capability
        assert _EXPECTED_ROUTES[capability][1] in _EXPECTED_ROUTES


@pytest.mark.parametrize(
    ("prompt", "expected_agent", "expected_intent"),
    [
        (
            "\u8bf7\u8bbe\u8ba1\u4e00\u8282\u8bfe\u5802\uff0c\u7ed9\u51fa\u5b66\u4e60\u76ee\u6807\u548c\u6559\u5b66\u6d41\u7a0b\u3002",
            "TEACH_01_LESSON_PREP_V1",
            "lesson_prep",
        ),
        (
            "请诊断学生作业，定位首个错误并保留正确步骤。",
            "TEACH_02_ASSIGNMENT_REVIEW_V1",
            "assignment_review",
        ),
        (
            "请给出7天学习路径、先修关系和复测任务。",
            "LEARN_01_LOCAL_RETRIEVAL_V1",
            "learning_advice",
        ),
        (
            "Search recent research papers and retain DOI or arXiv evidence.",
            "RESEARCH_01_ACADEMIC_SEARCH_V1",
            "academic_search",
        ),
        (
            "请检查课程资产版本、审批、发布阻塞和回滚清单。",
            "LEARN_01_LOCAL_RETRIEVAL_V1",
            "summarize_knowledge",
        ),
        (
            "\u8bf7\u8ba1\u7b97\u7535\u8def\u8282\u70b9\u7535\u538b\u5e76\u63a8\u5bfc\u6b65\u9aa4\u3002",
            "ACADEMIC_PROBLEM_SOLVER",
            "solve_problem",
        ),
    ],
)
def test_showcase_route_generalization(
    prompt: str, expected_agent: str, expected_intent: str
) -> None:
    decision = TaskRouter(AgentRegistry()).route(_request(prompt, allow_cloud=False))
    assert decision.agent_id == expected_agent
    assert decision.intent == expected_intent


def test_follow_up_keeps_learning_workflow_without_hiding_a_new_question() -> None:
    decision = TaskRouter(AgentRegistry()).route(
        _request(
            "Continue with two verification tasks from the previous answer.",
            previous_agent="LEARN_01_LOCAL_RETRIEVAL_V1",
            previous_intent="learning_advice",
            allow_cloud=False,
        )
    )
    assert decision.agent_id == "LEARN_01_LOCAL_RETRIEVAL_V1"
    assert decision.intent == "learning_advice"
    assert "session_continuity" in decision.reason_codes


@pytest.mark.parametrize(
    ("agent_id", "workflow"),
    [
        ("TEACH_01_LESSON_PREP_V1", "lesson_prep"),
        ("TEACH_02_ASSIGNMENT_REVIEW_V1", "internal_structured"),
        ("LEARN_01_LOCAL_RETRIEVAL_V1", "knowledge_qa"),
        ("RESEARCH_01_ACADEMIC_SEARCH_V1", "academic_search"),
        ("ACADEMIC_PROBLEM_SOLVER", "academic_solver"),
    ],
)
def test_depth_projection_is_visible_for_each_runtime_workflow(
    agent_id: str, workflow: str
) -> None:
    request = _request("test question", response_depth="deep")
    result = AgentResult(agent_id=agent_id, provider="local_agent")

    RuntimeResultPipeline._ensure_response_depth_metadata(result, request, agent_id)

    metadata = result.structured_result["response_depth"]
    assert metadata["level"] == "deep"
    assert metadata["max_output_tokens"] == policy_for(
        {"response_depth": "deep"}, workflow
    ).max_output_tokens


def test_academic_search_depth_changes_retrieval_budget() -> None:
    brief = policy_for({"response_depth": "brief"}, "academic_search")
    standard = policy_for({"response_depth": "standard"}, "academic_search")
    deep = policy_for({"response_depth": "deep"}, "academic_search")

    assert brief.retrieval_limit < standard.retrieval_limit < deep.retrieval_limit
    assert brief.evidence_limit < standard.evidence_limit < deep.evidence_limit
    assert brief.verify is False
    assert standard.verify is True
    assert deep.verify is True


def test_real_knowledge_synthesis_mode_is_not_overwritten_by_agent_mode() -> None:
    assert RuntimeResultPipeline._project_result_mode(
        "local_model", "learning_path_model_generation"
    ) == "learning_path_model_generation"
    assert RuntimeResultPipeline._project_result_mode(
        "local_model", "retrieval_only"
    ) == "local_model"
