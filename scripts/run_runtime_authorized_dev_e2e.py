"""Capture small, authorized Legacy/Runtime development E2E pairs.

This runner intentionally exercises the public Task API rather than importing
TaskRunner.  It is for a controlled development environment only: the chosen
test cases contain no student data, and all artifacts are written to an
ignored directory supplied by the operator.  It never changes launch modes,
release evidence, or provider configuration.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

RunMode = Literal["legacy", "runtime"]
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "flow_id",
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
    return base_url.rstrip("/")


def make_session(
    client: Any,
    base_url: str,
    user_id: str,
    case: E2ECase,
    mode: RunMode,
) -> str:
    response = client.post(
        f"{base_url}/sessions",
        json={
            "user_id": user_id,
            "course_id": case.course_id,
            "title": f"authorized-e2e:{case.case_id}:{mode}",
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
) -> dict[str, Any]:
    response = client.post(
        f"{base_url}/tasks",
        json={
            "session_id": session_id,
            "user_id": user_id,
            "user_role": "admin",
            "course_id": case.course_id,
            "intent": case.intent,
            "canonical_input": {"question": case.question},
            "options": {
                "debug_agent_id": case.agent_id,
                case.runtime_option_key: {"execute": mode == "runtime"},
            },
        },
    )
    response.raise_for_status()
    return response.json()


def await_task(
    client: Any,
    base_url: str,
    task_id: str,
    user_id: str,
    *,
    poll_interval: float,
    timeout_seconds: float,
) -> tuple[dict[str, Any], int]:
    started = time.monotonic()
    latest: dict[str, Any] = {}
    while time.monotonic() - started < timeout_seconds:
        response = client.get(
            f"{base_url}/tasks/{task_id}", params={"user_id": user_id}
        )
        response.raise_for_status()
        latest = response.json()
        if str(latest.get("status", "")).casefold() in TERMINAL_STATUSES:
            return latest, round((time.monotonic() - started) * 1000)
        time.sleep(poll_interval)
    return (
        {**latest, "status": "timeout", "timeout_seconds": timeout_seconds},
        round((time.monotonic() - started) * 1000),
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
        "metrics": result.get("metrics", {}),
    }


def run_one(
    client: Any,
    *,
    base_url: str,
    output: Path,
    user_id: str,
    case: E2ECase,
    mode: RunMode,
    poll_interval: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    session_id = make_session(client, base_url, user_id, case, mode)
    created = create_task(client, base_url, user_id, session_id, case, mode)
    task_id = str(created["id"])
    terminal, observed_wait_ms = await_task(
        client,
        base_url,
        task_id,
        user_id,
        poll_interval=poll_interval,
        timeout_seconds=timeout_seconds,
    )
    actual_agent = str(terminal.get("agent_id", ""))
    if actual_agent != case.agent_id:
        # Do not read or package result, event, or debug payloads for an
        # unexpected Agent.  A route mismatch is a test-boundary failure, not
        # permission to inspect another capability's execution.
        return {
            "case_id": case.case_id,
            "agent_id": case.agent_id,
            "mode": mode,
            "task_id": task_id,
            "expected_agent_matched": False,
            "actual_agent_id": actual_agent,
            "events": {"captured": False},
            "result": {"status": terminal.get("status")},
            "artifact_dir": None,
        }
    events = task_events(client, base_url, task_id)
    execution = execution_projection(client, base_url, task_id)
    artifact_dir = output / "artifacts" / case.agent_id / case.case_id / mode
    write_json(artifact_dir / "input.json", {"question": case.question})
    write_json(artifact_dir / "task.json", terminal)
    write_json(artifact_dir / "events.json", events)
    write_json(artifact_dir / "execution.json", execution)
    return {
        "case_id": case.case_id,
        "agent_id": case.agent_id,
        "mode": mode,
        "task_id": task_id,
        "expected_agent_matched": terminal.get("agent_id") == case.agent_id,
        "events": event_summary(events),
        "result": result_summary(
            terminal, execution, observed_wait_ms=observed_wait_ms
        ),
        "artifact_dir": str(artifact_dir),
    }


def main() -> int:
    args = parse_args()
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - environment failure
        raise SystemExit("httpx is required; run with the repository .venv") from exc
    cases = selected_cases(args.case)
    output = args.output.resolve()
    report: dict[str, Any] = {
        "schema_version": "runtime_authorized_dev_e2e.v1",
        "started_at": datetime.now(UTC).isoformat(),
        "base_url": api_root(args.base_url),
        "case_ids": [case.case_id for case in cases],
        "results": [],
    }
    modes: tuple[RunMode, ...] = (
        ("legacy", "runtime") if args.mode == "both" else (args.mode,)
    )
    # A development API on loopback must never be redirected through a
    # workstation proxy.  In particular, HTTP_PROXY can turn a healthy local
    # session request into a misleading 502 response.
    with httpx.Client(timeout=30.0, trust_env=False) as client:
        for case in cases:
            for mode in modes:
                report["results"].append(
                    run_one(
                        client,
                        base_url=api_root(args.base_url),
                        output=output,
                        user_id=args.user_id,
                        case=case,
                        mode=mode,
                        poll_interval=args.poll_interval,
                        timeout_seconds=args.timeout_seconds,
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
