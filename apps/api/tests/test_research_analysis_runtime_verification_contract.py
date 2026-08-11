from __future__ import annotations

import asyncio

import pytest
from app.contracts import AgentRequest, AgentResult, AgentResultStatus
from app.contracts.research_analysis import (
    ResearchAnalysisResult,
    ResearchDataQualityReport,
)
from app.runtime import (
    AgentRun,
    RuntimeNodeError,
    RuntimeNodeStatus,
    RuntimeRunStatus,
    RuntimeRunSuspended,
)
from app.services.research_analysis_runtime import ResearchAnalysisRuntimeService


class ProviderFreeInternalAgent:
    def __init__(self, result: AgentResult) -> None:
        self.result = result
        self.calls = 0

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: object = None,
    ) -> AgentResult:
        assert agent_id == ResearchAnalysisRuntimeService.agent_id
        assert request.task_id == "task-research-verification-contract"
        assert context is None
        self.calls += 1
        return self.result


def make_request() -> AgentRequest:
    return AgentRequest(
        task_id="task-research-verification-contract",
        session_id="session-research-verification",
        user_id="user-research-verification",
        options={
            "research_analysis_v2": {
                "execute": True,
                "request": {
                    "research_question": "Does the intervention change the outcome?",
                    "analysis_goal": "compare",
                    "design": "experimental_comparison",
                },
            }
        },
    )


def make_analysis_payload(
    status: str,
    *,
    quality_status: str = "passed",
) -> dict[str, object]:
    return ResearchAnalysisResult(
        status=status,  # type: ignore[arg-type]
        data_quality=ResearchDataQualityReport(status=quality_status),  # type: ignore[arg-type]
        design_assessment="provider-free verification fixture",
    ).model_dump(mode="json")


def make_result(
    payload: dict[str, object],
    *,
    source: str = "business_data",
) -> AgentResult:
    if source == "business_data":
        return AgentResult(
            status=AgentResultStatus.COMPLETED,
            agent_id=ResearchAnalysisRuntimeService.agent_id,
            provider="provider-free-fake",
            structured_result={"analysis_v2": True},
            business_data=payload,
        )
    if source == "structured_business_data":
        return AgentResult(
            status=AgentResultStatus.COMPLETED,
            agent_id=ResearchAnalysisRuntimeService.agent_id,
            provider="provider-free-fake",
            structured_result={"analysis_v2": True, "business_data": payload},
        )
    return AgentResult(
        status=AgentResultStatus.COMPLETED,
        agent_id=ResearchAnalysisRuntimeService.agent_id,
        provider="provider-free-fake",
        structured_result={"analysis_v2": True, **payload},
    )


def make_run(
    service: ResearchAnalysisRuntimeService,
    request: AgentRequest,
) -> AgentRun:
    return AgentRun(
        run_id=f"run-{request.task_id}",
        task_id=request.task_id,
        goal="research analysis verification",
        plan=service.build_plan(request),
    )


@pytest.mark.parametrize(
    ("status", "quality_status"),
    [
        ("planning", "not_checked"),
        ("quality_blocked", "blocked"),
        ("insufficient_data", "passed"),
    ],
)
def test_non_executed_analysis_never_completes_runtime(
    status: str,
    quality_status: str,
) -> None:
    request = make_request()
    fake = ProviderFreeInternalAgent(
        make_result(
            make_analysis_payload(status, quality_status=quality_status),
            source="structured_business_data",
        )
    )
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    run = make_run(service, request)

    with pytest.raises(RuntimeNodeError, match="runtime ended with failed"):
        asyncio.run(service.run(request, run))

    _prepare_id, _execute_id, verify_id = service._current_node_ids(run)
    verification = run.nodes[verify_id].observation
    assert run.status == RuntimeRunStatus.FAILED
    assert run.nodes[verify_id].status == RuntimeNodeStatus.PARTIAL
    assert verification is not None
    assert verification.facts["passed"] is False
    assert verification.facts["analysis_status"] == status
    assert fake.calls == 1


def test_executed_analysis_passes_typed_runtime_verification() -> None:
    request = make_request()
    fake = ProviderFreeInternalAgent(
        make_result(make_analysis_payload("executed"), source="structured_payload")
    )
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    run = make_run(service, request)

    result = asyncio.run(service.run(request, run))

    _prepare_id, _execute_id, verify_id = service._current_node_ids(run)
    verification = run.nodes[verify_id].observation
    assert result.status == AgentResultStatus.COMPLETED
    assert run.status == RuntimeRunStatus.COMPLETED
    assert verification is not None
    assert verification.facts["passed"] is True
    assert verification.facts["analysis_status"] == "executed"
    assert verification.facts["analysis_result_valid"] is True
    assert fake.calls == 1


def test_needs_review_waits_for_review_instead_of_completing() -> None:
    request = make_request()
    fake = ProviderFreeInternalAgent(
        make_result(make_analysis_payload("needs_review"))
    )
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    run = make_run(service, request)

    with pytest.raises(RuntimeRunSuspended) as suspended:
        asyncio.run(service.run(request, run))

    assert suspended.value.status == RuntimeRunStatus.WAITING_APPROVAL
    assert run.status == RuntimeRunStatus.WAITING_APPROVAL
    _prepare_id, _execute_id, verify_id = service._current_node_ids(run)
    verification = run.nodes[verify_id].observation
    assert verification is not None
    assert verification.facts["passed"] is False
    assert verification.facts["requires_review"] is True
    assert fake.calls == 1


def test_invalid_analysis_payload_fails_closed() -> None:
    request = make_request()
    fake = ProviderFreeInternalAgent(
        make_result({"status": "executed", "rows": 2})
    )
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    run = make_run(service, request)

    with pytest.raises(RuntimeNodeError, match="runtime ended with failed"):
        asyncio.run(service.run(request, run))

    _prepare_id, _execute_id, verify_id = service._current_node_ids(run)
    assert run.status == RuntimeRunStatus.FAILED
    assert run.nodes[verify_id].error_code == "analysis_result_contract_invalid"


def test_missing_analysis_marker_fails_closed() -> None:
    request = make_request()
    payload = make_analysis_payload("executed")
    fake = ProviderFreeInternalAgent(
        AgentResult(
            status=AgentResultStatus.COMPLETED,
            agent_id=ResearchAnalysisRuntimeService.agent_id,
            provider="provider-free-fake",
            structured_result={"business_data": payload},
            business_data=payload,
        )
    )
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    run = make_run(service, request)

    with pytest.raises(RuntimeNodeError, match="runtime ended with failed"):
        asyncio.run(service.run(request, run))

    _prepare_id, _execute_id, verify_id = service._current_node_ids(run)
    assert run.status == RuntimeRunStatus.FAILED
    assert run.nodes[verify_id].error_code == "analysis_result_contract_invalid"
