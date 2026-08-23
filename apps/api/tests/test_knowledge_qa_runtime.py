from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.bootstrap.runtime_task_engine import _runtime_service_agent_ids
from app.contracts import AgentRequest, AgentResult
from app.runtime import AgentRun, RuntimeNodeStatus, RuntimeRunStatus
from app.services.knowledge_qa_runtime import KnowledgeQARuntimeService
from app.services.runtime_business_registry import RuntimeBusinessRegistry
from app.services.runtime_launch_policy import RuntimeLaunchMode, RuntimeLaunchPolicy


class FakeKnowledgeQA:
    def __init__(
        self,
        *,
        evidence_status: str = "sufficient",
        citations: list[str] | None = None,
        evidence: list[str] | None = None,
    ) -> None:
        self.calls = 0
        self.evidence_status = evidence_status
        self.citations = citations if citations is not None else [
            "kb://CT/chapter.md"
        ]
        self.evidence = evidence if evidence is not None else ["S1"]

    async def run_with_generation(
        self, _agent_id: str, _request: AgentRequest
    ) -> SimpleNamespace:
        self.calls += 1
        result = AgentResult(
            agent_id="LEARN_01_LOCAL_RETRIEVAL_V1",
            provider="local",
            answer="依据本地证据给出的回答 [S1]",
            structured_result={"mode": "retrieval_only"},
            citations=self.citations,
            evidence_status=self.evidence_status,
        )
        return SimpleNamespace(
            result=result,
            context=SimpleNamespace(
                evidence_status=self.evidence_status,
                evidence=self.evidence,
            ),
        )


class IncompleteSynthesisKnowledgeQA(FakeKnowledgeQA):
    async def run_with_generation(
        self, _agent_id: str, _request: AgentRequest
    ) -> SimpleNamespace:
        self.calls += 1
        result = AgentResult(
            agent_id="LEARN_01_LOCAL_RETRIEVAL_V1",
            provider="test-model",
            answer="根据用户记录整理的暂定学习路径。",
            structured_result={"mode": "learning_path_model_generation"},
            evidence_status="insufficient",
        )
        return SimpleNamespace(
            result=result,
            context=SimpleNamespace(evidence_status="insufficient", evidence=[]),
        )


class ModelRequiredKnowledgeQA(FakeKnowledgeQA):
    async def run_with_generation(
        self, _agent_id: str, _request: AgentRequest
    ) -> SimpleNamespace:
        self.calls += 1
        result = AgentResult(
            agent_id="LEARN_01_LOCAL_RETRIEVAL_V1",
            provider="model_unavailable",
            answer="",
            structured_result={"mode": "learning_path_model_required"},
            evidence_status="none",
        )
        return SimpleNamespace(
            result=result,
            context=SimpleNamespace(evidence_status="none", evidence=[]),
        )


def test_knowledge_qa_runtime_plan_version_is_exposed_to_registry() -> None:
    service = KnowledgeQARuntimeService(FakeKnowledgeQA(), enabled=True)  # type: ignore[arg-type]
    registry = RuntimeBusinessRegistry([service])

    assert (
        registry.runtime_plan_version("LEARN_01_LOCAL_RETRIEVAL_V1")
        == "knowledge-qa-v1"
    )


def test_knowledge_qa_runtime_alias_is_local_runtime_owned() -> None:
    service = KnowledgeQARuntimeService(FakeKnowledgeQA(), enabled=True)  # type: ignore[arg-type]
    agent_ids = _runtime_service_agent_ids(service)
    policy = RuntimeLaunchPolicy(
        release_gate_required=True,
        local_agents=agent_ids,
    )

    decision = policy.resolve(
        "LEARN_01_KNOWLEDGE_QA_V1",
        AgentRequest(
            task_id="knowledge-alias-task",
            session_id="knowledge-alias-session",
            user_id="knowledge-alias-user",
            course_id="AE",
        ),
        lifecycle_enabled=True,
        runtime_option_key="knowledge_qa_runtime",
    )

    assert set(agent_ids) == {
        "LEARN_01_KNOWLEDGE_QA_V1",
        "LEARN_01_LOCAL_RETRIEVAL_V1",
    }
    assert decision.mode == RuntimeLaunchMode.DEFAULT
    assert decision.reason == "registered_local_runtime"


@pytest.mark.asyncio
async def test_knowledge_qa_runtime_executes_and_verifies_once() -> None:
    fake = FakeKnowledgeQA()
    service = KnowledgeQARuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = AgentRequest(
        task_id="knowledge-runtime-task",
        session_id="knowledge-runtime-session",
        user_id="knowledge-runtime-user",
        course_id="CT",
        options={"knowledge_qa_runtime": {"execute": True}},
    )
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="knowledge-runtime-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )

    result = await service.run(request, run)

    assert fake.calls == 1
    assert result.provider == "local"
    assert run.status.value == "completed"
    assert all(
        node.status == RuntimeNodeStatus.SUCCEEDED for node in run.nodes.values()
    )
    assert run.nodes["knowledge.verify"].observation is not None
    assert run.nodes["knowledge.verify"].observation.facts["passed"] is True


