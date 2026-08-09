from __future__ import annotations

import asyncio
import inspect

from app.contracts import AgentRequest, AgentResult, AgentResultStatus
from app.contracts.research_analysis import (
    ResearchAnalysisResult,
    ResearchDataQualityReport,
)
from app.runtime import (
    AgentRun,
    RuntimeCanaryEvidence,
    RuntimeCanarySuite,
    RuntimeNodeStatus,
    evaluate_runtime_canary_suite,
)
from app.services import research_analysis_runtime, task_runner
from app.services.research_analysis_runtime import ResearchAnalysisRuntimeService
from app.services.runtime_launch_policy import RuntimeLaunchMode, RuntimeLaunchPolicy

AGENT_ID = "RESEARCH_03_DATA_ANALYSIS_V1"


def _request(*, options: dict[str, object] | None = None) -> AgentRequest:
    return AgentRequest(
        task_id="research03-boundary-task",
        session_id="research03-boundary-session",
        user_id="research03-boundary-user",
        options=options or {},
    )


def _runtime_request() -> AgentRequest:
    return _request(
        options={
            "research_analysis_v2": {
                "execute": True,
                "request": {
                    "research_question": "Does the intervention change the outcome?",
                    "analysis_goal": "compare",
                    "design": "experimental_comparison",
                },
            }
        }
    )


class ProviderFreeInternalAgent:
    """A local fake: this test must never instantiate or call a real Provider."""

    def __init__(self) -> None:
        self.calls = 0

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: object = None,
    ) -> AgentResult:
        assert agent_id == AGENT_ID
        assert request.task_id == "research03-boundary-task"
        assert context is None
        self.calls += 1
        payload = ResearchAnalysisResult(
            status="executed",
            data_quality=ResearchDataQualityReport(status="passed"),
            design_assessment="provider-free runtime fixture",
        ).model_dump(mode="json")
        return AgentResult(
            status=AgentResultStatus.COMPLETED,
            agent_id=AGENT_ID,
            provider="local_analysis_fixture",
            answer="fixture analysis result",
            structured_result={"analysis_v2": True, "business_data": payload},
            business_data=payload,
        )


def test_research03_code_has_distinct_legacy_runtime_and_capability_edges() -> None:
    legacy_source = inspect.getsource(task_runner)
    runtime_source = inspect.getsource(research_analysis_runtime)

    # Structural evidence only: these names prove the current seams exist;
    # they do not prove production equivalence or release readiness.
    assert AGENT_ID in legacy_source
    assert "self.runtime_boundary.execute" in legacy_source
    assert "self.internal_agents.run" in legacy_source
    assert "self.provider.run" in legacy_source

    assert "self.internal_agents.run" in runtime_source
    assert "provider.run" not in runtime_source
    assert "AgentProvider" not in runtime_source


def test_research03_runtime_plan_owns_execution_and_verification_only() -> None:
    fake = ProviderFreeInternalAgent()
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]

    plan = service.build_plan(_runtime_request())

    assert plan.version == "research-v2"
    assert [node.node_id for node in plan.nodes] == [
        "analysis.execute",
        "analysis.verify",
    ]
    execute, verify = plan.nodes
    assert execute.node_type == "workflow"
    assert execute.handler_id == "research.analysis.execute"
    assert verify.node_type == "verification"
    assert verify.handler_id == "research.analysis.verify"
    assert verify.depends_on == [execute.node_id]
    assert plan.success_criteria == [
        "analysis_result_present",
        "analysis_result_passes_runtime_verification",
    ]


def test_research03_runtime_is_provider_free_at_the_runtime_seam() -> None:
    fake = ProviderFreeInternalAgent()
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]
    request = _runtime_request()
    run = AgentRun(
        run_id="research03-boundary-run",
        task_id=request.task_id,
        goal="research analysis",
        plan=service.build_plan(request),
    )

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.calls == 1
    assert run.status.value == "completed"
    assert all(
        node.status == RuntimeNodeStatus.SUCCEEDED for node in run.nodes.values()
    )


def test_research03_candidate_is_explicit_and_default_stays_legacy() -> None:
    service = ResearchAnalysisRuntimeService(
        ProviderFreeInternalAgent(), enabled=True  # type: ignore[arg-type]
    )
    assert service.supports(AGENT_ID, _request()) is False
    assert service.supports(AGENT_ID, _runtime_request()) is True
    assert ResearchAnalysisRuntimeService(
        ProviderFreeInternalAgent(), enabled=False  # type: ignore[arg-type]
    ).supports(AGENT_ID, _runtime_request()) is False

    policy = RuntimeLaunchPolicy()
    default_decision = policy.resolve(
        AGENT_ID,
        _request(),
        lifecycle_enabled=True,
        runtime_option_key="research_analysis_v2",
    )
    candidate_decision = policy.resolve(
        AGENT_ID,
        _runtime_request(),
        lifecycle_enabled=True,
        runtime_option_key="research_analysis_v2",
    )
    assert default_decision.mode == RuntimeLaunchMode.LEGACY
    assert candidate_decision.mode == RuntimeLaunchMode.CANARY


def test_synthetic_fixture_is_not_release_evidence() -> None:
    evidence = RuntimeCanaryEvidence(kind="synthetic", agent_id=AGENT_ID)
    report = evaluate_runtime_canary_suite(
        RuntimeCanarySuite(suite_id="research03-boundary-fixture", evidence=evidence)
    )

    assert evidence.release_ready is False
    assert report.release_eligible is False
