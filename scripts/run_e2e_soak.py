"""Run a bounded local end-to-end soak test for the web application.

The default duration is ten hours.  The test intentionally keeps external
research traffic sparse: one research conversation is run every few cycles,
while page readiness and local multi-domain tasks are checked every cycle.
Results are written as one JSON object per line so an interrupted run remains
auditable.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "evaluation" / "reports" / "e2e-soak.jsonl"
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
LOGGER = logging.getLogger("xzd.e2e_soak")


@dataclass(frozen=True)
class SoakCase:
    name: str
    message: str
    expected_agent_tokens: tuple[str, ...]


LOCAL_CASES = (
    SoakCase(
        name="general_network",
        message="为什么服务器要回复 SYN+ACK？",
        expected_agent_tokens=("GENERAL", "LEARN"),
    ),
    SoakCase(
        name="circuit_concept",
        message="请用通俗语言解释基尔霍夫电流定律，并给出一个简单例子。",
        expected_agent_tokens=("SOLVER", "LEARN", "GENERAL"),
    ),
    SoakCase(
        name="academic_writing",
        message="请把下面这句话改写成学术中文：柔性传感器能够感知人体运动。",
        expected_agent_tokens=("WRITING",),
    ),
    SoakCase(
        name="data_analysis",
        message="请分析以下数据的平均值、最大值和趋势：1, 2, 3, 5, 8。",
        expected_agent_tokens=("DATA",),
    ),
    SoakCase(
        name="digital_concept",
        message="锁存器和触发器有什么区别？",
        expected_agent_tokens=("LEARN", "SOLVER", "GENERAL"),
    ),
    SoakCase(
        name="signal_concept",
        message="请用通俗语言解释奈奎斯特采样定理，以及采样不足会产生什么问题。",
        expected_agent_tokens=("LEARN", "SOLVER", "GENERAL"),
    ),
    SoakCase(
        name="communication_concept",
        message="什么是QAM调制？它为什么能提高通信系统的频谱利用率？",
        expected_agent_tokens=("LEARN", "SOLVER", "GENERAL"),
    ),
    SoakCase(
        name="ai_concept",
        message="请用通俗语言解释多模态大模型与智能体的区别。",
        expected_agent_tokens=("LEARN", "GENERAL"),
    ),
    SoakCase(
        name="flexible_electronics_concept",
        message="请解释柔性电子器件中应变传感器的基本工作原理。",
        expected_agent_tokens=("LEARN", "GENERAL"),
    ),
    SoakCase(
        name="lesson_preparation",
        message="给本科生设计60分钟相量法课程，要包含课堂活动和形成性评价。",
        expected_agent_tokens=("TEACH",),
    ),
    SoakCase(
        name="assignment_review",
        message=(
            "题目：求电路电流\n学生答案：我得到2A\n"
            "评分标准：列式4分，结果6分\n满分：10分\n请批改并给教师反馈。"
        ),
        expected_agent_tokens=("TEACH",),
    ),
)

RESEARCH_MESSAGE = "2024年至2026年生成式人工智能在多模态和智能体方面有哪些代表性进展？"
RESEARCH_FOLLOW_UP = "其中哪些进展已经有产品化迹象？请按多模态和智能体分别说明。"
TOPIC_SWITCH = "为什么服务器要回复 SYN+ACK？"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--duration-seconds", type=float, default=10 * 60 * 60)
    parser.add_argument("--interval-seconds", type=float, default=300)
    parser.add_argument("--research-every", type=int, default=6)
    parser.add_argument("--poll-timeout-seconds", type=float, default=180)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _answer(task: dict[str, Any]) -> str:
    result = task.get("result_content")
    return str(result.get("answer", "")) if isinstance(result, dict) else ""


def _structured(task: dict[str, Any]) -> dict[str, Any]:
    result = task.get("result_content")
    if not isinstance(result, dict):
        return {}
    value = result.get("structured_result")
    return value if isinstance(value, dict) else {}


async def _wait_task(
    client: httpx.AsyncClient, task_id: str, timeout_seconds: float
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = await client.get(f"/api/v1/tasks/{task_id}")
        response.raise_for_status()
        task = cast(dict[str, Any], response.json())
        if task.get("status") in TERMINAL_STATUSES:
            return task
        await asyncio.sleep(1)
    raise TimeoutError(f"task {task_id} did not finish within {timeout_seconds}s")


async def _run_task(
    client: httpx.AsyncClient,
    message: str,
    *,
    session_id: str | None,
    poll_timeout_seconds: float,
    user_id: str,
) -> dict[str, Any]:
    started = time.monotonic()
    payload: dict[str, Any] = {
        "message": message,
        "user_id": user_id,
        "metadata": {"source": "e2e_soak"},
    }
    if session_id:
        payload["session_id"] = session_id
    response = await client.post("/api/v1/chat", json=payload)
    response.raise_for_status()
    submission = response.json()
    task = await _wait_task(client, str(submission["task_id"]), poll_timeout_seconds)
    task["submission"] = submission
    task["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return task


def _task_record(name: str, task: dict[str, Any]) -> dict[str, Any]:
    structured = _structured(task)
    external = structured.get("external_retrieval")
    external = external if isinstance(external, dict) else {}
    return {
        "case": name,
        "task_id": task.get("id"),
        "status": task.get("status"),
        "agent_id": task.get("agent_id"),
        "intent": task.get("intent"),
        "elapsed_seconds": task.get("elapsed_seconds"),
        "answer_length": len(_answer(task)),
        "external_status": external.get("status"),
        "external_provider_status": (
            dict(external.get("provider_status", {}))
            if isinstance(external.get("provider_status"), dict)
            else {}
        ),
        "external_items": len(external.get("items", []))
        if isinstance(external.get("items", []), list)
        else 0,
        "warnings": list(task.get("result_content", {}).get("warnings", []))
        if isinstance(task.get("result_content"), dict)
        else [],
    }


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in terms)


def _validate_case(case: SoakCase, task: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if task.get("status") != "completed":
        errors.append(f"status={task.get('status')}")
    if not _answer(task).strip():
        errors.append("empty_answer")
    agent_id = str(task.get("agent_id", "")).upper()
    if not any(token in agent_id for token in case.expected_agent_tokens):
        errors.append(f"unexpected_agent={agent_id}")
    return errors


async def _check_surface(client: httpx.AsyncClient) -> dict[str, Any]:
    health = await client.get("/api/v1/health")
    health.raise_for_status()
    workspace = await client.get("/workspace")
    workspace.raise_for_status()
    html = workspace.text
    asset_paths = (
        "/debug-assets/ui-core.js?v=20260811-workspace-answer-reset-v1",
        "/debug-assets/workspace.js?v=20260811-workspace-answer-reset-v1",
    )
    asset_statuses: dict[str, int] = {}
    for path in asset_paths:
        asset = await client.get(path)
        asset.raise_for_status()
        asset_statuses[path] = asset.status_code
    return {
        "health_status": health.json().get("status"),
        "workspace_status": workspace.status_code,
        "frontend_asset_statuses": asset_statuses,
        "frontend_build_ready": (
            "ui-core.js?v=20260811-workspace-answer-reset-v1" in html
            and "workspace.js?v=20260811-workspace-answer-reset-v1" in html
            and all(status == 200 for status in asset_statuses.values())
        ),
    }


async def _run_cycle(
    client: httpx.AsyncClient,
    cycle: int,
    *,
    research_every: int,
    poll_timeout_seconds: float,
) -> dict[str, Any]:
    cycle_record: dict[str, Any] = {
        "timestamp": _now(),
        "cycle": cycle,
        "surface": await _check_surface(client),
        "tasks": [],
        "failures": [],
    }
    user_id = f"e2e-soak-{cycle}"
    for case in LOCAL_CASES:
        try:
            task = await _run_task(
                client,
                case.message,
                session_id=None,
                poll_timeout_seconds=poll_timeout_seconds,
                user_id=user_id,
            )
            cycle_record["tasks"].append(_task_record(case.name, task))
            cycle_record["failures"].extend(
                f"{case.name}:{item}" for item in _validate_case(case, task)
            )
        except Exception as exc:  # noqa: BLE001 - soak must continue after one case
            cycle_record["failures"].append(f"{case.name}:{type(exc).__name__}:{exc}")

    if research_every > 0 and cycle % research_every == 0:
        try:
            first = await _run_task(
                client,
                RESEARCH_MESSAGE,
                session_id=None,
                poll_timeout_seconds=poll_timeout_seconds,
                user_id=user_id,
            )
            first_record = _task_record("research_initial", first)
            cycle_record["tasks"].append(first_record)
            if first.get("status") != "completed":
                cycle_record["failures"].append("research_initial:incomplete")
            if first_record["external_items"] <= 0:
                cycle_record["failures"].append("research_initial:no_external_evidence")
            first_answer = _answer(first)
            if not _contains_any(first_answer, ("多模态", "智能体", "agent")):
                cycle_record["failures"].append(
                    "research_initial:topic_terms_missing"
                )
            if _contains_any(first_answer, ("柔性电子", "电子皮肤")):
                cycle_record["failures"].append(
                    "research_initial:stale_topic_leak"
                )
            external = _structured(first).get("external_retrieval")
            if isinstance(external, dict) and external.get("status") != "completed":
                cycle_record["failures"].append(
                    f"research_initial:external_status={external.get('status')}"
                )
            provider_status = first_record["external_provider_status"]
            if provider_status and not any(
                status == "completed" for status in provider_status.values()
            ):
                cycle_record["failures"].append(
                    "research_initial:all_external_providers_failed"
                )
            if any(
                "requested at least" in str(warning).casefold()
                for warning in first_record["warnings"]
            ):
                cycle_record["failures"].append(
                    "research_initial:invented_paper_count_requirement"
                )
            session_id = first.get("session_id")
            if isinstance(session_id, str) and session_id:
                follow_up = await _run_task(
                    client,
                    RESEARCH_FOLLOW_UP,
                    session_id=session_id,
                    poll_timeout_seconds=poll_timeout_seconds,
                    user_id=user_id,
                )
                cycle_record["tasks"].append(
                    _task_record("research_follow_up", follow_up)
                )
                follow_up_record = cycle_record["tasks"][-1]
                if follow_up.get("status") != "completed":
                    cycle_record["failures"].append("research_follow_up:incomplete")
                if first_record["external_items"] > 0 and follow_up_record[
                    "external_items"
                ] <= 0:
                    cycle_record["failures"].append(
                        "research_follow_up:previous_evidence_not_reused"
                    )
                follow_up_provider_status = follow_up_record[
                    "external_provider_status"
                ]
                if follow_up_provider_status and not any(
                    status == "completed"
                    for status in follow_up_provider_status.values()
                ):
                    cycle_record["failures"].append(
                        "research_follow_up:all_external_providers_failed"
                    )
                follow_up_answer = _answer(follow_up)
                if _contains_any(
                    follow_up_answer,
                    ("当前未获得与", "暂无可核验证据", "未找到可展示的论文"),
                ):
                    cycle_record["failures"].append(
                        "research_follow_up:empty_evidence_answer"
                    )
                switched = await _run_task(
                    client,
                    TOPIC_SWITCH,
                    session_id=session_id,
                    poll_timeout_seconds=poll_timeout_seconds,
                    user_id=user_id,
                )
                cycle_record["tasks"].append(_task_record("topic_switch", switched))
                switched_answer = _answer(switched).casefold()
                if switched.get("status") != "completed":
                    cycle_record["failures"].append("topic_switch:incomplete")
                if "syn+ack" not in switched_answer and "tcp" not in switched_answer:
                    cycle_record["failures"].append("topic_switch:wrong_topic")
                if _contains_any(
                    switched_answer, ("柔性电子", "电子皮肤", "多模态", "智能体")
                ):
                    cycle_record["failures"].append("topic_switch:stale_topic_leak")
        except Exception as exc:  # noqa: BLE001 - soak must continue after research
            cycle_record["failures"].append(
                f"research_conversation:{type(exc).__name__}:{exc}"
            )
    return cycle_record


async def run(args: argparse.Namespace) -> int:
    args.log.parent.mkdir(parents=True, exist_ok=True)
    timeout = httpx.Timeout(30.0, connect=5.0)
    limits = httpx.Limits(max_connections=4, max_keepalive_connections=2)
    started = time.monotonic()
    cycle = 0
    failures = 0
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"),
        timeout=timeout,
        limits=limits,
        trust_env=False,
    ) as client:
        with args.log.open("a", encoding="utf-8") as stream:
            while True:
                cycle += 1
                try:
                    record = await _run_cycle(
                        client,
                        cycle,
                        research_every=args.research_every,
                        poll_timeout_seconds=args.poll_timeout_seconds,
                    )
                except Exception as exc:  # noqa: BLE001 - preserve cycle failure
                    record = {
                        "timestamp": _now(),
                        "cycle": cycle,
                        "tasks": [],
                        "failures": [f"cycle:{type(exc).__name__}:{exc}"],
                    }
                failures += len(record.get("failures", []))
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                stream.flush()
                LOGGER.info(
                    "cycle=%s failures=%s elapsed_s=%.0f",
                    cycle,
                    len(record.get("failures", [])),
                    time.monotonic() - started,
                )
                if args.once or time.monotonic() - started >= args.duration_seconds:
                    break
                await asyncio.sleep(max(0.0, args.interval_seconds))
    return 1 if failures else 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
