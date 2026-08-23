"""Capture small, authorized Runtime development E2E pairs.

This runner intentionally exercises the public Task API rather than importing
internal execution services.  It is for a controlled development environment
only. The chosen test cases contain no student data, and all artifacts are
written to an ignored directory supplied by the operator. It never changes launch modes,
release evidence, or provider configuration.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlsplit, urlunsplit

RunMode = Literal["legacy", "runtime"]
PairOrder = Literal["legacy-first", "runtime-first", "alternate"]
PAIRED_INPUT_SCHEMA_VERSION = "runtime_paired_input.v1"
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
MAX_AUTO_APPROVALS = 3
SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "raw_prompt",
    "secret",
    "token",
    "uid",
}


@dataclass(frozen=True, slots=True)
class E2ECase:
    case_id: str
    agent_id: str
    runtime_option_key: str
    course_id: str
    intent: str
    question: str
    runtime_request: dict[str, Any] | None = None
    dataset_csv: str | None = None


CASES: tuple[E2ECase, ...] = (
    E2ECase(
        case_id="general_stack_explanation",
        agent_id="GENERAL_QUESTION_V1",
        runtime_option_key="general_question_runtime",
        course_id="UNKNOWN",
        intent="general_qa",
        question="请用两句话解释数据结构中的栈，不需要引用外部资料。",
    ),
    E2ECase(
        case_id="knowledge_capacitor_voltage",
        agent_id="LEARN_01_LOCAL_RETRIEVAL_V1",
        runtime_option_key="knowledge_qa_runtime",
        course_id="CT",
        intent="explain_concept",
        question="为什么电容两端电压不能突变？请简要说明物理原因。",
    ),
    E2ECase(
        case_id="solver_series_current",
        agent_id="ACADEMIC_PROBLEM_SOLVER",
        runtime_option_key="academic_solver_runtime",
        course_id="CT",
        intent="solve_problem",
        question="一个 10V 理想电压源串联 5Ω 电阻，求回路电流并写出单位。",
    ),
    E2ECase(
        case_id="research_reproducible_evals",
        agent_id="RESEARCH_01_ACADEMIC_SEARCH_V1",
        runtime_option_key="external_research_runtime",
        course_id="UNKNOWN",
        intent="academic_search",
        question=(
            "检索并简要说明一项关于 AI Agent 可复现评测的公开研究；"
            "给出来源，并明确不确定性。"
        ),
    ),
    E2ECase(
        case_id="lesson_prep_runtime_handoff",
        agent_id="TEACH_01_LESSON_PREP_V1",
        runtime_option_key="lesson_prep_runtime",
        course_id="CT",
        intent="lesson_prep",
        question=(
            "请为电路理论中的基尔霍夫定律设计一节脱敏的课堂活动，"
            "包含学习目标、形成性评价和教师复核点。"
        ),
    ),
    E2ECase(
        case_id="assignment_review_runtime_handoff",
        agent_id="TEACH_02_ASSIGNMENT_REVIEW_V1",
        runtime_option_key="assignment_review_runtime",
        course_id="CT",
        intent="assignment_review",
        question=(
            "题目：一个10 V电压源串联5欧姆电阻，求电流。"
            "学生答案：2 A。请按步骤诊断并给教师反馈，不要自动定分。"
        ),
    ),
    E2ECase(
        case_id="academic_writing_runtime_handoff",
        agent_id="RESEARCH_02_ACADEMIC_WRITING_V1",
        runtime_option_key="academic_writing_runtime",
        course_id="CT",
        intent="academic_writing",
        question=(
            "请根据一个关于电路理论实验教学的脱敏研究问题，"
            "给出论文提纲、待核实的论断和引用检查清单。"
        ),
    ),
    E2ECase(
        case_id="research_data_analysis_runtime_handoff",
        agent_id="RESEARCH_03_DATA_ANALYSIS_V1",
        runtime_option_key="research_analysis_v2",
        course_id="CT",
        intent="data_analysis",
        question="Compare two synthetic groups and report the estimated effect.",
        runtime_request={
            "research_question": (
                "Compare two synthetic groups and report the estimated effect."
            ),
            "analysis_goal": "estimate_effect",
            "design": "experimental_comparison",
            "estimand": "group A minus group B mean outcome",
            "unit_of_analysis": "one row per participant",
            "variables": [
                {
                    "name": "participant",
                    "role": "identifier",
                    "dtype": "string",
                },
                {
                    "name": "group",
                    "role": "treatment",
                    "dtype": "string",
                    "allowed_values": ["A", "B"],
                },
                {
                    "name": "outcome",
                    "role": "outcome",
                    "dtype": "numeric",
                },
            ],
            "exploratory": True,
        },
        dataset_csv=(
            "participant,group,outcome\n"
            "p1,A,10\n"
            "p2,A,12\n"
            "p3,B,7\n"
            "p4,B,8\n"
        ),
    ),
    E2ECase(
        case_id="research_data_analysis_executable_runtime",
        agent_id="RESEARCH_03_DATA_ANALYSIS_V1",
        runtime_option_key="research_analysis_v2",
        course_id="CT",
        intent="data_analysis",
        question="Compare two synthetic groups and report the estimated effect.",
        runtime_request={
            "research_question": (
                "Compare two synthetic groups and report the estimated effect."
            ),
            "analysis_goal": "estimate_effect",
            "design": "experimental_comparison",
            "estimand": "group A minus group B mean outcome",
            "unit_of_analysis": "one row per participant",
            "variables": [
                {
                    "name": "participant",
                    "role": "identifier",
                    "dtype": "string",
                },
                {
                    "name": "group",
                    "role": "treatment",
                    "dtype": "string",
                    "allowed_values": ["A", "B"],
                },
                {
                    "name": "outcome",
                    "role": "outcome",
                    "dtype": "numeric",
                },
            ],
            "exploratory": True,
        },
        dataset_csv=(
            "participant,group,outcome\n"
            + "".join(
                f"a{index},A,{10 + (index % 5)}\n"
                f"b{index},B,{7 + (index % 5)}\n"
                for index in range(1, 13)
            )
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8031/api/v1")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Ignored, controlled directory for redacted development evidence.",
    )
    parser.add_argument("--user-id", default="runtime-authorized-dev-e2e")
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument(
        "--mode",
        choices=("legacy", "runtime", "both"),
        default="both",
        help=(
            "Runtime mode requires an isolated service configured for canary execution."
        ),
    )
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument(
        "--repeat-count",
        type=int,
        default=1,
        help="Number of Legacy/Runtime pairs per selected case (1-20).",
    )
    parser.add_argument(
        "--pair-order",
        choices=("legacy-first", "runtime-first", "alternate"),
        default="alternate",
        help="Order the two modes within each pair to expose order effects.",
    )
    parser.add_argument(
        "--auto-approve-dev",
        action="store_true",
        help=(
            "development-only: approve Runtime waiting_approval checkpoints "
            "and record each approval in the private report"
        ),
    )
    return parser.parse_args()


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.casefold() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(redact(value), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def selected_cases(requested: list[str]) -> tuple[E2ECase, ...]:
    wanted = set(requested)
    available = {case.case_id for case in CASES}
    unknown = wanted - available
    if unknown:
        raise ValueError(f"unknown case IDs: {', '.join(sorted(unknown))}")
    return tuple(case for case in CASES if not wanted or case.case_id in wanted)


def api_root(base_url: str) -> str:
    """Normalize a host URL or an explicit ``/api/v1`` root."""

    value = base_url.strip().rstrip("/")
    if not value:
        raise ValueError("base URL must not be empty")
    parsed = urlsplit(value)
    path = parsed.path.rstrip("/")
    if not path:
        path = "/api/v1"
    elif path != "/api/v1" and not path.endswith("/api/v1"):
        path = f"{path}/api/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def pair_modes(
    mode: str, pair_order: PairOrder, sample_index: int
) -> tuple[RunMode, ...]:
    """Return one repeat's execution order without changing request content."""

    if mode == "legacy":
        return ("legacy",)
    if mode == "runtime":
        return ("runtime",)
    runtime_first = pair_order == "runtime-first" or (
        pair_order == "alternate" and sample_index % 2 == 1
    )
    return ("runtime", "legacy") if runtime_first else ("legacy", "runtime")


