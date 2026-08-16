"""Capture a redacted public-API LearningLoop Runtime development run.

The LearningLoop Runtime is selected by the API process profile, not by an
extra request field.  Run this script once against a Runtime-enabled process
and once against a Legacy process to form a paired comparison.  The fixture
uses synthetic identifiers and a deterministic circuit problem only.
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

RunMode = Literal["legacy", "runtime"]
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
MAX_AUTO_APPROVALS = 3
SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "raw_prompt",
    "secret",
    "token",
}


@dataclass(frozen=True, slots=True)
class LearningCase:
    case_id: str
    action: str
    answer: str
    payload: dict[str, Any]


CASES: tuple[LearningCase, ...] = (
    LearningCase(
        case_id="teaching_request_more_hint",
        action="request_more_hint",
        answer="",
        payload={},
    ),
    LearningCase(
        case_id="learning_progress_revision",
        action="submit_attempt_revision",
        answer="P=20 W",
        payload={
            "attempt": {
                "raw_text": "P=20 W",
                "final_answer": "20 W",
                "steps": [],
                "confidence": 0.9,
            }
        },
    ),
    LearningCase(
        case_id="learning_progress_manual_review",
        action="submit_attempt_revision",
        answer="我修改了方法，但暂时没有给出数值结果。",
        payload={"attempt": {"raw_text": "方法已修改，但暂无数值结果"}},
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--user-id", default="learning-authorized-dev-e2e")
    parser.add_argument(
        "--task-id",
        default="",
        help="Reuse an already completed, synthetic development task.",
    )
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--mode", choices=("legacy", "runtime"), required=True)
    parser.add_argument("--sample-id", default="sample-001")
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--auto-approve-dev", action="store_true")
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


def selected_cases(requested: list[str]) -> tuple[LearningCase, ...]:
    wanted = set(requested)
    available = {case.case_id for case in CASES}
    unknown = wanted - available
    if unknown:
        raise ValueError(f"unknown case IDs: {', '.join(sorted(unknown))}")
    return tuple(case for case in CASES if not wanted or case.case_id in wanted)


def api_root(base_url: str) -> str:
    return base_url.rstrip("/")


def power_canonical_input() -> dict[str, Any]:
    return {
        "text": "A 10 V source drives a 2 ohm resistor. Find the current and power.",
        "problem_type": "power",
        "equations_given": ["I=V/R", "P=V*I"],
        "known_conditions": [
            {"name": "V", "value": 10, "unit": "V"},
            {"name": "R", "value": 2, "unit": "ohm"},
        ],
        "target_quantities": [
            {"name": "I", "unit": "A"},
            {"name": "P", "unit": "W"},
        ],
        "structure_status": "complete",
        "extraction_confidence": 0.99,
    }


def create_session(client: Any, base_url: str, user_id: str, case: LearningCase) -> str:
    response = client.post(
        f"{base_url}/sessions",
        json={
            "user_id": user_id,
            "course_id": "CT",
            "title": f"authorized-learning-e2e:{case.case_id}",
        },
    )
    response.raise_for_status()
    return str(response.json()["id"])


def create_task(
    client: Any,
    base_url: str,
    user_id: str,
    session_id: str,
) -> str:
    response = client.post(
        f"{base_url}/tasks",
        json={
            "session_id": session_id,
            "user_id": user_id,
            "user_role": "student",
            "scene": "solving",
            "course_id": "CT",
            "intent": "solve_problem",
            "canonical_input": power_canonical_input(),
            "attachments": [],
            "context_refs": [],
            "options": {
                "teaching_mode": "check_my_work",
                "student_attempt": {
                    "raw_text": "I=4 A; P=40 W",
                    "final_answer": "I=4 A; P=40 W",
                },
            },
        },
    )
    response.raise_for_status()
    return str(response.json()["id"])


def task_status(
    client: Any, base_url: str, task_id: str, user_id: str
) -> dict[str, Any]:
    response = client.get(f"{base_url}/tasks/{task_id}", params={"user_id": user_id})
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def await_task(
    client: Any,
    base_url: str,
    task_id: str,
    user_id: str,
    *,
    poll_interval: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    started = time.monotonic()
    latest: dict[str, Any] = {}
    while time.monotonic() - started < timeout_seconds:
        latest = task_status(client, base_url, task_id, user_id)
        if str(latest.get("status", "")).casefold() in TERMINAL_STATUSES:
            return latest
        time.sleep(poll_interval)
    return {**latest, "status": "timeout", "timeout_seconds": timeout_seconds}


def learning_action(
    client: Any,
    base_url: str,
    task_id: str,
    user_id: str,
    case: LearningCase,
    sample_id: str,
) -> dict[str, Any]:
    response = client.post(
        f"{base_url}/learning/actions",
        json={
            "source_task_id": task_id,
            "user_id": user_id,
            "action": case.action,
            "idempotency_key": f"{case.case_id}:{sample_id}",
            "student_answer": case.answer,
            "payload": case.payload,
        },
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def runtime_status(
    client: Any, base_url: str, run_id: str, user_id: str
) -> dict[str, Any]:
    response = client.get(
        f"{base_url}/learning/runtime/{run_id}", params={"user_id": user_id}
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def finish_runtime(
    client: Any,
    base_url: str,
    run_id: str,
    user_id: str,
    *,
    poll_interval: float,
    timeout_seconds: float,
    auto_approve_dev: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    started = time.monotonic()
    latest: dict[str, Any] = {}
    controls: list[dict[str, Any]] = []
    status_history: list[str] = []
    while time.monotonic() - started < timeout_seconds:
        latest = runtime_status(client, base_url, run_id, user_id)
        status = str(latest.get("status", "")).casefold()
        if status and (not status_history or status_history[-1] != status):
            status_history.append(status)
        if status in TERMINAL_STATUSES:
            latest["status_history"] = status_history
            return latest, controls
        if status == "waiting_approval" and auto_approve_dev:
            attempts = sum(item.get("action") == "approve" for item in controls)
            if attempts >= MAX_AUTO_APPROVALS:
                controls.append({"action": "approval_budget_exhausted"})
                break
            response = client.post(
                f"{base_url}/learning/runtime/{run_id}/control",
                json={
                    "action": "approve",
                    "expected_state_version": latest.get("state_version"),
                    "idempotency_key": f"approve:{run_id}:{attempts + 1}",
                },
            )
            if response.status_code == 409:
                controls.append({"action": "approve_conflict"})
            else:
                response.raise_for_status()
                control_record: dict[str, Any] = {"action": "approve"}
                body = response.json()
                if isinstance(body, dict):
                    control_record["status"] = body.get("status")
                    result = body.get("result")
                    if isinstance(result, dict):
                        control_record["result_status"] = result.get("status")
                controls.append(control_record)
        time.sleep(poll_interval)
    return {
        **latest,
        "status": "timeout",
        "timeout_seconds": timeout_seconds,
        "status_history": status_history,
    }, controls


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")


def event_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    sequences = [
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
    }


def runtime_summary(status: dict[str, Any]) -> dict[str, Any]:
    nodes = status.get("node_statuses", [])
    safe_nodes: list[dict[str, Any]] = []
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = node.get("node_id")
            error_code = node.get("error_code", "")
            safe_nodes.append(
                {
                    "node_id": (
                        node_id
                        if isinstance(node_id, str)
                        and _SAFE_IDENTIFIER.fullmatch(node_id)
                        else None
                    ),
                    "status": node.get("status"),
                    "effect_status": node.get("effect_status"),
                    "attempt": node.get("attempt"),
                    "error_code": (
                        error_code
                        if isinstance(error_code, str)
                        and _SAFE_IDENTIFIER.fullmatch(error_code)
                        else ""
                    ),
                }
            )
    return {
        "status": status.get("status"),
        "run_kind": status.get("run_kind"),
        "state_version": status.get("state_version"),
        "approval_required": status.get("approval_required"),
        "resumable": status.get("resumable"),
        "available_controls": status.get("available_controls", []),
        "node_statuses": safe_nodes,
    }


def safe_checkpoint_summaries(value: Any) -> list[dict[str, Any]]:
    """Keep only redacted checkpoint/event correlation fields."""

    if not isinstance(value, list):
        return []
    summaries: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        sequence = item.get("sequence")
        state_version = item.get("state_version")
        event_sequence = item.get("event_sequence")
        if not all(
            isinstance(number, int) and number >= 0
            for number in (sequence, state_version, event_sequence)
        ):
            continue
        status = item.get("status")
        created_at = item.get("created_at")
        summaries.append(
            {
                "sequence": sequence,
                "state_version": state_version,
                "status": status if isinstance(status, str) else "",
                "event_sequence": event_sequence,
                "created_at": created_at if isinstance(created_at, str) else "",
            }
        )
    return summaries


def checkpoint_event_summary(checkpoints: list[dict[str, Any]]) -> dict[str, Any]:
    sequences = [
        int(item["event_sequence"])
        for item in checkpoints
        if isinstance(item.get("event_sequence"), int)
    ]
    return {
        "count": len(checkpoints),
        "strictly_increasing": all(
            sequences[index] < sequences[index + 1]
            for index in range(len(sequences) - 1)
        ),
        "first_event_sequence": sequences[0] if sequences else None,
        "last_event_sequence": sequences[-1] if sequences else None,
    }


def run_one(
    client: Any,
    *,
    base_url: str,
    output: Path,
    user_id: str,
    existing_task_id: str,
    case: LearningCase,
    mode: RunMode,
    sample_id: str,
    poll_interval: float,
    timeout_seconds: float,
    auto_approve_dev: bool,
) -> dict[str, Any]:
    task_id = existing_task_id
    if not task_id:
        session_id = create_session(client, base_url, user_id, case)
        task_id = create_task(client, base_url, user_id, session_id)
    task = await_task(
        client,
        base_url,
        task_id,
        user_id,
        poll_interval=poll_interval,
        timeout_seconds=timeout_seconds,
    )
    action: dict[str, Any] = {}
    runtime: dict[str, Any] = {}
    checkpoints: list[dict[str, Any]] = []
    checkpoint_capture = "not_applicable"
    controls: list[dict[str, Any]] = []
    if task.get("status") == "completed":
        action = learning_action(client, base_url, task_id, user_id, case, sample_id)
        run_id = action.get("runtime_run_id")
        if isinstance(run_id, str) and run_id:
            runtime, controls = finish_runtime(
                client,
                base_url,
                run_id,
                user_id,
                poll_interval=poll_interval,
                timeout_seconds=timeout_seconds,
                auto_approve_dev=auto_approve_dev,
            )
            checkpoint_capture = "unavailable"
            debug_response = client.get(f"{base_url}/debug/execution/{task_id}")
            if debug_response.status_code == 200:
                debug_payload = debug_response.json()
                learning_projection = (
                    debug_payload.get("learning_runtime")
                    if isinstance(debug_payload, dict)
                    else None
                )
                if isinstance(learning_projection, dict):
                    projected_run_id = learning_projection.get("run_id")
                    if projected_run_id in {None, run_id}:
                        checkpoints = safe_checkpoint_summaries(
                            learning_projection.get("checkpoints")
                        )
                        checkpoint_capture = "captured"
                    else:
                        checkpoint_capture = "run_mismatch"
            else:
                checkpoint_capture = f"http_{debug_response.status_code}"
    events_response = client.get(
        f"{base_url}/tasks/{task_id}/events", params={"after": 0}
    )
    events_response.raise_for_status()
    events = events_response.json()
    events = events if isinstance(events, list) else []
    artifact_dir = output / "artifacts" / case.case_id / sample_id / mode
    write_json(artifact_dir / "input.json", {"case_id": case.case_id, "mode": mode})
    write_json(artifact_dir / "task.json", task)
    write_json(artifact_dir / "learning_action.json", action)
    write_json(artifact_dir / "runtime_status.json", runtime)
    write_json(artifact_dir / "checkpoints.json", checkpoints)
    write_json(artifact_dir / "events.json", events)
    expected_runtime = mode == "runtime"
    observed_runtime = bool(action.get("runtime_run_id"))
    result_status = runtime.get("status") if observed_runtime else action.get("status")
    return {
        "case_id": case.case_id,
        "sample_id": sample_id,
        "mode": mode,
        "task_id": task_id,
        "expected_runtime_route": expected_runtime,
        "observed_runtime_route": observed_runtime,
        "route_match": expected_runtime == observed_runtime,
        "task_status": task.get("status"),
        "action_status": action.get("status"),
        "runtime": runtime_summary(runtime),
        "runtime_status_history": runtime.get("status_history", []),
        "checkpoint_capture": checkpoint_capture,
        "checkpoints": checkpoint_event_summary(checkpoints),
        "result_status": result_status,
        "controls": controls,
        "events": event_summary(events),
        "artifact_dir": str(artifact_dir),
    }


def main() -> int:
    args = parse_args()
    cases = selected_cases(args.case)
    output = args.output.resolve()
    base_url = api_root(args.base_url)
    report: dict[str, Any] = {
        "schema_version": "learning_runtime_authorized_dev_e2e.v1",
        "started_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "mode": args.mode,
        "task_id_source": "existing" if args.task_id else "created",
        "case_ids": [case.case_id for case in cases],
        "auto_approve_dev": args.auto_approve_dev,
        "results": [],
    }
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - environment failure
        raise SystemExit("httpx is required; run with the repository .venv") from exc
    with httpx.Client(timeout=30.0, trust_env=False) as client:
        readiness = client.get(f"{base_url}/learning/runtime-readiness")
        readiness.raise_for_status()
        report["readiness"] = readiness.json()
        for case in cases:
            report["results"].append(
                run_one(
                    client,
                    base_url=base_url,
                    output=output,
                    user_id=args.user_id,
                    existing_task_id=args.task_id,
                    case=case,
                    mode=cast(RunMode, args.mode),
                    sample_id=args.sample_id,
                    poll_interval=args.poll_interval,
                    timeout_seconds=args.timeout_seconds,
                    auto_approve_dev=args.auto_approve_dev,
                )
            )
    report["completed_at"] = datetime.now(UTC).isoformat()
    results = cast(list[dict[str, Any]], report["results"])
    report["summary"] = {
        "runs": len(results),
        "completed": sum(
            item.get("result_status") == "completed" for item in results
        ),
        "route_mismatches": sum(not item.get("route_match") for item in results),
        "event_order_failures": sum(
            not item["events"].get("strictly_increasing") for item in results
        ),
    }
    report_path = output / "report.json"
    write_json(report_path, report)
    print(
        json.dumps(
            {"report": str(report_path), **report["summary"]}, ensure_ascii=False
        )
    )
    summary = report["summary"]
    return 0 if (
        summary["completed"] == summary["runs"]
        and not summary["route_mismatches"]
        and not summary["event_order_failures"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
