from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.agents import AgentRegistry  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.courses import default_course_registry  # noqa: E402
from app.evaluation.cache import EvaluationCache, evaluation_fingerprint  # noqa: E402
from app.evaluation.contracts import EvaluationCase  # noqa: E402
from app.evaluation.loader import EvaluationCaseLoader  # noqa: E402
from app.evaluation.runner import EvaluationRunner  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.model_registry import ModelRegistry  # noqa: E402

CASE_ROOT = ROOT / "evaluation" / "cases"
REPORT_ROOT = ROOT / "evaluation" / "reports"
CACHE_ROOT = ROOT / "evaluation" / "cache"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="芯智导学多学科正式执行链评测")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--validate-only", action="store_true")
    modes.add_argument("--offline", action="store_true")
    modes.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-paid", action="store_true")
    parser.add_argument("--course")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--case-id")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--rerun-failed", action="store_true")
    return parser.parse_args(argv)


def validate_paid_guard(args: argparse.Namespace) -> None:
    if args.live and not args.confirm_paid:
        raise ValueError("--live 必须同时提供 --confirm-paid，未发送任何模型请求")
    if args.confirm_paid and not args.live:
        raise ValueError("--confirm-paid 只能与 --live 一起使用")
    if args.max_cases is not None and args.max_cases < 1:
        raise ValueError("--max-cases 必须为正整数")


def validate_cases(
    args: argparse.Namespace,
) -> tuple[list[EvaluationCase], dict[str, object]]:
    loader = EvaluationCaseLoader(CASE_ROOT)
    all_cases = loader.load_all()
    selected = loader.filter(
        all_cases,
        course=args.course,
        tags=set(args.tag),
        case_id=args.case_id,
        max_cases=(3 if args.live and args.max_cases is None else args.max_cases),
    )
    if not selected:
        raise ValueError("筛选后没有评测案例")
    registry = AgentRegistry()
    courses = default_course_registry()
    model_registry = ModelRegistry(Settings(_env_file=None))
    errors = list(model_registry.errors)
    for case in selected:
        registry.get(case.expected_agent)
        if case.expected_course_pack:
            courses.get(case.expected_course_pack)
    summary: dict[str, object] = {
        "valid": not errors,
        "total_cases": len(all_cases),
        "selected_cases": len(selected),
        "courses": sorted({case.course for case in selected}),
        "registry_errors": errors,
        "sends_api_requests": False,
    }
    return selected, summary


def evaluation_settings(*, live: bool) -> Settings:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    database = CACHE_ROOT / ("live-evaluation.db" if live else "offline-evaluation.db")
    common: dict[str, Any] = {
        "app_env": "test",
        "test_database_url": f"sqlite+aiosqlite:///{database}",
        "model_max_retries": 0,
        "local_storage_path": CACHE_ROOT / "storage",
        "log_level": "WARNING",
    }
    if live:
        return Settings(**common)
    return Settings(
        **common,
        default_agent_provider="mock",
        allow_mock_fallback=True,
        allow_agent_mocks=True,
        xingchen_enabled=False,
        enable_xingchen_fallback=False,
        iflytek_spark_enabled=False,
        dashscope_enabled=False,
        enable_spark_reasoner=False,
        enable_qwen_text_fast=False,
        enable_qwen_vision_fast=False,
        enable_qwen_vision_primary=False,
        rag_enabled=False,
        _env_file=None,
    )


async def run(args: argparse.Namespace) -> int:
    validate_paid_guard(args)
    raw_cases, validation = validate_cases(args)
    if args.validate_only:
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 0 if validation["valid"] else 1
    cases = list(raw_cases)
    mode = "live" if args.live else "offline"
    app = create_app(evaluation_settings(live=args.live))
    cache = EvaluationCache(
        CACHE_ROOT,
        fingerprint=evaluation_fingerprint(ROOT),
    )
    filters = {
        "course": args.course,
        "tags": args.tag,
        "case_id": args.case_id,
        "max_cases": 3 if args.live and args.max_cases is None else args.max_cases,
    }
    async with EvaluationRunner(
        app,
        mode=mode,
        cache=cache,
        report_root=REPORT_ROOT,
        use_cache=not args.no_cache,
        rerun_failed=args.rerun_failed,
    ) as runner:
        report = await runner.run_suite(cases, filters=filters)
    print(json.dumps(report.summary, ensure_ascii=False, indent=2))
    print(f"json_report={REPORT_ROOT / 'latest.json'}")
    print(f"markdown_report={REPORT_ROOT / 'latest.md'}")
    return 1 if report.summary["errors"] or report.summary["timeouts"] else 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return asyncio.run(run(args))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
