from __future__ import annotations

import html
import re
from pathlib import Path

import pytest
from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, AgentResult, Intent
from app.services.response_depth import policy_for
from app.services.runtime_result_pipeline import RuntimeResultPipeline

_SHOWCASE_BUTTON = re.compile(
    r'<button type="button" data-capability="([^"]+)"[^>]*'
    r'data-prompt="([^"]*)"',
    re.DOTALL,
)
_EXPECTED_ROUTES = {
    "lesson_prep": ("TEACH_01_LESSON_PREP_V1", "lesson_prep"),
    "assignment_review": ("TEACH_02_ASSIGNMENT_REVIEW_V1", "assignment_review"),
    "student_learning_path": (
        "LEARN_01_LOCAL_RETRIEVAL_V1",
        "learning_advice",
    ),
    "academic_search": ("RESEARCH_01_ACADEMIC_SEARCH_V1", "academic_search"),
    "knowledge_governance": (
        "LEARN_01_LOCAL_RETRIEVAL_V1",
        "summarize_knowledge",
    ),
    "solve_problem": ("ACADEMIC_PROBLEM_SOLVER", "solve_problem"),
}


def _showcase_cases() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]
    page = (root / "app/static/debug/workspace.html").read_text(encoding="utf-8")
    return {
        capability: html.unescape(prompt)
        for capability, prompt in _SHOWCASE_BUTTON.findall(page)
    }


def _request(text: str, **options: object) -> AgentRequest:
    return AgentRequest(
        session_id="showcase-matrix",
        user_id="showcase-matrix-user",
        scene="dispatch",
        course_id="AUTO",
        intent=Intent.UNKNOWN,
        canonical_input={"text": text},
        options=dict(options),
    )


def test_six_showcase_prompts_route_to_their_declared_capabilities() -> None:
    cases = _showcase_cases()
    assert set(cases) == set(_EXPECTED_ROUTES)

    router = TaskRouter(AgentRegistry())
    for capability, prompt in cases.items():
        decision = router.route(_request(prompt, allow_cloud=False))
        expected_agent, expected_intent = _EXPECTED_ROUTES[capability]
        assert decision.agent_id == expected_agent, capability
        assert decision.intent == expected_intent, capability
        assert decision.route_status.value == "selected", capability


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
