"""Run the available full benchmark and produce bounded Phase H summaries."""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.agents import AgentRegistry  # noqa: E402
from app.evaluation.cache import EvaluationCache, evaluation_fingerprint  # noqa: E402
from app.evaluation.contracts import EvaluationCase, SuiteReport  # noqa: E402
from app.evaluation.loader import EvaluationCaseLoader  # noqa: E402
from app.evaluation.reporting import (  # noqa: E402
    evaluation_case_attachment_manifest,
    evaluation_case_catalog_content_sha256,
    evaluation_case_ids_sha256,
    evaluation_case_source_files_sha256,
)
from app.evaluation.runner import EvaluationRunner  # noqa: E402
from app.main import create_app  # noqa: E402

from scripts.run_evaluation import evaluation_settings  # noqa: E402

CASE_ROOT = ROOT / "evaluation" / "cases"
REPORT_ROOT = ROOT / "evaluation" / "reports" / "phase_h"
# Reuse the verified provider-free cache from G where case fingerprints match.
CACHE_ROOT = ROOT / "evaluation" / "cache" / "phase_g"
SUMMARY_PATH = REPORT_ROOT / "summary.json"


def _pass(result: Any) -> bool:
    return result.status in {"passed", "cached"}


def _mean(rows: list[Any], attr: str) -> float:
    return round(sum(float(getattr(row, attr)) for row in rows) / len(rows), 6)


