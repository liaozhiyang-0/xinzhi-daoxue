from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "api"))

from analyze_evaluation_report import (  # noqa: E402
    build_output,
    load_json,
    write_outputs,
)
from app.agents import AgentRegistry  # noqa: E402
from app.courses import default_course_registry  # noqa: E402
from app.evaluation.cache import (  # noqa: E402
    EvaluationCache,
    evaluation_fingerprint,
)
from app.evaluation.contracts import (  # noqa: E402
    EvaluationCase,
    EvaluationResult,
    SuiteReport,
)
from app.evaluation.reporting import build_statistics, write_report  # noqa: E402
from app.evaluation.runner import EvaluationRunner  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.model_registry import ModelRegistry  # noqa: E402

from scripts.run_evaluation import evaluation_settings  # noqa: E402

DEFAULT_CASES = ROOT / "统一格式" / "balanced_336" / "all_cases.json"
DEFAULT_CONFIG = ROOT / "evaluation_metrics.json"
DEFAULT_REPORTS = ROOT / "统一格式" / "evaluation_reports"
DEFAULT_CACHE = ROOT / "统一格式" / "evaluation_cache"
DEFAULT_MANUAL_JUDGEMENTS = ROOT / "manual_judgements.json"
JUDGE_PROMPT_VERSION = "xzd_simple_answer_judge_v3"


class RealQuestionEvaluationRunner(EvaluationRunner):
    """EvaluationRunner adapter that uploads local question images first."""

    async def _execute(self, case: EvaluationCase, trace_id: str) -> dict[str, Any]:
        assert self.client is not None
        evaluation_controls = {
            key: value
            for key, value in case.task_options.items()
            if key.startswith("_evaluation_")
        }
        task_options = {
            key: value
            for key, value in case.task_options.items()
            if not key.startswith("_evaluation_")
        }
        session_response = await self.client.post(
            "/api/v1/sessions",
            json={
                "user_id": "real-benchmark-user",
                "course_id": case.course,
                "title": f"Real benchmark {case.case_id}",
            },
        )
        session_response.raise_for_status()

        attachments: list[dict[str, Any]] = []
        for ref in case.file_refs:
            local_path = ROOT / str(ref["path"])
            media_type = str(ref.get("media_type") or "application/octet-stream")
            upload_response = await self.client.post(
                "/api/v1/files",
                data={"purpose": "student_solver_image"},
                files={
                    "upload": (
                        local_path.name,
                        local_path.read_bytes(),
                        media_type,
                    )
                },
            )
            upload_response.raise_for_status()
            attachments.append(self._attachment_from_upload(upload_response.json()))

        canonical = {"text": case.message, **case.structured_input}
        task_response = await self.client.post(
            "/api/v1/tasks",
            json={
                "session_id": session_response.json()["id"],
                "user_id": "real-benchmark-user",
                "user_role": "student",
                "scene": "solving",
                "course_id": case.course,
                "intent": case.intent,
                "canonical_input": canonical,
                "attachments": attachments,
                "context_refs": [],
                "options": {
                    "request_id": trace_id,
                    "trace_id": trace_id,
                    "input_type": case.input_type,
                    "evaluation_case_id": case.case_id,
                    "evaluation_mode": self.mode,
                    "allow_cloud": self.mode in {"live", "real_model", "real_xingchen"},
                    **task_options,
                },
            },
        )
        task_response.raise_for_status()
        task = task_response.json()
        while task["status"] not in {"completed", "failed", "cancelled"}:
            await asyncio.sleep(0.2)
            response = await self.client.get(
                f"/api/v1/tasks/{task['id']}?user_id=real-benchmark-user"
            )
            response.raise_for_status()
            task = response.json()

        actions = evaluation_controls.get("_evaluation_follow_up_actions", [])
        for index, item in enumerate(actions if isinstance(actions, list) else []):
            action = item if isinstance(item, str) else str(item.get("action", ""))
            student_answer = (
                "" if isinstance(item, str) else str(item.get("student_answer", ""))
            )
            action_response = await self.client.post(
                "/api/v1/learning/actions",
                json={
                    "source_task_id": task["id"],
                    "user_id": "real-benchmark-user",
                    "action": action,
                    "idempotency_key": (f"{trace_id}_{case.case_id}_{index}_{action}")[
                        :128
                    ],
                    "student_answer": student_answer,
                    "payload": {},
                },
            )
            action_response.raise_for_status()
            response = await self.client.get(
                f"/api/v1/tasks/{task['id']}?user_id=real-benchmark-user"
            )
            response.raise_for_status()
            task = response.json()

        if evaluation_controls.get("_evaluation_cross_user_check"):
            response = await self.client.get(
                f"/api/v1/tasks/{task['id']}?user_id=another-evaluation-user"
            )
            task["_evaluation_cross_user_isolated"] = response.status_code in {
                403,
                404,
            }
        return task

    @staticmethod
    def _attachment_from_upload(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "file_id": payload.get("id"),
            "filename": payload.get("filename"),
            "content_type": payload.get("content_type"),
            "size_bytes": payload.get("size_bytes"),
            "storage_key": payload.get("storage_key"),
            "checksum_sha256": payload.get("checksum_sha256"),
            "provider_file_id": None,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="六门课程336题一体化执行、判分、断点续跑与指标汇总"
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--validate-only", action="store_true")
    modes.add_argument("--offline", action="store_true")
    modes.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-paid", action="store_true")
    parser.add_argument("--judge-answers", action="store_true")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--manual-judgements",
        type=Path,
        default=DEFAULT_MANUAL_JUDGEMENTS,
    )
    parser.add_argument("--course", action="append", default=[])
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--rerun-failed", action="store_true")
    parser.add_argument("--run-name")
    parser.add_argument("--checkpoint-every", type=int, default=1)
    parser.add_argument("--judge-pass-threshold", type=float, default=0.8)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.live and not args.confirm_paid:
        raise ValueError("--live 必须同时提供 --confirm-paid")
    if args.confirm_paid and not args.live:
        raise ValueError("--confirm-paid 只能与 --live 一起使用")
    if args.judge_answers and not args.live:
        raise ValueError("--judge-answers 只允许在 --live 模式使用")
    if args.max_cases is not None and args.max_cases < 1:
        raise ValueError("--max-cases 必须为正整数")
    if args.checkpoint_every < 1:
        raise ValueError("--checkpoint-every 必须为正整数")
    if not 0 <= args.judge_pass_threshold <= 1:
        raise ValueError("--judge-pass-threshold 必须位于0到1之间")


