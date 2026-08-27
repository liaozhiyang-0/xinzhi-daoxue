from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.contracts import (
    AgentRequest,
    AgentResult,
    AgentResultStatus,
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
    def __init__(self) -> None:
        self.calls = 0

    async def classify_intent(
        self, _request: AgentRequest
    ) -> ResearchIntentDecision:
        return ResearchIntentDecision(
            goal="frontier_brief",
            topic="agent planning",
            requires_web=True,
        )

    async def run(self, request: AgentRequest) -> AgentResult:
        self.calls += 1
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


class SequencedResearchFrontier(FakeResearchFrontier):
    def __init__(self, *modes: str) -> None:
        super().__init__()
        self.modes = list(modes)

    async def run(self, request: AgentRequest) -> AgentResult:
        self.calls += 1
        external = request.options["external_retrieval"]
        assert isinstance(external, dict)
        evidence_id = str(external["items"][0]["evidence_id"])
        mode = self.modes.pop(0) if self.modes else "valid"
        if mode == "failed":
            return AgentResult(
                status=AgentResultStatus.FAILED,
                agent_id="RESEARCH_01_ACADEMIC_SEARCH_V1",
                provider="local_agent",
                warnings=["synthetic answer failure"],
            )
        reference_id = "missing-paper" if mode == "invalid_citation" else evidence_id
        return AgentResult(
            agent_id="RESEARCH_01_ACADEMIC_SEARCH_V1",
            provider="local_agent",
            answer=f"A finding [{reference_id}]",
            structured_result={
                "status": "completed",
                "external_references": [reference_id],
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
        review_status="approved",
        approved_count=1,
        retrieval_trace_id=retrieval_trace_id,
    )


def _runtime_request(task_id: str) -> AgentRequest:
    return AgentRequest(
        task_id=task_id,
        session_id=f"{task_id}-session",
        user_id=f"{task_id}-user",
        canonical_input={"text": "latest agent planning papers"},
        options={"external_research_runtime": {"execute": True}},
    )


def _degraded_external_result(query: str) -> ExternalRetrievalResult:
    return _external_result(query).model_copy(
        update={
            "status": "partial",
            "review_status": "failed",
            "warnings": ["synthetic degraded review"],
        }
    )


def _electronics_scope_result(query: str) -> ExternalRetrievalResult:
    direct = ExternalEvidenceItem(
        evidence_id="electronics-education",
        source_type=ExternalSourceType.ACADEMIC_PAPER,
        provider="fake",
        source_ref="doi:10.1000/electronics-education",
        title="AI tutoring in electrical engineering education",
        canonical_url=TypeAdapter(AnyHttpUrl).validate_python(
            "https://example.org/electronics-education"
        ),
        content_excerpt=(
            "An intelligent tutoring system in an electrical engineering course "
            "with circuit design exercises."
        ),
        retrieved_at=datetime.now(UTC),
    )
    unrelated = ExternalEvidenceItem(
        evidence_id="nursing-education",
        source_type=ExternalSourceType.ACADEMIC_PAPER,
        provider="fake",
        source_ref="doi:10.1000/nursing-education",
        title="ChatGPT in nursing education",
        canonical_url=TypeAdapter(AnyHttpUrl).validate_python(
            "https://example.org/nursing-education"
        ),
        content_excerpt="Large language models in nursing education and training.",
        retrieved_at=datetime.now(UTC),
    )
    return ExternalRetrievalResult(
        query=query,
        normalized_query=query,
        source_scopes=[ExternalSourceScope.ACADEMIC],
        items=[direct, unrelated],
        provider_status={"fake": "completed"},
        approved_count=2,
    )


def test_external_retrieval_payload_withholds_unreviewed_candidates() -> None:
    request = _runtime_request("external-review-boundary-task")
    degraded = _degraded_external_result("latest agent planning papers")
    policy = ExternalRetrievalPolicy(
        enabled=True,
        source_scopes=[ExternalSourceScope.ACADEMIC],
        generation_injection=True,
    )

    guarded = ExternalResearchRuntimeService._with_retrieval(
        request,
        degraded,
        policy,
    )
    guarded_payload = guarded.options["external_retrieval"]
    assert isinstance(guarded_payload, dict)
    assert guarded_payload["items"] == []
    assert "retrieved_context" not in guarded.options

    approved = ExternalResearchRuntimeService._with_retrieval(
        request,
        degraded,
        policy,
        evidence_review_approved=True,
    )
    approved_payload = approved.options["external_retrieval"]
    assert isinstance(approved_payload, dict)
    assert approved_payload["items"][0]["evidence_id"] == "paper-001"
    assert approved.options["external_retrieval_untrusted"] is True


@pytest.mark.parametrize(
    ("review_status", "approved_count"),
    [("not_run", 1), ("approved", 0)],
)
def test_external_retrieval_review_metadata_mismatch_is_gated(
    review_status: str, approved_count: int
) -> None:
    request = _runtime_request("external-review-metadata-task")
    result = _external_result("latest agent planning papers").model_copy(
        update={
            "review_status": review_status,
            "approved_count": approved_count,
        }
    )
    policy = ExternalRetrievalPolicy(
        enabled=True,
        source_scopes=[ExternalSourceScope.ACADEMIC],
    )

    guarded = ExternalResearchRuntimeService._with_retrieval(
        request,
        result,
        policy,
    )

    payload = guarded.options["external_retrieval"]
    assert isinstance(payload, dict)
    assert payload["items"] == []


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
async def test_external_retrieval_execution_filters_cross_discipline_evidence() -> None:
    class FakeSearch:
        async def search(self, query: str, **_: object) -> ExternalRetrievalResult:
            return _electronics_scope_result(query)

    service = ExternalRetrievalExecutionService(
        settings=Settings(app_env="test", _env_file=None),  # type: ignore[call-arg]
        external_search=FakeSearch(),  # type: ignore[arg-type]
        external_fetcher=None,
        external_paper_reviewer=None,
        external_search_planner=None,
    )
    request = AgentRequest(
        task_id="external-filter-task",
        session_id="external-filter-session",
        user_id="external-filter-user",
        canonical_input={
            "text": "请检索电子信息课程智能辅导效果的近期研究",
        },
    )
    policy = ExternalRetrievalPolicy(
        enabled=True,
        source_scopes=[ExternalSourceScope.ACADEMIC],
    )

    result = await service.retrieve(request, policy)

    assert [item.evidence_id for item in result.items] == ["electronics-education"]
    assert result.approved_count == 1
    assert "cross-topic evidence was removed before display" in result.warnings


@pytest.mark.asyncio
async def test_external_retrieval_uses_fallback_after_primary_review_rejects_all(
) -> None:
    calls: list[tuple[str, ...]] = []

    class FakeSearch:
        def fallback_provider_names(
            self, **_: object
        ) -> tuple[str, ...]:
            return ("fallback",)

        async def search_many(
            self,
            query: str,
            *,
            provider_names: list[str] | tuple[str, ...] | None = None,
            **_: object,
        ) -> ExternalRetrievalResult:
            names = tuple(provider_names or ())
            calls.append(names)
            return _external_result(query).model_copy(
                update={"provider_status": {names[0]: "completed"}}
            )

    class RejectPrimaryReview:
        async def review(
            self,
            _query: str,
            result: ExternalRetrievalResult,
            **_: object,
        ) -> ExternalRetrievalResult:
            if "primary" in result.provider_status:
                return result.model_copy(
                    update={
                        "items": [],
                        "status": "failed",
                        "review_status": "rejected",
                        "approved_count": 0,
                        "warnings": ["primary evidence rejected"],
                    }
                )
            return result.model_copy(
                update={
                    "status": "completed",
                    "review_status": "approved",
                    "approved_count": len(result.items),
                }
            )

    service = ExternalRetrievalExecutionService(
        settings=Settings(app_env="test", _env_file=None),  # type: ignore[call-arg]
        external_search=FakeSearch(),  # type: ignore[arg-type]
        external_fetcher=None,
        external_paper_reviewer=RejectPrimaryReview(),  # type: ignore[arg-type]
        external_search_planner=None,
    )
    request = AgentRequest(
        task_id="external-fallback-task",
        session_id="external-fallback-session",
        user_id="external-fallback-user",
        canonical_input={"text": "latest agent planning papers"},
    )
    policy = ExternalRetrievalPolicy(
        enabled=True,
        source_scopes=[ExternalSourceScope.ACADEMIC],
        providers=["primary", "fallback"],
        max_iterations=1,
    )

    result = await service.retrieve(request, policy, allow_degraded_review=True)

    assert calls == [("primary", "fallback"), ("fallback",)]
    assert result.status == "completed"
    assert result.provider_status == {
        "primary": "completed",
        "fallback": "completed",
    }
    assert "fallback providers invoked after primary evidence review" in result.warnings


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
async def test_external_research_runtime_review_waits_for_approval_and_resumes(
) -> None:
    fetch_calls = 0

    async def retrieve(
        request: AgentRequest,
        _policy: ExternalRetrievalPolicy,
        *,
        allow_degraded_review: bool,
    ) -> ExternalRetrievalResult:
        nonlocal fetch_calls
        fetch_calls += 1
        assert allow_degraded_review is True
        return _degraded_external_result(str(request.canonical_input["text"]))

    frontier = FakeResearchFrontier()
    policy = ExternalRetrievalPolicy(
        enabled=True,
        source_scopes=[ExternalSourceScope.ACADEMIC],
    )
    service = ExternalResearchRuntimeService(
        frontier,  # type: ignore[arg-type]
        policy=policy,
        retrieve=retrieve,
        external_enabled=True,
        enabled=True,
    )
    request = _runtime_request("external-approval-task")
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="external-approval-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )

    with pytest.raises(RuntimeRunSuspended):
        await service.run(request, run)

    assert run.status.value == "waiting_approval"
    assert run.last_decision is not None
    assert run.last_decision.approval_scope == service.approval_scope
    assert run.nodes["research.fetch"].status == RuntimeNodeStatus.SUCCEEDED
    assert run.nodes["research.answer"].status == RuntimeNodeStatus.READY
    assert run.nodes["research.verify"].status == RuntimeNodeStatus.PENDING
    assert frontier.calls == 0
    assert fetch_calls == 1

    run.control_data["approved"] = True
    result = await service.run(request, run)

    assert result.status == AgentResultStatus.COMPLETED
    assert run.status.value == "completed"
    assert fetch_calls == 1
    assert frontier.calls == 1
    assert run.control_data == {}
    assert run.nodes["research.fetch"].attempt == 1
    assert run.nodes["research.verify"].observation is not None
    assert run.nodes["research.verify"].observation.facts["approval_granted"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_mode", ["answer", "verify"])
async def test_external_research_runtime_replans_answer_only_without_refetch(
    failure_mode: str,
) -> None:
    fetch_calls = 0

    async def retrieve(
        request: AgentRequest,
        _policy: ExternalRetrievalPolicy,
        *,
        allow_degraded_review: bool,
    ) -> ExternalRetrievalResult:
        nonlocal fetch_calls
        fetch_calls += 1
        assert allow_degraded_review is True
        return _external_result(str(request.canonical_input["text"]))

    frontier = SequencedResearchFrontier(
        "failed" if failure_mode == "answer" else "invalid_citation",
        "valid",
    )
    policy = ExternalRetrievalPolicy(
        enabled=True,
        source_scopes=[ExternalSourceScope.ACADEMIC],
    )
    service = ExternalResearchRuntimeService(
        frontier,  # type: ignore[arg-type]
        policy=policy,
        retrieve=retrieve,
        external_enabled=True,
        enabled=True,
    )
    request = _runtime_request(f"external-replan-{failure_mode}-task")
    plan = service.build_plan(request)
    run = AgentRun(
        run_id=f"external-replan-{failure_mode}-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )

    result = await service.run(request, run)

    assert result.status == AgentResultStatus.COMPLETED
    assert run.iteration == 1
    assert fetch_calls == 1
    assert frontier.calls == 2
    assert set(run.nodes) == {
        "research.intent",
        "research.fetch",
        "research.answer.replan.1",
        "research.verify.replan.1",
    }
    assert run.nodes["research.fetch"].status == RuntimeNodeStatus.SUCCEEDED
    assert run.nodes["research.fetch"].attempt == 1
    assert run.nodes["research.answer.replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )
    assert run.nodes["research.verify.replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )


@pytest.mark.asyncio
async def test_external_research_runtime_bounds_answer_only_replans() -> None:
    fetch_calls = 0

    async def retrieve(
        request: AgentRequest,
        _policy: ExternalRetrievalPolicy,
        *,
        allow_degraded_review: bool,
    ) -> ExternalRetrievalResult:
        nonlocal fetch_calls
        fetch_calls += 1
        assert allow_degraded_review is True
        return _external_result(str(request.canonical_input["text"]))

    frontier = SequencedResearchFrontier("failed", "failed", "failed")
    policy = ExternalRetrievalPolicy(
        enabled=True,
        source_scopes=[ExternalSourceScope.ACADEMIC],
    )
    service = ExternalResearchRuntimeService(
        frontier,  # type: ignore[arg-type]
        policy=policy,
        retrieve=retrieve,
        external_enabled=True,
        enabled=True,
    )
    request = _runtime_request("external-replan-budget-task")
    plan = service.build_plan(request)
    run = AgentRun(
        run_id="external-replan-budget-run",
        task_id=request.task_id,
        goal=plan.goal,
        plan=plan,
    )

    result = await service.run(request, run)

    assert result.status == AgentResultStatus.FAILED
    assert run.iteration == 2
    assert fetch_calls == 1
    assert frontier.calls == 3
    assert run.last_decision is not None
    assert run.last_decision.reason_codes == [
        "external_answer_replan_budget_exhausted"
    ]


@pytest.mark.asyncio
async def test_external_research_runtime_recovery_restores_checkpointed_result(
) -> None:
    fetch_calls = 0

    async def retrieve(
        request: AgentRequest,
        _policy: ExternalRetrievalPolicy,
        *,
        allow_degraded_review: bool,
    ) -> ExternalRetrievalResult:
        nonlocal fetch_calls
        fetch_calls += 1
        assert allow_degraded_review is True
        trace_id = request.options.get("external_retrieval_trace_id")
        assert isinstance(trace_id, str) and trace_id
        return _external_result(
            str(request.canonical_input["text"]),
            retrieval_trace_id=trace_id,
        )

    first_frontier = FakeResearchFrontier()
    policy = ExternalRetrievalPolicy(
        enabled=True,
        source_scopes=[ExternalSourceScope.ACADEMIC],
    )
    first_service = ExternalResearchRuntimeService(
        first_frontier,  # type: ignore[arg-type]
        policy=policy,
        retrieve=retrieve,
        external_enabled=True,
        enabled=True,
    )
    request = _runtime_request("external-checkpoint-result-task")
    plan = first_service.build_plan(request)
    run = AgentRun(
        run_id="external-checkpoint-result-run",
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
            == RuntimeNodeStatus.SUCCEEDED
            and run_to_checkpoint.nodes["research.answer"].status
            == RuntimeNodeStatus.READY
        ):
            process_loss_simulated = True
            raise RuntimeError("simulated checkpoint loss after fetch")

    with pytest.raises(
        RuntimeError, match="simulated checkpoint loss after fetch"
    ):
        await first_service.run(request, run, checkpoint_hook=checkpoint)
    assert fetch_calls == 1
    assert run.nodes["research.fetch"].observation is not None
    assert "external_result_payload" in run.nodes["research.fetch"].observation.facts

    second_frontier = FakeResearchFrontier()
    second_service = ExternalResearchRuntimeService(
        second_frontier,  # type: ignore[arg-type]
        policy=policy,
        retrieve=retrieve,
        external_enabled=True,
        enabled=True,
    )
    result = await second_service.run(request, run)

    assert result.status == AgentResultStatus.COMPLETED
    assert fetch_calls == 1
    assert second_frontier.calls == 1
    assert run.nodes["research.fetch"].attempt == 1


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
