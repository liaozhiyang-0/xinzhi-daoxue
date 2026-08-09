from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.contracts import (
    AgentRequest,
    AgentResult,
    ExternalEvidenceItem,
    ExternalEvidenceSupport,
    ExternalRetrievalPolicy,
    ExternalRetrievalResult,
    ExternalSourceScope,
    ExternalSourceType,
)
from app.contracts.research import ResearchIntentDecision
from app.core.config import Settings
from app.runtime import AgentRun, RuntimeNodeStatus, RuntimeRunSuspended
from app.services.external_research_runtime import ExternalResearchRuntimeService
from app.services.external_retrieval_execution import (
    ExternalRetrievalExecutionService,
)
from pydantic import AnyHttpUrl, TypeAdapter


class FakeResearchFrontier:
    async def classify_intent(
        self, _request: AgentRequest
    ) -> ResearchIntentDecision:
        return ResearchIntentDecision(
            goal="frontier_brief",
            topic="agent planning",
            requires_web=True,
        )

    async def run(self, request: AgentRequest) -> AgentResult:
        external = request.options["external_retrieval"]
        assert isinstance(external, dict)
        evidence_id = str(external["items"][0]["evidence_id"])
        return AgentResult(
            agent_id="RESEARCH_01_ACADEMIC_SEARCH_V1",
            provider="local_agent",
            answer=f"A verified finding [{evidence_id}]",
            structured_result={
                "status": "completed",
                "external_references": [evidence_id],
            },
            evidence_status="sufficient",
        )


def _external_result(
    query: str, *, retrieval_trace_id: str = ""
) -> ExternalRetrievalResult:
    return ExternalRetrievalResult(
        query=query,
        normalized_query=query,
        source_scopes=[ExternalSourceScope.ACADEMIC],
        items=[
            ExternalEvidenceItem(
                evidence_id="paper-001",
                source_type=ExternalSourceType.ACADEMIC_PAPER,
                provider="fake",
                source_ref="doi:10.1000/example",
                title="Agent planning",
                canonical_url=TypeAdapter(AnyHttpUrl).validate_python(
                    "https://example.org/paper"
                ),
                content_excerpt="A bounded abstract.",
                retrieved_at=datetime.now(UTC),
                support_level=ExternalEvidenceSupport.RETRIEVED,
            )
        ],
        provider_status={"fake": "completed"},
        retrieval_trace_id=retrieval_trace_id,
    )


@pytest.mark.asyncio
async def test_external_retrieval_execution_service_owns_provider_orchestration(
) -> None:
    class FakeSearch:
        async def search(self, query: str, **_: object) -> ExternalRetrievalResult:
            return _external_result(query)

    service = ExternalRetrievalExecutionService(
        settings=Settings(  # type: ignore[call-arg]
            app_env="test", _env_file=None
        ),
        external_search=FakeSearch(),  # type: ignore[arg-type]
        external_fetcher=None,
        external_paper_reviewer=None,
        external_search_planner=None,
    )
    request = AgentRequest(
        task_id="external-execution-task",
        session_id="external-execution-session",
        user_id="external-execution-user",
        canonical_input={"text": "agent planning"},
    )
    policy = ExternalRetrievalPolicy(
        enabled=True,
        source_scopes=[ExternalSourceScope.ACADEMIC],
    )

    result = await service.retrieve(request, policy)

    assert result.status == "completed"
    assert result.items[0].evidence_id == "paper-001"