def load_cases(path: Path) -> list[EvaluationCase]:
    payload = load_json(path)
    raw_cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(raw_cases, list):
        raise ValueError(f'{path}: 顶层必须为 {{"cases": [...]}}')
    return [EvaluationCase.model_validate(item) for item in raw_cases]


def select_cases(
    cases: list[EvaluationCase], args: argparse.Namespace
) -> list[EvaluationCase]:
    courses = {str(item).upper() for item in args.course}
    case_ids = {str(item) for item in args.case_id}
    selected = [
        case
        for case in cases
        if (not courses or case.course in courses)
        and (not case_ids or case.case_id in case_ids)
    ]
    return selected[: args.max_cases] if args.max_cases is not None else selected


def case_is_standard_answer(case: EvaluationCase, config: dict[str, Any]) -> bool:
    role = str(case.structured_input.get("balanced_suite_role") or "")
    tags = set(case.tags)
    rule = config["cohorts"]["standard_answer"]
    return role in set(rule["balanced_suite_roles"]) and not (
        set(rule.get("excluded_tags") or []) & tags
    )


def validate_suite(
    cases: list[EvaluationCase],
    config: dict[str, Any],
    *,
    live: bool,
    judge_answers: bool,
) -> dict[str, Any]:
    if not cases:
        raise ValueError("筛选后没有评测案例")
    registry = AgentRegistry()
    courses = default_course_registry()
    missing_files: list[str] = []
    for case in cases:
        registry.get(case.expected_agent)
        if case.expected_course_pack:
            courses.get(case.expected_course_pack)
        for ref in case.file_refs:
            path = ROOT / str(ref["path"])
            if not path.is_file():
                missing_files.append(f"{case.case_id}:{ref['path']}")
    if missing_files:
        raise ValueError(f"缺少题图文件: {missing_files[:10]}")

    settings = evaluation_settings(live=live)
    model_registry = ModelRegistry(settings)
    if model_registry.errors:
        raise ValueError("模型注册表校验失败: " + "; ".join(model_registry.errors))
    standard_answers = sum(case_is_standard_answer(case, config) for case in cases)
    return {
        "valid": True,
        "selected_cases": len(cases),
        "courses": sorted({case.course for case in cases}),
        "question_images": sum(len(case.file_refs) for case in cases),
        "standard_answer_cases": standard_answers,
        "answer_judge_calls_planned": standard_answers if judge_answers else 0,
        "live": live,
        "sends_api_requests": False,
        "cache_enabled": True,
    }