def make_session(
    client: Any,
    base_url: str,
    user_id: str,
    case: E2ECase,
    mode: RunMode,
    sample_id: str,
) -> str:
    response = client.post(
        f"{base_url}/sessions",
        json={
            "user_id": user_id,
            "course_id": case.course_id,
            "title": f"authorized-e2e:{case.case_id}:{sample_id}:{mode}",
        },
    )
    response.raise_for_status()
    return str(response.json()["id"])


def create_task(
    client: Any,
    base_url: str,
    user_id: str,
    session_id: str,
    case: E2ECase,
    mode: RunMode,
    attachments: list[dict[str, Any]] | None = None,
    runtime_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options: dict[str, Any] = {"debug_agent_id": case.agent_id}
    # ``*_runtime`` options use execute=False as a legacy opt-out.  The
    # RESEARCH_03 business option is different: its presence is the explicit
    # V2 candidate request, so Legacy pairs must omit it entirely.
    if mode == "runtime" or case.runtime_option_key.endswith("_runtime"):
        runtime_options: dict[str, Any] = {"execute": mode == "runtime"}
        request_payload = runtime_request or case.runtime_request
        if request_payload is not None:
            runtime_options["request"] = request_payload
        options[case.runtime_option_key] = runtime_options
    response = client.post(
        f"{base_url}/tasks",
        json={
            "session_id": session_id,
            "user_id": user_id,
            "user_role": "admin",
            "course_id": case.course_id,
            "intent": case.intent,
            "canonical_input": {"question": case.question},
            "attachments": attachments or [],
            "options": options,
        },
    )
    response.raise_for_status()
    return cast(dict[str, Any], response.json())


def pending_plan_proposal(
    client: Any,
    base_url: str,
    task_id: str,
    runtime_run_id: str,
) -> dict[str, Any] | None:
    """Return the newest pending plan proposal for the controlled Runtime."""

    response = client.get(f"{base_url}/tasks/{task_id}/runtime-plan-proposals")
    response.raise_for_status()
    proposals = response.json()
    if not isinstance(proposals, list):
        return None
    pending = [
        item
        for item in proposals
        if isinstance(item, dict)
        and item.get("status") == "pending"
        and item.get("run_id") == runtime_run_id
    ]
    return max(
        pending,
        key=lambda item: int(item.get("state_version") or 0),
        default=None,
    )


def await_task(
    client: Any,
    base_url: str,
    task_id: str,
    user_id: str,
    *,
    poll_interval: float,
    timeout_seconds: float,
    auto_approve_dev: bool = False,
) -> tuple[dict[str, Any], int, list[dict[str, Any]]]:
    started = time.monotonic()
    latest: dict[str, Any] = {}
    control_actions: list[dict[str, Any]] = []
    while time.monotonic() - started < timeout_seconds:
        response = client.get(
            f"{base_url}/tasks/{task_id}", params={"user_id": user_id}
        )
        response.raise_for_status()
        latest = response.json()
        if str(latest.get("status", "")).casefold() in TERMINAL_STATUSES:
            return (
                latest,
                round((time.monotonic() - started) * 1000),
                control_actions,
            )
        if auto_approve_dev:
            controls_response = client.get(
                f"{base_url}/tasks/{task_id}/runtime-controls",
                params={"user_id": user_id},
            )
            controls_response.raise_for_status()
            projection = controls_response.json()
            runtime_run_id = str(projection.get("runtime_run_id") or "")
            proposal = (
                pending_plan_proposal(client, base_url, task_id, runtime_run_id)
                if projection.get("status") == "waiting_approval"
                and runtime_run_id
                else None
            )
            approval_attempt_count = sum(
                1
                for action in control_actions
                if action.get("action") in {
                    "approve",
                    "approve_conflict",
                    "approve_plan_proposal",
                    "approve_plan_proposal_conflict",
                }
            )
            approve_available = any(
                item.get("action") == "approve" and item.get("available")
                for item in projection.get("controls", [])
                if isinstance(item, dict)
            )
            if (
                projection.get("status") == "waiting_approval"
                and runtime_run_id
                and (approve_available or proposal is not None)
                and approval_attempt_count < MAX_AUTO_APPROVALS
            ):
                proposal_decision = proposal is not None
                proposal_id = (
                    str(proposal["proposal_id"])
                    if proposal_decision and proposal
                    else None
                )
                expected_state_version = (
                    proposal["state_version"]
                    if proposal_decision and proposal
                    else projection.get("state_version")
                )
                approval = client.post(
                    (
                        f"{base_url}/tasks/{task_id}/runtime-plan-proposals/"
                        f"{proposal_id}/decision"
                        if proposal_decision
                        else f"{base_url}/tasks/{task_id}/approve"
                    ),
                    params=(
                        {}
                        if proposal_decision
                        else {"runtime_run_id": runtime_run_id}
                    ),
                    json=(
                        {
                            "decision": "approved",
                            "reason": "authorized development E2E control test",
                            "expected_state_version": expected_state_version,
                        }
                        if proposal_decision
                        else {
                            "decision": "approved",
                            "reason": "authorized development E2E control test",
                            "expected_state_version": projection.get(
                                "state_version"
                            ),
                        }
                    ),
                )
                if approval.status_code == 409:
                    # The worker can advance the checkpoint between the
                    # projection read and this optimistic-concurrency write.
                    # Re-read on the next poll instead of treating that race
                    # as a failed E2E run.
                    control_actions.append(
                        {
                            "action": (
                                "approve_plan_proposal_conflict"
                                if proposal_decision
                                else "approve_conflict"
                            ),
                            "runtime_run_id": runtime_run_id,
                            "proposal_id": proposal_id,
                            "state_version": expected_state_version,
                            "actor": "anonymous_development_test",
                        }
                    )
                else:
                    approval.raise_for_status()
                    control_actions.append(
                        {
                            "action": (
                                "approve_plan_proposal"
                                if proposal_decision
                                else "approve"
                            ),
                            "runtime_run_id": runtime_run_id,
                            "proposal_id": proposal_id,
                            "state_version": expected_state_version,
                            "actor": "anonymous_development_test",
                        }
                    )
            elif (
                projection.get("status") == "waiting_approval"
                and approval_attempt_count >= MAX_AUTO_APPROVALS
                and not any(
                    action.get("action") == "approval_budget_exhausted"
                    for action in control_actions
                )
            ):
                control_actions.append(
                    {
                        "action": "approval_budget_exhausted",
                        "runtime_run_id": projection.get("runtime_run_id"),
                        "state_version": projection.get("state_version"),
                        "actor": "anonymous_development_test",
                        "max_auto_approval_attempts": MAX_AUTO_APPROVALS,
                    }
                )
        time.sleep(poll_interval)
    return (
        {**latest, "status": "timeout", "timeout_seconds": timeout_seconds},
        round((time.monotonic() - started) * 1000),
        control_actions,
    )


def task_events(client: Any, base_url: str, task_id: str) -> list[dict[str, Any]]:
    response = client.get(f"{base_url}/tasks/{task_id}/events", params={"after": 0})
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else []


def execution_projection(client: Any, base_url: str, task_id: str) -> dict[str, Any]:
    response = client.get(f"{base_url}/debug/execution/{task_id}")
    if response.status_code == 404:
        return {"available": False, "status_code": 404}
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {"available": False}


def event_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    sequences: list[int] = [
        int(item["sequence"])
        for item in events
        if isinstance(item.get("sequence"), int)
    ]
    return {
        "count": len(events),
        "strictly_increasing": all(
            sequences[index] < sequences[index + 1]
            for index in range(len(sequences) - 1)
        ),
        "first_sequence": sequences[0] if sequences else None,
        "last_sequence": sequences[-1] if sequences else None,
        "types": [str(item.get("type", item.get("event_type", ""))) for item in events],
    }


def _task_lifecycle_elapsed_ms(task: dict[str, Any]) -> int | None:
    started_at = task.get("started_at")
    completed_at = task.get("completed_at")
    if not isinstance(started_at, str) or not isinstance(completed_at, str):
        return None
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, round((completed - started).total_seconds() * 1000))


