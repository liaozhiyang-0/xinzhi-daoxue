from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_CASES = ROOT / "统一格式" / "all_cases.json"
DEFAULT_REPORT_DIR = ROOT / "统一格式" / "reports"
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def load_cases(path: Path) -> list[dict[str, Any]]:
    if path.suffix.casefold() == ".jsonl":
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ValueError(f"{path}: JSON顶层必须为{{cases:[...]}}")
    return cases


def select_cases(
    cases: list[dict[str, Any]],
    *,
    course: str | None,
    case_id: str | None,
    max_cases: int | None,
    include_review: bool,
) -> list[dict[str, Any]]:
    selected = cases
    if course:
        selected = [item for item in selected if item["course"] == course.upper()]
    if case_id:
        selected = [item for item in selected if item["case_id"] == case_id]
    if not include_review:
        selected = [
            item for item in selected if not item.get("requires_manual_review")
        ]
    if max_cases is not None:
        selected = selected[:max_cases]
    return selected


def request_preview(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "course_id": case["course"],
        "intent": case["intent"],
        "canonical_input": {"question": case["message"]},
        "attachments": [
            {"local_path": ref["path"], "media_type": ref["media_type"]}
            for ref in case["file_refs"]
        ],
        "options": case.get("task_options") or {},
    }


def attachment_from_upload(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "filename",
        "content_type",
        "size_bytes",
        "storage_key",
        "checksum_sha256",
    )
    selected = {key: payload.get(key) for key in keys}
    selected["file_id"] = selected.pop("id")
    selected["provider_file_id"] = None
    return selected


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_case(
    client: Any,
    *,
    base_url: str,
    case: dict[str, Any],
    user_id: str,
    poll_interval: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    started = time.monotonic()
    session_response = client.post(
        f"{base_url}/sessions",
        json={
            "user_id": user_id,
            "course_id": case["course"],
            "title": f"真实测试 {case['case_id']}",
        },
    )
    session_response.raise_for_status()
    session_id = session_response.json()["id"]

    attachments: list[dict[str, Any]] = []
    for ref in case["file_refs"]:
        path = ROOT / ref["path"]
        with path.open("rb") as stream:
            upload_response = client.post(
                f"{base_url}/files",
                data={"purpose": "student_solver_image"},
                files={"upload": (path.name, stream, ref["media_type"])},
            )
        upload_response.raise_for_status()
        attachments.append(attachment_from_upload(upload_response.json()))

    task_response = client.post(
        f"{base_url}/tasks",
        json={
            "session_id": session_id,
            "user_id": user_id,
            "course_id": case["course"],
            "intent": case["intent"],
            "canonical_input": {"question": case["message"]},
            "attachments": attachments,
            "options": case.get("task_options") or {},
        },
    )
    task_response.raise_for_status()
    task = task_response.json()
    task_id = task["id"]

    while str(task.get("status", "")).casefold() not in TERMINAL_STATUSES:
        if time.monotonic() - started > timeout_seconds:
            return {
                "case_id": case["case_id"],
                "status": "timeout",
                "task_id": task_id,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        time.sleep(poll_interval)
        response = client.get(
            f"{base_url}/tasks/{task_id}",
            params={"user_id": user_id},
        )
        response.raise_for_status()
        task = response.json()

    return {
        "case_id": case["case_id"],
        "status": task["status"],
        "task_id": task_id,
        "course": case["course"],
        "expected_agent": case["expected_agent"],
        "actual_agent": task.get("agent_id"),
        "reference_answer": case.get("reference_answer"),
        "reference_answer_assets": (case.get("structured_input") or {}).get(
            "reference_answer_assets", []
        ),
        "result_content": task.get("result_content"),
        "error_message": task.get("error_message"),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="将统一测试集直接提交到本地POST /api/v1/tasks"
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000/api/v1",
    )
    parser.add_argument(
        "--course",
        choices=["AE", "COMM", "CT", "DE", "DSP", "SS"],
    )
    parser.add_argument("--case-id")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--include-review", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--timeout-seconds", type=float, default=240)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅检查筛选结果与请求预览，不调用API",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    cases = select_cases(
        load_cases(args.cases.resolve()),
        course=args.course,
        case_id=args.case_id,
        max_cases=args.max_cases,
        include_review=args.include_review,
    )
    if not cases:
        raise SystemExit("没有符合条件的测试样例")

    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "case_count": len(cases),
                    "case_ids": [case["case_id"] for case in cases],
                    "first_request_preview": request_preview(cases[0]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    try:
        import httpx
    except ImportError as exc:
        raise SystemExit(
            "缺少httpx；请使用仓库.venv中的Python运行此脚本"
        ) from exc

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = (
        args.output.resolve()
        if args.output
        else DEFAULT_REPORT_DIR / f"api_run_{timestamp}.json"
    )
    user_id = f"real-benchmark-{uuid.uuid4().hex[:12]}"
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "started_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url.rstrip("/"),
        "user_id": user_id,
        "case_ids": [case["case_id"] for case in cases],
        "results": [],
    }

    with httpx.Client(timeout=args.timeout_seconds) as client:
        for case in cases:
            try:
                result = run_case(
                    client,
                    base_url=args.base_url.rstrip("/"),
                    case=case,
                    user_id=user_id,
                    poll_interval=args.poll_interval,
                    timeout_seconds=args.timeout_seconds,
                )
            except Exception as exc:
                result = {
                    "case_id": case["case_id"],
                    "status": "request_error",
                    "error": str(exc),
                }
            report["results"].append(result)
            write_report(output, report)

    report["completed_at"] = datetime.now(UTC).isoformat()
    report["summary"] = dict(
        sorted(
            {
                status: sum(
                    item.get("status") == status for item in report["results"]
                )
                for status in {
                    str(item.get("status")) for item in report["results"]
                }
            }.items()
        )
    )
    write_report(output, report)
    print(json.dumps({"report": str(output), **report["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
