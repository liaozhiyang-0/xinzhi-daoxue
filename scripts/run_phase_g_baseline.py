"""Run the bounded Phase G provider-free baseline.

This is a thin orchestration layer over the existing evaluation runner.  It
does not call a provider in offline mode and does not change scoring rules.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections import Counter, defaultdict
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
REPORT_ROOT = ROOT / "evaluation" / "reports" / "phase_g"
CACHE_ROOT = ROOT / "evaluation" / "cache" / "phase_g"
BASELINE_PATH = ROOT / "evaluation" / "baselines" / "agentic_v1_real_baseline.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the bounded Phase G baseline")
    parser.add_argument("--max-cases", type=int, default=40)
    parser.add_argument("--output", type=Path, default=BASELINE_PATH)
    parser.add_argument("--no-cache", action="store_true")
    return parser.parse_args()


def _case_sort_key(case: EvaluationCase) -> tuple[str, str, str, str, str]:
    return (
        case.course,
        case.task_family,
        case.input_type,
        case.difficulty,
        case.case_id,
    )


def select_representative_cases(
    cases: list[EvaluationCase], max_cases: int
) -> list[EvaluationCase]:
    """Prefer one case per observable course/task/input group, then fill gaps."""

    if max_cases < 1:
        raise ValueError("--max-cases must be positive")
    ordered = sorted(cases, key=_case_sort_key)
    groups: dict[tuple[str, str, str], list[EvaluationCase]] = defaultdict(list)
    for case in ordered:
        groups[(case.course, case.task_family, case.input_type)].append(case)

    selected: list[EvaluationCase] = []
    for key in sorted(groups):
        if len(selected) >= max_cases:
            break
        selected.append(groups[key][0])

    for case in ordered:
        if len(selected) >= max_cases:
            break
        if case.case_id not in {item.case_id for item in selected}:
            selected.append(case)
    return selected


def _sha256_case_ids(cases: list[EvaluationCase]) -> str:
    return hashlib.sha256(
        "\n".join(item.case_id for item in cases).encode("utf-8")
    ).hexdigest()


def _metric_value(metrics: dict[str, Any], *names: str) -> int | float | None:
    for name in names:
        value = metrics.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return None


def _record(case: EvaluationCase, result: Any) -> dict[str, Any]:
    actual = result.actual if isinstance(result.actual, dict) else {}
    summary = actual.get("execution_summary")
    summary = summary if isinstance(summary, dict) else {}
    metrics = actual.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    route = actual.get("route")
    route = route if isinstance(route, dict) else summary.get("route", {})
    failure_stage = result.failure_stage
    return {
        "case_id": case.case_id,
        "course": case.course,
        "task_type": case.task_family,
        "input_mode": case.input_type,
        "provider": str(
            summary.get("provider") or metrics.get("provider_used") or "offline"
        ),
        "model": str(metrics.get("model") or "not_applicable"),
        "model_version": "not_applicable",
        "prompt_version": "repository_current",
        "planner_version": "repository_current",
        "skill_version": "repository_current",
        "rag_version": "repository_current",
        "tool_version": "repository_current",
        "reflection_enabled": bool(metrics.get("reflection_enabled", False)),
        "experience_enabled": bool(metrics.get("memory_enabled", False)),
        "latency_ms": result.elapsed_ms,
        "tokens": {
            "input": _metric_value(metrics, "input_tokens"),
            "output": _metric_value(metrics, "output_tokens"),
        },
        "cost": None,
        "answer": "not_retained",
        "score": result.total_score,
        "status": result.status,
        "failure_stage": failure_stage.value if failure_stage else None,
        "route": route,
        "evidence_level": "synthetic_provider_free",
    }


def build_baseline(
    report: SuiteReport,
    cases: list[EvaluationCase],
    available_cases: list[EvaluationCase],
) -> dict[str, Any]:
    case_by_id = {case.case_id: case for case in cases}
    records = [
        _record(case_by_id[result.case_id], result)
        for result in report.results
        if result.case_id in case_by_id
    ]

    def grouped(key: str) -> dict[str, Any]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in records:
            groups[str(row[key])].append(row)
        return {
            name: {
                "case_count": len(rows),
                "pass_rate": round(
                    sum(row["status"] in {"passed", "cached"} for row in rows)
                    / len(rows),
                    6,
                ),
                "mean_score": round(
                    sum(float(row["score"]) for row in rows) / len(rows), 6
                ),
                "mean_latency_ms": round(
                    sum(float(row["latency_ms"]) for row in rows) / len(rows), 3
                ),
            }
            for name, rows in sorted(groups.items())
        }

    status_counts = Counter(row["status"] for row in records)
    failures = Counter(
        row["failure_stage"] or "none"
        for row in records
        if row["status"] not in {"passed", "cached"} or row["failure_stage"]
    )
    latencies = sorted(int(row["latency_ms"]) for row in records)
    overall = {
        "case_count": len(records),
        "status_counts": dict(sorted(status_counts.items())),
        "pass_rate": round(
            sum(row["status"] in {"passed", "cached"} for row in records)
            / len(records),
            6,
        )
        if records
        else 0.0,
        "mean_score": round(
            sum(float(row["score"]) for row in records) / len(records), 6
        )
        if records
        else 0.0,
        "latency_ms": {
            "p50": latencies[len(latencies) // 2] if latencies else 0,
            "max": max(latencies) if latencies else 0,
        },
        "cost": {"known": False, "total": None, "currency": None},
        "failure_stages": dict(failures),
    }
    return {
        "schema_version": "phase_g_baseline.v1",
        "baseline_id": "agentic_v1_real_baseline",
        "generated_at": datetime.now(UTC).isoformat(),
        "evidence_level": "synthetic_provider_free",
        "real_provider_status": {
            "status": "skipped",
            "reason": "no_provider_key_or_explicit_budget",
            "external_requests": 0,
        },
        "dataset": {
            "selected_case_count": len(records),
            "available_official_case_count": len(available_cases),
            "case_ids_sha256": _sha256_case_ids(available_cases),
            "case_catalog_sha256": report.run_metadata.case_catalog_sha256,
            "source_type_counts": dict(
                Counter(case.provenance.source_type for case in available_cases)
            ),
        },
        "overall": overall,
        "course": grouped("course"),
        "task": grouped("task_type"),
        "input_mode": grouped("input_mode"),
        "records": records,
        "governance": {
            "answers_retained": False,
            "scorer_modified": False,
            "production_config_modified": False,
        },
    }


async def run(args: argparse.Namespace) -> int:
    loader = EvaluationCaseLoader(CASE_ROOT)
    all_cases = loader.load_all()
    selected = select_representative_cases(all_cases, args.max_cases)
    registry = AgentRegistry()
    for case in selected:
        registry.get(case.expected_agent)
    attachment_sha, attachment_count = evaluation_case_attachment_manifest(
        all_cases, CASE_ROOT
    )
    app = create_app(evaluation_settings(live=False))
    cache = EvaluationCache(
        CACHE_ROOT,
        fingerprint=evaluation_fingerprint(ROOT),
    )
    filters = {
        "phase": "G",
        "mode": "offline",
        "max_cases": args.max_cases,
        "selection": "stratified_course_task_input_v1",
    }
    async with EvaluationRunner(
        app,
        mode="offline",
        cache=cache,
        report_root=REPORT_ROOT,
        use_cache=not args.no_cache,
    ) as runner:
        report = await runner.run_suite(
            selected,
            filters=filters,
            case_catalog_sha256=evaluation_case_ids_sha256(
                case.case_id for case in all_cases
            ),
            case_catalog_content_sha256=evaluation_case_catalog_content_sha256(
                all_cases
            ),
            case_source_files_sha256=evaluation_case_source_files_sha256(CASE_ROOT),
            case_attachment_manifest_sha256=attachment_sha,
            case_attachment_count=attachment_count,
            case_attachment_root=CASE_ROOT,
        )
    payload = build_baseline(report, selected, all_cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload["overall"], ensure_ascii=False, indent=2))
    print(f"baseline={args.output}")
    print(f"report={REPORT_ROOT / 'latest.json'}")
    return 1 if report.summary.get("errors") or report.summary.get("timeouts") else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