def _group_metrics(rows: Iterable[tuple[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Any]] = defaultdict(list)
    for name, result in rows:
        groups[name].append(result)
    return {
        name: {
            "case_count": len(items),
            "pass_rate": round(sum(_pass(item) for item in items) / len(items), 6),
            "failure_rate": round(
                sum(not _pass(item) for item in items) / len(items), 6
            ),
            "mean_score": _mean(items, "total_score"),
            "mean_latency_ms": _mean(items, "elapsed_ms"),
            "max_latency_ms": max(int(item.elapsed_ms) for item in items),
        }
        for name, items in sorted(groups.items())
    }


def _failure_pattern_key(case: EvaluationCase, result: Any) -> tuple[str, ...]:
    stage = result.failure_stage.value if result.failure_stage else "unknown"
    error_types = "+".join(sorted(error.value for error in result.error_types))
    if not error_types:
        error_types = "none"
    return (
        stage,
        error_types,
        case.course,
        case.task_family,
        case.input_type,
        case.difficulty,
    )


def _failure_patterns(
    cases: list[EvaluationCase], report: SuiteReport
) -> list[dict[str, Any]]:
    case_by_id = {case.case_id: case for case in cases}
    grouped: dict[tuple[str, ...], list[tuple[EvaluationCase, Any]]] = defaultdict(list)
    for result in report.results:
        case = case_by_id.get(result.case_id)
        if case is None or _pass(result):
            continue
        grouped[_failure_pattern_key(case, result)].append((case, result))
    ordered = sorted(
        grouped.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )
    patterns: list[dict[str, Any]] = []
    for index, (key, items) in enumerate(ordered[:20], start=1):
        stage, error_types, course, task_family, input_type, difficulty = key
        patterns.append(
            {
                "pattern_id": f"P{index:02d}",
                "pattern": "+".join(key),
                "case_count": len(items),
                "failure_rate": round(len(items) / len(report.results), 6),
                "severity": (
                    "critical"
                    if stage in {"routing", "course_pack_resolution", "timeout"}
                    else "major"
                ),
                "course": course,
                "task_family": task_family,
                "input_mode": input_type,
                "difficulty": difficulty,
                "failure_stage": stage,
                "failure_codes": (
                    [] if error_types == "none" else error_types.split("+")
                ),
                "examples": sorted(item.case_id for item, _ in items)[:5],
                "owner": stage,
                "generalizable": len(items) > 1,
                "likely_cause": "needs trace-level root-cause review",
            }
        )
    return patterns


def build_summary(cases: list[EvaluationCase], report: SuiteReport) -> dict[str, Any]:
    case_by_id = {case.case_id: case for case in cases}
    pairs = [
        (case_by_id[result.case_id], result)
        for result in report.results
        if result.case_id in case_by_id
    ]
    status_counts = Counter(result.status for _, result in pairs)
    all_results = [result for _, result in pairs]
    return {
        "schema_version": "phase_h_benchmark.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "evidence_level": "synthetic_provider_free",
        "coverage": {
            "available_official_cases": len(cases),
            "executed_cases": len(pairs),
            "roadmap_target_cases": 336,
            "missing_from_current_workspace": max(0, 336 - len(cases)),
            "expanded_500_800_cases": 0,
            "coverage_status": "partial",
            "source_type_counts": dict(
                Counter(case.provenance.source_type for case in cases)
            ),
            "courses": sorted({case.course for case in cases}),
        },
        "overall": {
            "status_counts": dict(sorted(status_counts.items())),
            "pass_rate": round(
                sum(_pass(result) for result in all_results) / len(all_results), 6
            ),
            "mean_score": _mean(all_results, "total_score"),
            "mean_latency_ms": _mean(all_results, "elapsed_ms"),
            "max_latency_ms": max(int(result.elapsed_ms) for result in all_results),
            "cost": {
                "known": False,
                "external_provider_calls": 0,
                "evidence": "offline provider-free run",
            },
        },
        "per_course": _group_metrics((case.course, result) for case, result in pairs),
        "per_task": _group_metrics(
            (case.task_family, result) for case, result in pairs
        ),
        "per_problem_type": _group_metrics(
            (case.problem_type or "unspecified", result) for case, result in pairs
        ),
        "per_input_mode": _group_metrics(
            (case.input_type, result) for case, result in pairs
        ),
        "per_agent_capability": _group_metrics(
            (case.expected_agent, result) for case, result in pairs
        ),
        "per_difficulty": _group_metrics(
            (case.difficulty, result) for case, result in pairs
        ),
        "top_failure_patterns": _failure_patterns(cases, report),
        "top_latency_bottlenecks": sorted(
            (
                {"dimension": name, **metrics}
                for name, metrics in _group_metrics(
                    (case.course, result) for case, result in pairs
                ).items()
            ),
            key=lambda item: (-item["mean_latency_ms"], item["dimension"]),
        )[:10],
        "governance": {
            "scorer_modified": False,
            "test_cases_deleted": False,
            "agent_or_runtime_modified": False,
            "answers_retained": False,
        },
        "report_path": str(REPORT_ROOT / "latest.json"),
    }


async def run() -> int:
    loader = EvaluationCaseLoader(CASE_ROOT)
    cases = loader.load_all()
    registry = AgentRegistry()
    for case in cases:
        registry.get(case.expected_agent)
    attachment_sha, attachment_count = evaluation_case_attachment_manifest(
        cases, CASE_ROOT
    )
    app = create_app(evaluation_settings(live=False))
    cache = EvaluationCache(CACHE_ROOT, fingerprint=evaluation_fingerprint(ROOT))
    async with EvaluationRunner(
        app,
        mode="offline",
        cache=cache,
        report_root=REPORT_ROOT,
        use_cache=True,
    ) as runner:
        report = await runner.run_suite(
            cases,
            filters={
                "phase": "H",
                "mode": "offline",
                "selection": "all_available_official_cases_v1",
            },
            case_catalog_sha256=evaluation_case_ids_sha256(
                case.case_id for case in cases
            ),
            case_catalog_content_sha256=evaluation_case_catalog_content_sha256(cases),
            case_source_files_sha256=evaluation_case_source_files_sha256(CASE_ROOT),
            case_attachment_manifest_sha256=attachment_sha,
            case_attachment_count=attachment_count,
            case_attachment_root=CASE_ROOT,
        )
    summary = build_summary(cases, report)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary["overall"], ensure_ascii=False, indent=2))
    print(f"summary={SUMMARY_PATH}")
    print(f"report={REPORT_ROOT / 'latest.json'}")
    return 1 if report.summary.get("errors") or report.summary.get("timeouts") else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