@pytest.mark.asyncio
async def test_g2_04_verilog_timing_diagnosis_reaches_terminal_state() -> None:
    service = KnowledgeQARuntimeService(FakeKnowledgeQA(), enabled=True)  # type: ignore[arg-type]
    request = AgentRequest(
        task_id="team-feedback-g2-04-runtime",
        session_id="team-feedback-g2-04-session",
        user_id="team-feedback-g2-04-user",
        course_id="DE",
        canonical_input={
            "text": (
                "学生在Vivado中编写的分频器Verilog代码综合时出现了时序违例。"
                "请诊断排查常见错误，给出排错思路，并生成一道原理相似的验证题。"
            )
        },
        options={"knowledge_qa_runtime": {"execute": True}},
    )
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="team-feedback-g2-04-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )

    result = await service.run(request, run)

    assert result.answer
    assert run.status.value == "completed"
    assert all(
        node.status == RuntimeNodeStatus.SUCCEEDED for node in run.nodes.values()
    )


@pytest.mark.asyncio
async def test_knowledge_qa_verifier_records_evidence_facts_when_citations_exist(
) -> None:
    service = KnowledgeQARuntimeService(FakeKnowledgeQA(), enabled=True)  # type: ignore[arg-type]
    request = AgentRequest(
        task_id="knowledge-runtime-facts-task",
        session_id="knowledge-runtime-facts-session",
        user_id="knowledge-runtime-facts-user",
        course_id="CT",
        options={"knowledge_qa_runtime": {"execute": True}},
    )
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="knowledge-runtime-facts-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )

    await service.run(request, run)

    facts = run.nodes["knowledge.verify"].observation.facts
    assert facts["evidence_status"] == "sufficient"
    assert facts["evidence_count"] == 1
    assert facts["citation_count"] == 1
    assert facts["passed"] is True


@pytest.mark.asyncio
async def test_sufficient_evidence_without_citation_is_partial(
) -> None:
    service = KnowledgeQARuntimeService(
        FakeKnowledgeQA(citations=[], evidence=["S1"]), enabled=True
    )  # type: ignore[arg-type]
    request = AgentRequest(
        task_id="knowledge-runtime-missing-citation-task",
        session_id="knowledge-runtime-missing-citation-session",
        user_id="knowledge-runtime-missing-citation-user",
        course_id="CT",
        options={"knowledge_qa_runtime": {"execute": True}},
    )
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="knowledge-runtime-missing-citation-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )

    await service.run(request, run)

    observation = run.nodes["knowledge.verify"].observation
    assert observation.terminal_status == RuntimeNodeStatus.PARTIAL
    assert observation.facts["passed"] is False
    assert observation.facts["reason_code"] == "knowledge_citations_missing"
    assert observation.facts["evidence_count"] == 1
    assert observation.facts["citation_count"] == 0


@pytest.mark.asyncio
async def test_knowledge_qa_verifier_records_insufficient_evidence_as_needs_review(
) -> None:
    service = KnowledgeQARuntimeService(
        FakeKnowledgeQA(evidence_status="insufficient", citations=[], evidence=[]),
        enabled=True,
    )  # type: ignore[arg-type]
    request = AgentRequest(
        task_id="knowledge-runtime-insufficient-task",
        session_id="knowledge-runtime-insufficient-session",
        user_id="knowledge-runtime-insufficient-user",
        course_id="CT",
        options={"knowledge_qa_runtime": {"execute": True}},
    )
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="knowledge-runtime-insufficient-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )

    await service.run(request, run)

    observation = run.nodes["knowledge.verify"].observation
    assert observation.terminal_status == RuntimeNodeStatus.PARTIAL
    assert observation.facts["evidence_status"] == "insufficient"
    assert observation.facts["evidence_count"] == 0
    assert observation.facts["citation_count"] == 0
    assert observation.facts["passed"] is False
    assert observation.facts["needs_review"] is True


@pytest.mark.asyncio
async def test_incomplete_showcase_synthesis_completes_with_review_marker() -> None:
    service = KnowledgeQARuntimeService(
        IncompleteSynthesisKnowledgeQA(), enabled=True  # type: ignore[arg-type]
    )
    request = AgentRequest(
        task_id="knowledge-runtime-incomplete-synthesis",
        session_id="knowledge-runtime-incomplete-session",
        user_id="knowledge-runtime-incomplete-user",
        course_id="CT",
        options={"knowledge_qa_runtime": {"execute": True}},
    )
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="knowledge-runtime-incomplete-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )

    await service.run(request, run)

    observation = run.nodes["knowledge.verify"].observation
    assert run.status.value == "completed"
    assert observation is not None
    assert observation.terminal_status == RuntimeNodeStatus.SUCCEEDED
    assert observation.facts["evidence_incomplete"] is True
    assert observation.facts["needs_review"] is True


@pytest.mark.asyncio
async def test_model_required_synthesis_fails_with_specific_reason() -> None:
    service = KnowledgeQARuntimeService(
        ModelRequiredKnowledgeQA(), enabled=True  # type: ignore[arg-type]
    )
    request = AgentRequest(
        task_id="knowledge-runtime-model-required",
        session_id="knowledge-runtime-model-required-session",
        user_id="knowledge-runtime-model-required-user",
        course_id="AE",
        intent="learning_advice",
        scenario_id="student_learning_path_v1",
        options={"knowledge_qa_runtime": {"execute": True}},
    )
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="knowledge-runtime-model-required-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )

    await service.run(request, run)

    observation = run.nodes["knowledge.verify"].observation
    assert run.status == RuntimeRunStatus.FAILED
    assert observation is not None
    assert observation.terminal_status == RuntimeNodeStatus.PARTIAL
    assert observation.facts["reason_code"] == "model_generation_required"
    assert observation.facts["generation_required"] is True
