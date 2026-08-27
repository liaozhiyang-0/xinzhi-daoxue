from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.agents import AgentRegistry  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.courses import default_course_registry  # noqa: E402
from app.evaluation.cache import EvaluationCache, evaluation_fingerprint  # noqa: E402
from app.evaluation.contracts import EvaluationCase, EvaluationMode  # noqa: E402
from app.evaluation.loader import EvaluationCaseLoader  # noqa: E402
from app.evaluation.reporting import (  # noqa: E402
    evaluation_case_attachment_manifest,
    evaluation_case_catalog_content_sha256,
    evaluation_case_ids_sha256,
    evaluation_case_source_files_sha256,
)
from app.evaluation.runner import EvaluationRunner  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.model_registry import ModelRegistry  # noqa: E402

CASE_ROOT = ROOT / "evaluation" / "cases"
REPORT_ROOT = ROOT / "evaluation" / "reports"
CACHE_ROOT = ROOT / "evaluation" / "cache"
MIGRATION_ROOT = ROOT / "apps" / "api" / "alembic" / "versions"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="芯智导学多学科正式执行链评测")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--validate-only", action="store_true")
    modes.add_argument("--offline", action="store_true")
    modes.add_argument("--live", action="store_true")
    parser.add_argument(
        "--mode",
        choices=(
            "local_deterministic",
            "local_mock",
            "real_model",
        ),
    )
    parser.add_argument(
        "--suite",
        choices=(
            "academic_solver",
            "expanded_benchmark_v2",
            "knowledge_qa",
            "learning_loop",
            "task_reliability",
            "boundary",
        ),
    )
    parser.add_argument("--confirm-paid", action="store_true")
    parser.add_argument("--course")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--case-id")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--rerun-failed", action="store_true")
    return parser.parse_args(argv)


def validate_paid_guard(args: argparse.Namespace) -> None:
    paid = args.live or args.mode in {"real_model"}
    if paid and not args.confirm_paid:
        raise ValueError("真实模型模式必须同时提供 --confirm-paid，未发送任何模型请求")
    if args.confirm_paid and not paid:
        raise ValueError("--confirm-paid 只能与真实模型模式一起使用")
    if args.max_cases is not None and args.max_cases < 1:
        raise ValueError("--max-cases 必须为正整数")


def validate_cases(
    args: argparse.Namespace,
) -> tuple[list[EvaluationCase], dict[str, object]]:
    loader = EvaluationCaseLoader(CASE_ROOT / args.suite if args.suite else CASE_ROOT)
    case_source_root = CASE_ROOT / args.suite if args.suite else CASE_ROOT
    all_cases = loader.load_all()
    selected = loader.filter(
        all_cases,
        course=args.course,
        tags=set(args.tag),
        case_id=args.case_id,
        max_cases=(
            3
            if (args.live or args.mode in {"real_model"})
            and args.max_cases is None
            else args.max_cases
        ),
    )
    if not selected:
        raise ValueError("筛选后没有评测案例")
    registry = AgentRegistry()
    courses = default_course_registry()
    model_registry = ModelRegistry(Settings(_env_file=None))  # type: ignore[call-arg]
    errors = list(model_registry.errors)
    for case in selected:
        registry.get(case.expected_agent)
        if case.expected_course_pack:
            courses.get(case.expected_course_pack)
    attachment_manifest_errors: list[str] = []
    attachment_manifest_sha256 = ""
    attachment_count = 0
    try:
        attachment_manifest_sha256, attachment_count = (
            evaluation_case_attachment_manifest(all_cases, case_source_root)
        )
    except ValueError as exc:
        attachment_manifest_errors.append(str(exc))
    summary: dict[str, object] = {
        "valid": not errors and not attachment_manifest_errors,
        "total_cases": len(all_cases),
        "selected_cases": len(selected),
        "case_catalog_sha256": evaluation_case_ids_sha256(
            item.case_id for item in all_cases
        ),
        "case_catalog_content_sha256": evaluation_case_catalog_content_sha256(
            all_cases
        ),
        "case_source_files_sha256": evaluation_case_source_files_sha256(
            case_source_root
        ),
        "case_attachment_manifest_sha256": attachment_manifest_sha256,
        "case_attachment_count": attachment_count,
        "attachment_manifest_errors": attachment_manifest_errors,
        "courses": sorted({case.course for case in selected}),
        "registry_errors": errors,
        "sends_api_requests": False,
    }
    return selected, summary


def _evaluation_schema_revision() -> str:
    revisions = sorted(path.stem for path in MIGRATION_ROOT.glob("*.py"))
    if not revisions:
        raise ValueError("未找到数据库 migration，无法创建隔离评测库")
    return revisions[-1].split("_", maxsplit=1)[0]


def evaluation_settings(*, live: bool) -> Settings:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    mode_name = "live" if live else "offline"
    database = CACHE_ROOT / f"{mode_name}-evaluation-{_evaluation_schema_revision()}.db"
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
        iflytek_spark_enabled=False,
        dashscope_enabled=False,
        enable_spark_reasoner=False,
        enable_qwen_text_fast=False,
        enable_qwen_vision_fast=False,
        enable_qwen_vision_primary=False,
        enable_qwen_brief=False,
        rag_enabled=False,
        _env_file=None,  # type: ignore[call-arg]
    )


async def run(args: argparse.Namespace) -> int:
    validate_paid_guard(args)
    raw_cases, validation = validate_cases(args)
    if args.validate_only:
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 0 if validation["valid"] else 1
    if not validation["valid"]:
        raise ValueError("评测案例校验失败，请先使用 --validate-only 查看具体错误")
    cases = list(raw_cases)
    case_source_root = CASE_ROOT / args.suite if args.suite else CASE_ROOT
    mode = cast(EvaluationMode, args.mode or ("live" if args.live else "offline"))
    live = mode in {"live", "real_model"}
    app = create_app(evaluation_settings(live=live))
    cache = EvaluationCache(
        CACHE_ROOT,
        fingerprint=evaluation_fingerprint(ROOT),
    )
    filters = {
        "course": args.course,
        "tags": args.tag,
        "case_id": args.case_id,
        "max_cases": 3 if args.live and args.max_cases is None else args.max_cases,
        "suite": args.suite,
        "mode": mode,
    }
    case_attachment_count = validation.get("case_attachment_count", 0)
    if not isinstance(case_attachment_count, int):
        raise ValueError("评测附件数量必须是整数")
    async with EvaluationRunner(
        app,
        mode=mode,
        cache=cache,
        report_root=REPORT_ROOT,
        use_cache=not args.no_cache,
        rerun_failed=args.rerun_failed,
    ) as runner:
        report = await runner.run_suite(
            cases,
            filters=filters,
            case_catalog_sha256=str(validation["case_catalog_sha256"]),
            case_catalog_content_sha256=str(
                validation["case_catalog_content_sha256"]
            ),
            case_source_files_sha256=str(validation["case_source_files_sha256"]),
            case_attachment_manifest_sha256=str(
                validation["case_attachment_manifest_sha256"]
            ),
            case_attachment_count=case_attachment_count,
            case_attachment_root=case_source_root,
        )
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
