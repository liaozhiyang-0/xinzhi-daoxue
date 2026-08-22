from __future__ import annotations

from app.capabilities import default_capability_registry
from app.contracts.planner import CanonicalGoal
from app.courses import default_course_registry
from app.services.skill_policy import SkillPolicy
from app.services.skill_registry import SkillRegistry
from app.services.skill_retriever import SkillRetrievalRequest, SkillRetriever


def _services() -> tuple[SkillRetriever, SkillPolicy]:
    registry = SkillRegistry(
        default_course_registry(), default_capability_registry()
    )
    return SkillRetriever(registry), SkillPolicy(registry)


def test_retriever_is_deterministic_and_bounded_for_ct() -> None:
    retriever, _ = _services()
    request = SkillRetrievalRequest(
        goal=CanonicalGoal(objective="节点电压法求节点电压", course="CT"),
        course="CT",
        problem_type="node_voltage",
        capabilities=["circuit_analysis"],
        available_skill_ids=["CT.KCL"],
    )

    matches = retriever.retrieve(request, top_k=1)

    assert len(matches) == 1
    assert matches[0].skill_id == "CT.NODAL"
    assert "problem_type:node_voltage" in matches[0].match_reasons


def test_course_only_goal_does_not_pollute_general_fallback() -> None:
    retriever, _ = _services()
    request = SkillRetrievalRequest(
        goal=CanonicalGoal(objective="请帮我安排一个学习任务", course="CT"),
        course="CT",
        problem_type="general",
    )

    assert retriever.retrieve(request) == []


def test_policy_rejects_missing_prerequisite_and_worker() -> None:
    retriever, policy = _services()
    request = SkillRetrievalRequest(
        goal=CanonicalGoal(objective="评审研究证据", course="RESEARCH"),
        course="RESEARCH",
        problem_type="evidence_review",
        evidence_state={"source_refs": True},
    )
    matches = retriever.retrieve(request)

    result = policy.evaluate(matches, request)

    assert result.approved == []
    assert result.rejected[0].reason_codes == [
        "prerequisite_missing",
        "worker_dependency_unavailable",
    ]


def test_policy_allows_research_skill_only_with_registered_dependencies() -> None:
    retriever, policy = _services()
    request = SkillRetrievalRequest(
        goal=CanonicalGoal(objective="规划学术检索", course="RESEARCH"),
        course="RESEARCH",
        problem_type="academic_search",
        available_workers=["AcademicSearchPlannerService"],
        evidence_state={"query_scope": True},
    )

    result = policy.evaluate(retriever.retrieve(request), request)

    assert [item.skill_id for item in result.approved] == [
        "RESEARCH.QUERY_PLANNING"
    ]


def test_policy_rejects_unregistered_and_version_injection() -> None:
    _, policy = _services()
    request = SkillRetrievalRequest(course="CT")

    result = policy.validate_requested(
        ["CT.KCL", "CT.NOT_REGISTERED"],
        request,
        versions={"CT.KCL": "99.0"},
    )

    assert result.approved == []
    assert [item.skill_id for item in result.rejected] == [
        "CT.NOT_REGISTERED",
        "CT.KCL",
    ]
    assert result.rejected[0].reason_codes == ["unregistered_skill"]
    assert result.rejected[1].reason_codes == ["version_mismatch"]
