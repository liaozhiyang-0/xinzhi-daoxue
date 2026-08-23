"""Small, redacted audit envelope shared by Task and Runtime boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.contracts import AgentRequest, AgentResult, RouteDecision
from app.runtime.semantic_evidence import payload_sha256

TASK_AUDIT_SCHEMA_VERSION = "task_audit.v1"
SCENARIO_OUTPUT_CONTRACT_VERSION = "scenario_output_contract.v1"


def _normalized_runtime_request(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    payload = dict(value)
    manifest = payload.get("data_manifest")
    if isinstance(manifest, Mapping):
        normalized_manifest = dict(manifest)
        dataset_id = str(normalized_manifest.get("dataset_id", "")).strip()
        if dataset_id:
            normalized_manifest["source_ref"] = f"dataset:{dataset_id}"
        else:
            normalized_manifest.pop("source_ref", None)
        payload["data_manifest"] = normalized_manifest
    return payload


def runtime_request_sha256(options: Mapping[str, Any]) -> str:
    """Hash model-facing request payloads without mode/control metadata."""

    requests = [
        _normalized_runtime_request(value.get("request"))
        for value in options.values()
        if isinstance(value, Mapping) and isinstance(value.get("request"), Mapping)
    ]
    if not requests:
        return ""
    payload: object = requests[0] if len(requests) == 1 else requests
    return payload_sha256(payload)


def build_task_audit(
    request: AgentRequest,
    route: RouteDecision,
    *,
    canonical_input: Mapping[str, Any],
) -> dict[str, Any]:
    """Build bounded metadata that joins input, route, Runtime, and output."""

    attachment_payload = [
        {
            "file_id": item.file_id,
            "checksum_sha256": item.checksum_sha256 or "",
            "content_type": item.content_type,
            "size_bytes": item.size_bytes,
        }
        for item in request.attachments
    ]
    scenario_id = request.scenario_id or str(
        request.options.get("scenario_id", "")
    ).strip()
    scenario_version = str(
        request.options.get("scenario_version", "")
    ).strip()
    return {
        "schema_version": TASK_AUDIT_SCHEMA_VERSION,
        "request_id": str(request.options.get("request_id", "")).strip()
        or request.task_id,
        "task_id": request.task_id,
        "session_id": request.session_id,
        "scenario_id": scenario_id,
        "scenario_version": scenario_version,
        "run_batch_id": str(request.options.get("run_batch_id", "")).strip(),
        "input_sha256": payload_sha256(dict(canonical_input)),
        "attachment_sha256": payload_sha256(attachment_payload),
        "runtime_request_sha256": runtime_request_sha256(request.options),
        "course_id": request.course_id,
        "intent": request.intent.value,
        "agent_id": route.agent_id,
        "route_source": route.route_source,
        "route_revision": route.route_revision,
        "runtime_run_id": "",
        "evidence_ids": [],
        "artifact_ids": [],
        "output_contract_version": (
            SCENARIO_OUTPUT_CONTRACT_VERSION if scenario_id else ""
        ),
        "terminal_status": "",
        "failure_category": "",
    }


def audit_from_request(request: AgentRequest) -> dict[str, Any]:
    """Read an existing audit envelope without exposing unrelated options."""

    return audit_from_request_snapshot(request.model_dump(mode="json"))


def audit_from_request_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    options = snapshot.get("options")
    if not isinstance(options, Mapping):
        return {}
    audit = options.get("_audit")
    return dict(audit) if isinstance(audit, Mapping) else {}


def audit_from_task_input(input_content: Mapping[str, Any]) -> dict[str, Any]:
    return audit_from_request_snapshot(input_content)


def replace_task_audit(
    input_content: Mapping[str, Any], audit: Mapping[str, Any]
) -> dict[str, Any]:
    payload = dict(input_content)
    options = dict(payload.get("options") or {})
    options["_audit"] = dict(audit)
    payload["options"] = options
    return payload


def with_runtime_run_id(
    input_content: Mapping[str, Any], runtime_run_id: str
) -> dict[str, Any]:
    audit = audit_from_task_input(input_content)
    if not audit:
        return dict(input_content)
    audit["runtime_run_id"] = runtime_run_id
    return replace_task_audit(input_content, audit)


def audit_for_terminal(
    audit: Mapping[str, Any], status: str, failure_category: str = ""
) -> dict[str, Any]:
    result = dict(audit)
    result["terminal_status"] = status
    result["failure_category"] = failure_category
    return result


def terminal_event_data(
    *,
    status: str,
    failure_category: str,
    error_code: str,
    error_message: str,
    runtime_run_id: str = "",
    reason: str = "",
) -> dict[str, Any]:
    """Build a replayable, bounded payload for terminal task events."""

    bounded_status = str(status).strip()[:64]
    bounded_category = str(failure_category).strip()[:128]
    bounded_code = str(error_code).strip()[:128]
    bounded_message = str(error_message).strip()[:2_000]
    bounded_run_id = str(runtime_run_id).strip()[:128]
    bounded_reason = str(reason).strip()[:2_000]
    return {
        "terminal_status": bounded_status,
        "failure_category": bounded_category,
        "error_code": bounded_code,
        "error_message": bounded_message,
        "runtime_run_id": bounded_run_id,
        **({"reason": bounded_reason} if bounded_reason else {}),
    }


def _add_ids(target: set[str], values: object) -> None:
    if isinstance(values, list):
        target.update(
            str(value).strip() for value in values if str(value).strip()
        )


def evidence_ids_from_result(
    result: AgentResult, runtime_run: Any | None = None
) -> list[str]:
    values: set[str] = {
        str(value).strip()
        for value in result.citations
        if str(value).strip()
    }
    structured = result.structured_result
    for key in (
        "verified_evidence_ids",
        "evidence_ids",
        "runtime_retrieval_evidence_ids",
    ):
        _add_ids(values, structured.get(key))
    packet = structured.get("evidence_packet")
    if isinstance(packet, Mapping):
        sources = packet.get("sources")
        if isinstance(sources, list):
            for source in sources:
                if isinstance(source, Mapping):
                    source_id = str(source.get("source_id", "")).strip()
                    if source_id:
                        values.add(source_id)
    if runtime_run is not None:
        for observation in getattr(runtime_run, "observations", []):
            _add_ids(values, getattr(observation, "evidence_ids", []))
        for node in getattr(runtime_run, "nodes", {}).values():
            observation = getattr(node, "observation", None)
            if observation is not None:
                _add_ids(values, getattr(observation, "evidence_ids", []))
    return sorted(values)[:100]


def artifact_ids_from_result(
    result: AgentResult, runtime_run: Any | None = None
) -> list[str]:
    values = {
        item.artifact_id.strip()
        for item in result.artifacts
        if item.artifact_id.strip()
    }
    if runtime_run is not None:
        for observation in getattr(runtime_run, "observations", []):
            _add_ids(values, getattr(observation, "artifact_ids", []))
        for node in getattr(runtime_run, "nodes", {}).values():
            observation = getattr(node, "observation", None)
            if observation is not None:
                _add_ids(values, getattr(observation, "artifact_ids", []))
    return sorted(values)[:100]


def audit_for_result(
    request: AgentRequest,
    result: AgentResult,
    *,
    runtime_run_id: str = "",
    runtime_run: Any | None = None,
) -> dict[str, Any]:
    audit = audit_from_request(request)
    if not audit:
        return {}
    audit["runtime_run_id"] = runtime_run_id or audit.get("runtime_run_id", "")
    audit["evidence_ids"] = evidence_ids_from_result(result, runtime_run)
    audit["artifact_ids"] = artifact_ids_from_result(result, runtime_run)
    if audit.get("scenario_id"):
        audit["output_contract_version"] = SCENARIO_OUTPUT_CONTRACT_VERSION
    return audit_for_terminal(audit, result.status.value)
