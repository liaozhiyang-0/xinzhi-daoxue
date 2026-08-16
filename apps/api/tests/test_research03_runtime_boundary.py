from __future__ import annotations

import asyncio
import inspect

from app.contracts import AgentRequest, AgentResult, AgentResultStatus
from app.contracts.research_analysis import (
    ResearchAnalysisRequest,
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
from app.services import research_analysis_runtime, runtime_task_engine
from app.services.research_analysis_runtime import ResearchAnalysisRuntimeService
from app.services.runtime_launch_policy import RuntimeLaunchMode, RuntimeLaunchPolicy

AGENT_ID = "RESEARCH_03_DATA_ANALYSIS_V1"
PREPARE_NODE_ID = "analysis.prepare"
EXECUTE_NODE_ID = "analysis.execute"
VERIFY_NODE_ID = "analysis.verify"


def _expected_prepared_control_data(request: AgentRequest) -> dict[str, object]:
    options = request.options["research_analysis_v2"]
    assert isinstance(options, dict)
    payload = ResearchAnalysisRequest.model_validate(
        options["request"]
    ).model_dump(mode="json")
    manifest = payload["data_manifest"]
    assert isinstance(manifest, dict)
    return {
        "research_analysis_prepared": {
            "schema_version": "research-analysis-prepared-v1",
            "payload": payload,
            "execution_mode": "local",
            "execution_options": {"execute": True},
            "authorization_manifest_ref": {
                "present": True,
                "dataset_id": manifest["dataset_id"],
                "version": manifest["version"],
                "format": manifest["format"],
                "checksum_sha256": manifest["checksum_sha256"],
                "authorized": manifest["authorized"],
                "contains_sensitive_data": manifest["contains_sensitive_data"],
            },
        }
    }


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
                "execution_mode": "local",
                "request": {
                    "research_question": "Does the intervention change the outcome?",
                    "analysis_goal": "compare",
                    "design": "experimental_comparison",
                    "data_manifest": {
                        "dataset_id": "research03-boundary-fixture",
                        "version": "v1",
                        "format": "csv",
                        "checksum_sha256": "a" * 64,
                        "row_count": 2,
                        "column_count": 3,
                        "authorized": True,
                        "source_ref": "attachment:research03-boundary",
                    },
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


def test_research03_code_has_distinct_runtime_and_capability_edges() -> None:
    task_engine_source = inspect.getsource(runtime_task_engine)
    runtime_source = inspect.getsource(research_analysis_runtime)

    assert "TaskRuntimeLifecycle" in task_engine_source
    assert "self.runtime_execution.execute" in task_engine_source

    assert "self.internal_agents.run" in runtime_source
    assert "provider.run" not in runtime_source
    assert "AgentProvider" not in runtime_source


def test_research03_runtime_plan_has_prepare_execute_verify_contract() -> None:
    fake = ProviderFreeInternalAgent()
    service = ResearchAnalysisRuntimeService(fake, enabled=True)  # type: ignore[arg-type]

    plan = service.build_plan(_runtime_request())

    assert plan.version == "research-v2"
    assert [node.node_id for node in plan.nodes] == [
        PREPARE_NODE_ID,
        EXECUTE_NODE_ID,
        VERIFY_NODE_ID,
    ]
    prepare, execute, verify = plan.nodes
    assert prepare.handler_id == "research.analysis.prepare"
    assert execute.handler_id == "research.analysis.execute"
    assert verify.node_type == "verification"
    assert verify.handler_id == "research.analysis.verify"
    assert prepare.node_type == "control"
    assert execute.depends_on == [prepare.node_id]
    assert verify.depends_on == [execute.node_id]
    assert plan.success_criteria == [
        "analysis_request_prepared",
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
    completed_prepare_without_agent_call = False

    def event(event_name: str, _run: AgentRun, node_id: str) -> None:
        nonlocal completed_prepare_without_agent_call
        if event_name == "node_completed" and node_id == PREPARE_NODE_ID:
            completed_prepare_without_agent_call = True
            assert fake.calls == 0

    result = asyncio.run(service.run(request, run, event_hook=event))

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.calls == 1
    assert run.status.value == "completed"
    assert completed_prepare_without_agent_call is True
    assert run.nodes[PREPARE_NODE_ID].status == RuntimeNodeStatus.SUCCEEDED
    assert run.control_data == _expected_prepared_control_data(request)
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
    assert default_decision.mode == RuntimeLaunchMode.DEFAULT
    assert candidate_decision.mode == RuntimeLaunchMode.DEFAULT


def test_synthetic_fixture_is_not_release_evidence() -> None:
    evidence = RuntimeCanaryEvidence(kind="synthetic", agent_id=AGENT_ID)
    report = evaluate_runtime_canary_suite(
        RuntimeCanarySuite(suite_id="research03-boundary-fixture", evidence=evidence)
    )

    assert evidence.release_ready is False
    assert report.release_eligible is False
