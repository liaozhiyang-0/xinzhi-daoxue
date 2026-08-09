from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from app.contracts import AgentRequest, Artifact, ArtifactType
from app.runtime import AgentRun, RuntimeNodeStatus, RuntimeRunStatus
from app.services.knowledge_qa_runtime import KnowledgeQARuntimeService

from tests.test_knowledge_qa_runtime import FakeKnowledgeQA


class ArtifactKnowledgeQA(FakeKnowledgeQA):
    """Extend the shared fake with a local artifact-only evidence path."""

    async def run_with_generation(
        self, agent_id: str, request: AgentRequest
    ) -> SimpleNamespace:
        execution = await super().run_with_generation(agent_id, request)
        artifact = Artifact(
            artifact_type=ArtifactType.ANSWER,
            owner_id=request.user_id,
            task_id=request.task_id,
            course_id=request.course_id,
            content={"answer": execution.result.answer},
            source_refs=["kb://CT/chapter.md"],
        )
        return SimpleNamespace(
            result=execution.result.model_copy(update={"artifacts": [artifact]}),
            context=execution.context,
        )


class InvalidResultKnowledgeQA(FakeKnowledgeQA):
    """Return a contract-invalid result without introducing a real Provider."""

    def __init__(self, update: dict[str, Any]) -> None:
        super().__init__()
        self.update = update

    async def run_with_generation(
        self, agent_id: str, request: AgentRequest
    ) -> SimpleNamespace:
        execution = await super().run_with_generation(agent_id, request)
        return SimpleNamespace(
            result=execution.result.model_copy(update=self.update),
            context=execution.context,
        )


def _request(task_id: str) -> AgentRequest:
    return AgentRequest(
        task_id=task_id,
        session_id=f"{task_id}-session",
        user_id=f"{task_id}-user",
        course_id="CT",
        options={"knowledge_qa_runtime": {"execute": True}},
    )


def _run_for(
    service: KnowledgeQARuntimeService, request: AgentRequest
) -> AgentRun:
    plan = service.build_plan(request)
    return AgentRun(
        run_id=f"{request.task_id}-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )


@pytest.mark.asyncio
async def test_execute_then_verify_is_the_only_current_plan() -> None:
    fake = FakeKnowledgeQA()
    service = KnowledgeQARuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = _request("knowledge-contract-order")
    run = _run_for(service, request)

    await service.run(request, run)

    assert [node.node_id for node in run.plan.nodes] == [
        "knowledge.execute",
        "knowledge.verify",
    ]
    assert [observation.node_id for observation in run.observations] == [
        "knowledge.execute",
        "knowledge.verify",
    ]
    assert run.iteration == 0
    assert run.status == RuntimeRunStatus.COMPLETED
    assert all(
        state.status == RuntimeNodeStatus.SUCCEEDED
        for state in run.nodes.values()
    )


@pytest.mark.asyncio
async def test_sufficient_evidence_with_citation_commits_success() -> None:
    fake = FakeKnowledgeQA()
    service = KnowledgeQARuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = _request("knowledge-contract-citation")
    run = _run_for(service, request)

    result = await service.run(request, run)

    verification = run.nodes["knowledge.verify"]
    assert result.provider == "local"
    assert fake.calls == 1
    assert run.status == RuntimeRunStatus.COMPLETED
    assert verification.status == RuntimeNodeStatus.SUCCEEDED
    assert verification.observation is not None
    assert verification.observation.facts == {
        "passed": True,
        "result_status": "completed",
        "mode": "retrieval_only",
        "evidence_status": "sufficient",
        "evidence_count": 1,
        "citation_count": 1,
    }


@pytest.mark.asyncio
async def test_sufficient_evidence_with_artifact_can_commit_without_citation() -> None:
    fake = ArtifactKnowledgeQA(citations=[])
    service = KnowledgeQARuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = _request("knowledge-contract-artifact")
    run = _run_for(service, request)

    await service.run(request, run)

    verification = run.nodes["knowledge.verify"]
    assert run.status == RuntimeRunStatus.COMPLETED
    assert verification.status == RuntimeNodeStatus.SUCCEEDED
    assert verification.observation is not None
    assert verification.observation.facts["citation_count"] == 0
    assert verification.observation.artifact_ids
    assert verification.observation.facts["passed"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("evidence_status", "citations", "evidence", "reason_code"),
    [
        ("insufficient", [], [], "knowledge_evidence_insufficient"),
        ("sufficient", [], ["S1"], "knowledge_citations_missing"),
    ],
)
async def test_missing_evidence_or_citation_cannot_commit_success(
    evidence_status: str,
    citations: list[str],
    evidence: list[str],
    reason_code: str,
) -> None:
    fake = FakeKnowledgeQA(
        evidence_status=evidence_status,
        citations=citations,
        evidence=evidence,
    )
    service = KnowledgeQARuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = _request(f"knowledge-contract-rejected-{reason_code}")
    run = _run_for(service, request)

    await service.run(request, run)

    verification = run.nodes["knowledge.verify"]
    assert run.status == RuntimeRunStatus.FAILED
    assert verification.status == RuntimeNodeStatus.PARTIAL
    assert verification.observation is not None
    assert verification.observation.facts["passed"] is False
    assert verification.observation.facts["reason_code"] == reason_code
    assert run.completed_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "update",
    [
        {"structured_result": {"mode": "untrusted_generation"}},
        {"answer": ""},
    ],
)
async def test_invalid_result_fails_closed_without_success_commit(
    update: dict[str, Any],
) -> None:
    fake = InvalidResultKnowledgeQA(update)
    service = KnowledgeQARuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = _request("knowledge-contract-invalid")
    run = _run_for(service, request)

    await service.run(request, run)

    verification = run.nodes["knowledge.verify"]
    assert run.status == RuntimeRunStatus.FAILED
    assert verification.status == RuntimeNodeStatus.PARTIAL
    assert verification.observation is not None
    assert verification.observation.facts["passed"] is False
    assert verification.observation.facts["replan_required"] is False
    assert run.completed_at is not None