def report_summary(results: list[EvaluationResult]) -> dict[str, Any]:
    passed = sum(item.status == "passed" for item in results)
    return {
        "total": len(results),
        "passed": passed,
        "failed": sum(item.status == "failed" for item in results),
        "errors": sum(item.status == "error" for item in results),
        "timeouts": sum(item.status == "timeout" for item in results),
        "cached": sum("result_loaded_from_cache" in item.warnings for item in results),
        "pass_rate": passed / len(results) if results else 0.0,
    }


def judge_summary(results: list[EvaluationResult], planned: int) -> dict[str, Any]:
    judgements: list[dict[str, Any]] = []
    for result in results:
        judgement = result.actual.get("answer_evaluation")
        if isinstance(judgement, dict):
            judgements.append(judgement)
    usage_values: list[dict[str, Any]] = []
    for judgement in judgements:
        usage = judgement.get("usage")
        if isinstance(usage, dict):
            usage_values.append(usage)
    return {
        "planned": planned,
        "available": len(judgements),
        "unavailable": max(0, planned - len(judgements)),
        "cached": sum(bool(item.get("cached")) for item in judgements),
        "passed": sum(item.get("passed") is True for item in judgements),
        "known_total_tokens": sum(
            int(usage["total_tokens"])
            for usage in usage_values
            if isinstance(usage.get("total_tokens"), int)
        ),
        "calls_with_known_tokens": sum(
            isinstance(usage.get("total_tokens"), int) for usage in usage_values
        ),
    }


def build_report(
    cases: list[EvaluationCase],
    results: list[EvaluationResult],
    *,
    mode: Literal["offline", "live"],
    started_at: str,
    filters: dict[str, Any],
) -> SuiteReport:
    return SuiteReport(
        mode=mode,
        started_at=started_at,
        completed_at=datetime.now(UTC).isoformat(),
        filters=filters,
        summary=report_summary(results),
        statistics=build_statistics(cases[: len(results)], results),
        results=results,
        estimated_cost=None,
    )


