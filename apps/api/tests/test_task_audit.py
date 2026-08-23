from types import SimpleNamespace

from app.contracts import (
    AgentRequest,
    AgentResult,
    AttachmentRef,
    Intent,
    RouteDecision,
    RouteStatus,
)
from app.services.task_audit import (
    SCENARIO_OUTPUT_CONTRACT_VERSION,
    TASK_AUDIT_SCHEMA_VERSION,
    audit_for_result,
    build_task_audit,
    terminal_event_data,
    with_runtime_run_id,
)


def _route() -> RouteDecision:
    return RouteDecision(
        agent_id="GENERAL_QUESTION_V1",
        scene="solving",
        course_id="CT",
        intent=Intent.SOLVE_PROBLEM.value,
        route_status=RouteStatus.SELECTED,
        reason="test",
        retrieval_required=False,
        provider_required=False,
        route_revision=2,
    )


def _request() -> AgentRequest:
    return AgentRequest(
        task_id="task-audit-test",
        session_id="session-audit-test",
        user_id="user-audit-test",
        intent=Intent.SOLVE_PROBLEM,
        scenario_id="G2-05",
        canonical_input={"text": "请解释这个问题"},
        attachments=[
            AttachmentRef(
                file_id="file-1",
                filename="input.png",
                content_type="image/png",
                size_bytes=12,
                storage_key="storage/file-1",
                checksum_sha256="a" * 64,
            )
        ],
        options={
            "request_id": "request-audit-test",
            "run_batch_id": "feedback-replay-2026-08-20",
            "scenario_version": "1",
        },
    )


def test_task_audit_binds_request_and_attachment_metadata() -> None:
    request = _request()
    audit = build_task_audit(request, _route(), canonical_input=request.canonical_input)

    assert audit["schema_version"] == TASK_AUDIT_SCHEMA_VERSION
    assert audit["request_id"] == "request-audit-test"
    assert audit["run_batch_id"] == "feedback-replay-2026-08-20"
    assert audit["scenario_id"] == "G2-05"
    assert audit["output_contract_version"] == SCENARIO_OUTPUT_CONTRACT_VERSION
    assert len(audit["input_sha256"]) == 64
    assert len(audit["attachment_sha256"]) == 64
    assert audit["runtime_request_sha256"] == ""


def test_task_audit_binds_runtime_request_without_upload_identity() -> None:
    request = _request().model_copy(
        update={
            "options": {
                "research_analysis_v2": {
                    "execute": True,
                    "request": {
                        "research_question": "Compare synthetic groups",
                        "data_manifest": {
                            "dataset_id": "synthetic-v1",
                            "source_ref": "attachment:upload-id",
                        },
                    },
                }
            }
        }
    )

    audit = build_task_audit(request, _route(), canonical_input=request.canonical_input)

    assert len(audit["runtime_request_sha256"]) == 64


def test_task_audit_keeps_runtime_and_evidence_lineage() -> None:
    request = _request().model_copy(
        update={
            "options": {
                "_audit": build_task_audit(
                    _request(), _route(), canonical_input=_request().canonical_input
                )
            }
        }
    )
    result = AgentResult(
        agent_id="GENERAL_QUESTION_V1",
        provider="mock",
        citations=["citation-0"],
        structured_result={
            "verified_evidence_ids": ["evidence-1"],
            "evidence_packet": {"sources": [{"source_id": "source-2"}]},
        },
    )

    runtime_run = SimpleNamespace(
        observations=[
            SimpleNamespace(
                evidence_ids=["runtime-evidence-1"],
                artifact_ids=["runtime-artifact-1"],
            )
        ],
        nodes={
            "verify": SimpleNamespace(
                observation=SimpleNamespace(
                    evidence_ids=["node-evidence-2"],
                    artifact_ids=["node-artifact-2"],
                )
            )
        },
    )

    audit = audit_for_result(
        request,
        result,
        runtime_run_id="run-audit-test",
        runtime_run=runtime_run,
    )

    assert audit["runtime_run_id"] == "run-audit-test"
    assert audit["evidence_ids"] == [
        "citation-0",
        "evidence-1",
        "node-evidence-2",
        "runtime-evidence-1",
        "source-2",
    ]
    assert audit["artifact_ids"] == [
        "node-artifact-2",
        "runtime-artifact-1",
    ]
    assert audit["terminal_status"] == "completed"


def test_task_audit_runtime_id_update_does_not_mutate_original_payload() -> None:
    request = _request()
    audit = build_task_audit(request, _route(), canonical_input=request.canonical_input)
    payload = request.model_dump(mode="json")
    payload["options"]["_audit"] = audit

    updated = with_runtime_run_id(payload, "run-1")

    assert payload["options"]["_audit"]["runtime_run_id"] == ""
    assert updated["options"]["_audit"]["runtime_run_id"] == "run-1"


def test_terminal_event_data_is_replayable_without_task_row() -> None:
    event_data = terminal_event_data(
        status="failed",
        failure_category="provider_timeout",
        error_code="provider_timeout",
        error_message="模型服务暂时不可用，请稍后重试。",
        runtime_run_id="run-terminal-event",
    )

    assert event_data == {
        "terminal_status": "failed",
        "failure_category": "provider_timeout",
        "error_code": "provider_timeout",
        "error_message": "模型服务暂时不可用，请稍后重试。",
        "runtime_run_id": "run-terminal-event",
    }