@pytest.mark.asyncio
async def test_external_research_runtime_executes_intent_fetch_answer_verify() -> None:
    calls = 0

    async def retrieve(
        request: AgentRequest,
        _policy: ExternalRetrievalPolicy,
        *,
        allow_degraded_review: bool,
    ) -> ExternalRetrievalResult:
        nonlocal calls
        calls += 1
        assert allow_degraded_review is True
        trace_id = request.options.get("external_retrieval_trace_id")
        assert isinstance(trace_id, str) and trace_id
        return _external_result(
            str(request.canonical_input["text"]),
            retrieval_trace_id=trace_id,
        )

    policy = ExternalRetrievalPolicy(
        enabled=True,
        source_scopes=[ExternalSourceScope.ACADEMIC],
        generation_injection=True,
    )
    service = ExternalResearchRuntimeService(
        FakeResearchFrontier(),  # type: ignore[arg-type]
        policy=policy,
        retrieve=retrieve,
        external_enabled=True,
        enabled=True,
    )
    request = AgentRequest(
        task_id="external-research-task",
        session_id="external-research-session",
        user_id="external-research-user",
        course_id="UNKNOWN",
        canonical_input={"text": "latest agent planning papers"},
        options={"external_research_runtime": {"execute": True}},
    )
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="external-research-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )

    result = await service.run(request, run)

    assert calls == 1
    assert result.provider == "local_agent"
    assert result.structured_result["external_citation_validation"]["status"] == (
        "passed"
    )
    assert run.status.value == "completed"
    assert all(
        node.status == RuntimeNodeStatus.SUCCEEDED for node in run.nodes.values()
    )
    assert run.nodes["research.fetch"].observation is not None
    fetch_state = run.nodes["research.fetch"]
    assert fetch_state.execution_key == "external-research-run:research.fetch"
    assert fetch_state.reconciliation_id == (
        "runtime:external-research-run:research.fetch"
    )
    assert fetch_state.provider_trace_id == fetch_state.reconciliation_id
    assert fetch_state.observation is not None
    assert fetch_state.observation.facts["reconciliation_id"] == (
        fetch_state.reconciliation_id
    )
    assert fetch_state.observation.facts["provider_trace_id"] == (
        fetch_state.provider_trace_id
    )
    assert run.nodes["research.verify"].observation is not None
    assert run.nodes["research.verify"].observation.facts["passed"] is True


@pytest.mark.asyncio
async def test_external_research_runtime_pauses_unknown_provider_effect() -> None:
    async def retrieve(
        _request: AgentRequest,
        _policy: ExternalRetrievalPolicy,
        *,
        allow_degraded_review: bool,
    ) -> ExternalRetrievalResult:
        del allow_degraded_review
        return _external_result("agent planning")

    policy = ExternalRetrievalPolicy(
        enabled=True,
        source_scopes=[ExternalSourceScope.ACADEMIC],
    )
    service = ExternalResearchRuntimeService(
        FakeResearchFrontier(),  # type: ignore[arg-type]
        policy=policy,
        retrieve=retrieve,
        external_enabled=True,
        enabled=True,
    )
    request = AgentRequest(
        task_id="external-recovery-task",
        session_id="external-recovery-session",
        user_id="external-recovery-user",
        canonical_input={"text": "agent planning"},
        options={"external_research_runtime": {"execute": True}},
    )
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="external-recovery-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )
    process_loss_simulated = False

    async def checkpoint(run_to_checkpoint: AgentRun) -> None:
        nonlocal process_loss_simulated
        if (
            not process_loss_simulated
            and run_to_checkpoint.nodes["research.fetch"].status
            == RuntimeNodeStatus.RUNNING
        ):
            process_loss_simulated = True
            raise RuntimeError("simulated process loss")

    with pytest.raises(RuntimeError, match="simulated process loss"):
        await service.run(request, run, checkpoint_hook=checkpoint)
    assert run.nodes["research.fetch"].status == RuntimeNodeStatus.RUNNING
    assert run.nodes["research.fetch"].reconciliation_id == (
        "runtime:external-recovery-run:research.fetch"
    )

    with pytest.raises(RuntimeRunSuspended):
        await service.run(request, run)
    assert run.status.value == "paused"
    assert run.nodes["research.fetch"].effect_status.value == "unknown"
    assert (
        run.nodes["research.fetch"].error_code
        == "in_flight_execution_requires_reconciliation"
    )