def answer_judge_cache_key(case: EvaluationCase, answer: str) -> str:
    payload = {
        "version": JUDGE_PROMPT_VERSION,
        "case_id": case.case_id,
        "question": case.message,
        "reference_answer": case.reference_answer,
        "answer": answer,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def answer_sha256(answer: str) -> str:
    return hashlib.sha256(answer.encode("utf-8")).hexdigest()


def load_manual_judgements(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    payload = load_json(path)
    reviews = payload.get("reviews") if isinstance(payload, dict) else None
    if not isinstance(reviews, list):
        raise ValueError(f"{path}: 顶层必须包含 reviews 数组")
    return [item for item in reviews if isinstance(item, dict)]


def matching_manual_judgement(
    case: EvaluationCase,
    result: EvaluationResult,
    reviews: list[dict[str, Any]],
) -> dict[str, Any] | None:
    digest = answer_sha256(str(result.actual.get("answer") or ""))
    for review in reviews:
        if (
            str(review.get("case_id")) == case.case_id
            and str(review.get("answer_sha256")) == digest
        ):
            return {
                "passed": review.get("passed") is True,
                "score": float(review.get("score", 0)),
                "judge": "hybrid",
                "reference_used": True,
                "reason": str(review.get("reason") or "人工简判"),
                "verdict": str(review.get("verdict") or "unjudgeable"),
                "review_method": "hash_bound_simple_review",
                "reviewed_at": review.get("reviewed_at"),
                "cached": True,
            }
    return None


def load_judge_cache(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def parse_simple_judge(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if text.startswith("```"):
        text = text.removeprefix("```text").removeprefix("```")
        text = text.removesuffix("```").strip()
    verdict_match = re.search(
        r"(?im)^\s*VERDICT\s*[:=]\s*"
        r"(correct|partial|incorrect|unjudgeable)\s*$",
        text,
    )
    if verdict_match is None:
        return None
    verdict = verdict_match.group(1).lower()
    score_match = re.search(
        r"(?im)^\s*SCORE\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*$",
        text,
    )
    if score_match is None:
        score = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}.get(verdict, 0.0)
    else:
        score = float(score_match.group(1))
        if score > 1:
            score /= 100
        score = min(1.0, max(0.0, score))
    reason_match = re.search(r"(?im)^\s*REASON\s*[:=]\s*(.+)$", text)
    reason = (
        reason_match.group(1).strip()[:500]
        if reason_match is not None
        else "模型未提供简短判分理由。"
    )
    return {"verdict": verdict, "score": score, "reason": reason}


def judgement_passed(
    verdict: str,
    score: float,
    *,
    pass_threshold: float,
) -> bool:
    """Accept high-confidence partials without turning real errors into passes."""

    normalized = verdict.strip().casefold()
    return score >= pass_threshold and normalized in {"correct", "partial"}


async def judge_answer(
    app: Any,
    case: EvaluationCase,
    result: EvaluationResult,
    *,
    cache_root: Path,
    pass_threshold: float,
) -> dict[str, Any] | None:
    answer = str(result.actual.get("answer") or "").strip()
    if not answer:
        return None
    cache_path = cache_root / f"{answer_judge_cache_key(case, answer)}.json"
    cached = load_judge_cache(cache_path)
    if cached is not None:
        return {**cached, "cached": True}

    prompt = (
        "你是工科课程答案简易判分器。优先比较最终结论、关键数值、符号、"
        "单位和必要前提；允许数学等价写法、分段式与统一式互换、变量名称"
        "差异、合理舍入和不影响结论的格式差异。所有实质结论正确时判为"
        "correct，不得仅因未复刻参考答案版式或缺少非必要展开而降级。若核心"
        "结论正确但漏答题目明确要求的一个组成部分，判为partial并按完整度"
        "给分；若最终结论、关键方向、拓扑或数值明确不一致，判为incorrect；"
        "参考答案或题目不足以判断时返回unjudgeable。\n\n"
        "必须严格只输出下面三行英文键，不要JSON，不要Markdown，不要增加"
        "其他字段：\n"
        "VERDICT=correct|partial|incorrect|unjudgeable\n"
        "SCORE=0到1之间的小数\n"
        "REASON=不超过100字的中文理由\n\n"
        f"课程：{case.course}\n"
        f"题目：{case.message}\n\n"
        f"参考答案：{case.reference_answer}\n\n"
        f"候选答案：{answer}"
    )
    request_id = f"answer_judge_{case.case_id}"
    try:
        response = await app.state.model_service.generate_for_task(
            "structured_output_normalization",
            messages=[
                {
                    "role": "system",
                    "content": "严格、保守地判定工科答案是否实质正确。",
                },
                {"role": "user", "content": prompt},
            ],
            request_id=request_id,
            extra_options={"temperature": 0, "max_tokens": 300},
        )
        parsed = parse_simple_judge(response.content)
        if parsed is None:
            raise ValueError("判分模型未按三行简易协议返回")
    except Exception as exc:
        print(
            f"[judge unavailable] {case.case_id}: "
            f"{type(exc).__name__}: {str(exc)[:160]}",
            flush=True,
        )
        return None

    judgement = {
        "passed": judgement_passed(
            parsed["verdict"],
            parsed["score"],
            pass_threshold=pass_threshold,
        ),
        "score": parsed["score"],
        "judge": "hybrid",
        "reference_used": True,
        "reason": parsed["reason"],
        "verdict": parsed["verdict"],
        "review_method": "simple_three_line_model_judge",
        "prompt_version": JUDGE_PROMPT_VERSION,
        "provider": response.provider,
        "model": response.model,
        "elapsed_ms": response.elapsed_ms,
        "usage": (
            response.usage.model_dump(exclude_none=True)
            if response.usage is not None
            else None
        ),
        "cached": False,
    }
    await asyncio.to_thread(cache_root.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(
        cache_path.write_text,
        json.dumps(judgement, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return judgement


async def run_benchmark(
    args: argparse.Namespace,
    cases: list[EvaluationCase],
    config: dict[str, Any],
) -> int:
    mode: Literal["offline", "live"] = "live" if args.live else "offline"
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_name = args.run_name or f"full_{mode}_{timestamp}"
    run_root = DEFAULT_REPORTS / run_name
    raw_root = run_root / "raw"
    metrics_root = run_root / "metrics"
    cache_root = DEFAULT_CACHE / "execution"
    judge_cache_root = DEFAULT_CACHE / "answer_judges"
    run_root.mkdir(parents=True, exist_ok=False)

    settings = evaluation_settings(live=args.live)
    manual_judgements = load_manual_judgements(args.manual_judgements.resolve())
    app = create_app(settings)
    cache = EvaluationCache(
        cache_root,
        fingerprint=evaluation_fingerprint(PROJECT_ROOT),
    )
    filters = {
        "cases": str(args.cases.resolve()),
        "course": args.course,
        "case_id": args.case_id,
        "max_cases": args.max_cases,
        "judge_answers": args.judge_answers,
        "judge_pass_threshold": args.judge_pass_threshold,
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "manual_judgements": str(args.manual_judgements.resolve()),
        "run_name": run_name,
    }
    started_at = datetime.now(UTC).isoformat()
    results: list[EvaluationResult] = []
    wall_started = perf_counter()

    async with RealQuestionEvaluationRunner(
        app,
        mode=mode,
        cache=cache,
        report_root=raw_root,
        use_cache=not args.no_cache,
        rerun_failed=args.rerun_failed,
    ) as runner:
        for index, case in enumerate(cases, start=1):
            case_started = perf_counter()
            result = await runner.run_case(case)
            if args.judge_answers and case_is_standard_answer(case, config):
                judgement = matching_manual_judgement(case, result, manual_judgements)
                if judgement is None:
                    judgement = await judge_answer(
                        app,
                        case,
                        result,
                        cache_root=judge_cache_root,
                        pass_threshold=args.judge_pass_threshold,
                    )
                if judgement is not None:
                    result = result.model_copy(
                        update={
                            "actual": {
                                **result.actual,
                                "answer_evaluation": judgement,
                            }
                        }
                    )
            results.append(result)
            elapsed = perf_counter() - case_started
            cached = "result_loaded_from_cache" in result.warnings
            print(
                f"[{index:03d}/{len(cases):03d}] {case.case_id} "
                f"{result.status} {elapsed:.1f}s"
                f"{' cached' if cached else ''}",
                flush=True,
            )
            if index % args.checkpoint_every == 0 or index == len(cases):
                checkpoint = build_report(
                    cases,
                    results,
                    mode=mode,
                    started_at=started_at,
                    filters=filters,
                )
                write_report(checkpoint, raw_root)

    report = build_report(
        cases,
        results,
        mode=mode,
        started_at=started_at,
        filters=filters,
    )
    json_path, markdown_path = write_report(report, raw_root)
    summary, rows, visualization = build_output(
        [case.model_dump(mode="json") for case in cases],
        [result.model_dump(mode="json") for result in results],
        config,
        report.model_dump(mode="json"),
    )
    write_outputs(metrics_root, summary, rows, visualization)
    planned_judgements = (
        sum(case_is_standard_answer(case, config) for case in cases)
        if args.judge_answers
        else 0
    )
    manifest = {
        "schema_version": "1.0",
        "run_name": run_name,
        "mode": mode,
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "wall_elapsed_seconds": round(perf_counter() - wall_started, 3),
        "selected_cases": len(cases),
        "judge_answers": args.judge_answers,
        "raw_report": str(json_path),
        "markdown_report": str(markdown_path),
        "metrics_summary": str(metrics_root / "metrics_summary.json"),
        "case_metrics": str(metrics_root / "case_metrics.csv"),
        "visualization_data": str(metrics_root / "visualization_data.json"),
        "summary": report.summary,
        "answer_judge_summary": judge_summary(results, planned_judgements),
    }
    (run_root / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 1 if report.summary["errors"] or report.summary["timeouts"] else 0


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
        config = load_json(args.config.resolve())
        cases = select_cases(load_cases(args.cases.resolve()), args)
        validation = validate_suite(
            cases,
            config,
            live=args.live,
            judge_answers=args.judge_answers,
        )
        if args.validate_only:
            print(json.dumps(validation, ensure_ascii=False, indent=2))
            return 0
        return asyncio.run(run_benchmark(args, cases, config))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