_DIAGNOSTIC_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")


def _safe_diagnostic_identifier(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    return candidate if _DIAGNOSTIC_IDENTIFIER.fullmatch(candidate) else None


def runtime_failure_diagnostics(execution: dict[str, Any]) -> dict[str, Any]:
    """Summarize safe Runtime failure/proposal signals for E2E triage.

    The public debug projection intentionally omits provider prompts and raw
    exception messages.  Stable error codes, node IDs, and bounded proposal
    reason codes are sufficient to distinguish a Provider/child failure from
    an approval or quality-gate decision without copying sensitive payloads
    into the private report.
    """

    runtime = execution.get("runtime", {})
    if not isinstance(runtime, dict):
        return {
            "failure_codes": [],
            "unresolved_failure_codes": [],
            "recovered_failure_codes": [],
            "failed_node_ids": [],
            "plan_proposal_count": 0,
            "plan_proposal_reason_codes": [],
        }

    failure_codes: set[str] = set()
    failed_node_ids: set[str] = set()
    raw_nodes = runtime.get("nodes", [])
    nodes = raw_nodes if isinstance(raw_nodes, list) else []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        status = str(node.get("status", "")).casefold()
        code = _safe_diagnostic_identifier(node.get("error_code"))
        node_id = _safe_diagnostic_identifier(node.get("node_id"))
        if code and status in {"failed", "blocked", "partial"}:
            failure_codes.add(code)
        if node_id and status in {"failed", "blocked"}:
            failed_node_ids.add(node_id)

    proposal_count = 0
    proposal_reason_codes: set[str] = set()
    events = execution.get("events", [])
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            envelope = event.get("data")
            if not isinstance(envelope, dict):
                continue
            data = envelope.get("data")
            if not isinstance(data, dict):
                continue
            code = _safe_diagnostic_identifier(data.get("error_code"))
            if code and str(data.get("status", "")).casefold() in {
                "failed",
                "blocked",
                "partial",
            }:
                failure_codes.add(code)
            if data.get("stage_id") != "runtime_plan_proposal":
                continue
            proposal_count += 1
            reasons = data.get("reason_codes", [])
            if isinstance(reasons, list):
                for reason in reasons:
                    safe_reason = _safe_diagnostic_identifier(reason)
                    if safe_reason:
                        proposal_reason_codes.add(safe_reason)

    runtime_status = str(runtime.get("status", "")).casefold()
    unresolved_failure_codes = (
        set(failure_codes)
        if runtime_status != "completed"
        else {
            _safe_diagnostic_identifier(node.get("error_code"))
            for node in nodes
            if isinstance(node, dict)
            and str(node.get("status", "")).casefold()
            in {"failed", "blocked", "partial"}
            and _safe_diagnostic_identifier(node.get("error_code"))
        }
    )
    unresolved_failure_codes.discard(None)
    recovered_failure_codes = failure_codes - {
        code for code in unresolved_failure_codes if isinstance(code, str)
    }
    return {
        "failure_codes": sorted(failure_codes),
        "unresolved_failure_codes": sorted(
            code for code in unresolved_failure_codes if isinstance(code, str)
        ),
        "recovered_failure_codes": sorted(recovered_failure_codes),
        "failed_node_ids": sorted(failed_node_ids),
        "plan_proposal_count": proposal_count,
        "plan_proposal_reason_codes": sorted(proposal_reason_codes),
    }


def result_summary(
    task: dict[str, Any], execution: dict[str, Any], *, observed_wait_ms: int
) -> dict[str, Any]:
    result = task.get("result_content")
    result = result if isinstance(result, dict) else {}
    runtime = execution.get("runtime", {}) if isinstance(execution, dict) else {}
    runtime = runtime if isinstance(runtime, dict) else {}
    observability = runtime.get("observability", {})
    observability = observability if isinstance(observability, dict) else {}
    runtime_timing = observability.get("timing", {})
    runtime_timing = runtime_timing if isinstance(runtime_timing, dict) else {}
    checkpoints = runtime.get("checkpoints", [])
    return {
        "status": task.get("status"),
        "agent_id": task.get("agent_id"),
        "failure_category": task.get("failure_category"),
        "has_result": bool(result),
        "fallback_used": bool(result.get("fallback_used")),
        "runtime_status": runtime.get("status"),
        "runtime_checkpoint_count": (
            len(checkpoints) if isinstance(checkpoints, list) else 0
        ),
        "runtime_node_count": (
            len(runtime.get("nodes", []))
            if isinstance(runtime.get("nodes"), list)
            else 0
        ),
        "runtime_launch_mode": (runtime.get("launch_decision") or {}).get("mode")
        if isinstance(runtime.get("launch_decision"), dict)
        else None,
        "task_lifecycle_elapsed_ms": _task_lifecycle_elapsed_ms(task),
        "client_observed_terminal_wait_ms": observed_wait_ms,
        "runtime_timing": {
            key: runtime_timing.get(key)
            for key in (
                "run_elapsed_ms",
                "completed_node_elapsed_ms",
                "active_node_wall_ms",
                "runtime_control_overhead_ms",
            )
        },
        "runtime_failure_diagnostics": runtime_failure_diagnostics(execution),
        "metrics": result.get("metrics", {}),
    }


def upload_case_dataset(
    client: Any,
    *,
    base_url: str,
    user_id: str,
    case: E2ECase,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Upload one synthetic dataset and return its redaction-safe task ref."""

    if case.dataset_csv is None:
        return [], None
    response = client.post(
        f"{base_url}/files",
        data={"purpose": "generic"},
        files={
            "upload": (
                f"{case.case_id}.csv",
                case.dataset_csv.encode("utf-8"),
                "text/csv",
            )
        },
        params={"user_id": user_id},
    )
    response.raise_for_status()
    file_payload = cast(dict[str, Any], response.json())
    attachment = {
        key: file_payload[key]
        for key in (
            "id",
            "filename",
            "content_type",
            "size_bytes",
            "storage_key",
            "checksum_sha256",
        )
    }
    attachment["file_id"] = attachment.pop("id")
    manifest = {
        "dataset_id": f"{case.case_id}-synthetic",
        "version": "v1",
        "format": "csv",
        "checksum_sha256": file_payload["checksum_sha256"],
        "row_count": max(0, len(case.dataset_csv.splitlines()) - 1),
        "column_count": len(case.dataset_csv.splitlines()[0].split(",")),
        "authorized": True,
        "contains_sensitive_data": False,
        "source_ref": f"attachment:{file_payload['id']}",
    }
    return [attachment], manifest


def paired_input_payload(
    case: E2ECase,
    *,
    attachments: list[dict[str, Any]],
    runtime_request: dict[str, Any] | None,
    canonical_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stable semantic input snapshot for Legacy/Runtime pairing.

    API task payloads contain mode switches, session IDs, and per-upload file
    IDs.  Those values are execution metadata, not the user input being
    compared.  Keep the content-bearing attachment fields and normalize the
    dataset source reference so repeated uploads hash to the same pair input.
    """

    stable_attachments = [
        {
            key: attachment.get(key)
            for key in (
                "filename",
                "content_type",
                "size_bytes",
                "checksum_sha256",
            )
            if key in attachment
        }
        for attachment in attachments
    ]
    stable_runtime_request = dict(runtime_request or {})
    manifest = stable_runtime_request.get("data_manifest")
    if isinstance(manifest, dict):
        stable_manifest = dict(manifest)
        dataset_id = str(stable_manifest.get("dataset_id", "")).strip()
        if dataset_id:
            stable_manifest["source_ref"] = f"dataset:{dataset_id}"
        else:
            stable_manifest.pop("source_ref", None)
        stable_runtime_request["data_manifest"] = stable_manifest
    return {
        "schema_version": PAIRED_INPUT_SCHEMA_VERSION,
        "course_id": case.course_id,
        "intent": case.intent,
        "canonical_input": canonical_input or {"question": case.question},
        "attachments": stable_attachments,
        "runtime_request": stable_runtime_request,
    }


def run_one(
    client: Any,
    *,
    base_url: str,
    output: Path,
    user_id: str,
    case: E2ECase,
    mode: RunMode,
    sample_id: str,
    poll_interval: float,
    timeout_seconds: float,
    auto_approve_dev: bool,
) -> dict[str, Any]:
    session_id = make_session(
        client, base_url, user_id, case, mode, sample_id
    )
    attachments, manifest = upload_case_dataset(
        client,
        base_url=base_url,
        user_id=user_id,
        case=case,
    )
    runtime_request = (
        {**case.runtime_request, "data_manifest": manifest}
        if case.runtime_request is not None and manifest is not None
        else case.runtime_request
    )
    created = create_task(
        client,
        base_url,
        user_id,
        session_id,
        case,
        mode,
        attachments=attachments,
        runtime_request=runtime_request,
    )
    task_id = str(created["id"])
    terminal, observed_wait_ms, control_actions = await_task(
        client,
        base_url,
        task_id,
        user_id,
        poll_interval=poll_interval,
        timeout_seconds=timeout_seconds,
        auto_approve_dev=auto_approve_dev,
    )
    actual_agent = str(terminal.get("agent_id", ""))
    if actual_agent != case.agent_id:
        # Do not read or package result, event, or debug payloads for an
        # unexpected Agent.  A route mismatch is a test-boundary failure, not
        # permission to inspect another capability's execution.
        return {
            "case_id": case.case_id,
            "sample_id": sample_id,
            "agent_id": case.agent_id,
            "mode": mode,
            "task_id": task_id,
            "expected_agent_matched": False,
            "actual_agent_id": actual_agent,
            "events": {"captured": False},
            "result": {"status": terminal.get("status")},
            "control_actions": control_actions,
            "artifact_dir": None,
        }
    events = task_events(client, base_url, task_id)
    execution = execution_projection(client, base_url, task_id)
    artifact_dir = (
        output / "artifacts" / case.agent_id / case.case_id / sample_id / mode
    )
    task_input = terminal.get("input_content")
    task_canonical_input = (
        task_input.get("canonical_input")
        if isinstance(task_input, dict)
        and isinstance(task_input.get("canonical_input"), dict)
        else None
    )
    write_json(
        artifact_dir / "input.json",
        paired_input_payload(
            case,
            attachments=attachments,
            runtime_request=runtime_request,
            canonical_input=task_canonical_input,
        ),
    )
    write_json(artifact_dir / "task.json", terminal)
    write_json(artifact_dir / "events.json", events)
    write_json(artifact_dir / "execution.json", execution)
    return {
        "case_id": case.case_id,
        "sample_id": sample_id,
        "agent_id": case.agent_id,
        "mode": mode,
        "task_id": task_id,
        "expected_agent_matched": terminal.get("agent_id") == case.agent_id,
        "events": event_summary(events),
        "result": result_summary(
            terminal, execution, observed_wait_ms=observed_wait_ms
        ),
        "control_actions": control_actions,
        "artifact_dir": str(artifact_dir),
    }


def main() -> int:
    args = parse_args()
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - environment failure
        raise SystemExit("httpx is required; run with the repository .venv") from exc
    cases = selected_cases(args.case)
    if not 1 <= args.repeat_count <= 20:
        raise SystemExit("--repeat-count must be between 1 and 20")
    output = args.output.resolve()
    report: dict[str, Any] = {
        "schema_version": "runtime_authorized_dev_e2e.v3",
        "started_at": datetime.now(UTC).isoformat(),
        "base_url": api_root(args.base_url),
        "case_ids": [case.case_id for case in cases],
        "repeat_count": args.repeat_count,
        "pair_order": args.pair_order,
        "auto_approve_dev": args.auto_approve_dev,
        "results": [],
    }
    # A development API on loopback must never be redirected through a
    # workstation proxy.  In particular, HTTP_PROXY can turn a healthy local
    # session request into a misleading 502 response.
    with httpx.Client(timeout=30.0, trust_env=False) as client:
        for case in cases:
            for sample_index in range(args.repeat_count):
                sample_id = f"sample-{sample_index + 1:03d}"
                for mode in pair_modes(args.mode, args.pair_order, sample_index):
                    report["results"].append(
                        run_one(
                            client,
                            base_url=api_root(args.base_url),
                            output=output,
                            user_id=args.user_id,
                            case=case,
                            mode=mode,
                            sample_id=sample_id,
                            poll_interval=args.poll_interval,
                            timeout_seconds=args.timeout_seconds,
                            auto_approve_dev=args.auto_approve_dev,
                        )
                    )
    report["completed_at"] = datetime.now(UTC).isoformat()
    report["summary"] = {
        "runs": len(report["results"]),
        "completed": sum(
            item["result"]["status"] == "completed" for item in report["results"]
        ),
        "timeouts": sum(
            item["result"]["status"] == "timeout" for item in report["results"]
        ),
        "agent_mismatches": sum(
            not item["expected_agent_matched"] for item in report["results"]
        ),
        "event_order_failures": sum(
            item["events"].get("captured") is not False
            and not item["events"]["strictly_increasing"]
            for item in report["results"]
        ),
    }
    report_path = output / "report.json"
    write_json(report_path, report)
    print(
        json.dumps(
            {"report": str(report_path), **report["summary"]},
            ensure_ascii=False,
        )
    )
    summary = report["summary"]
    return 0 if (
        summary["completed"] == summary["runs"]
        and summary["agent_mismatches"] == 0
        and summary["event_order_failures"] == 0
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
