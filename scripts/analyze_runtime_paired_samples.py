"""Analyze repeated, authorized Legacy/Runtime E2E reports offline.

This diagnostic consumes only the redacted ``report.json`` files produced by
``run_runtime_authorized_dev_e2e.py``. It never starts an API, calls a
Provider, changes launch modes, packages release evidence, or makes a release
decision. Repeated samples remain diagnostic data; structural parity,
independent semantic review, and human approval keep their existing gates.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

METRIC_KEYS = (
    "metrics.latency_ms",
    "task_lifecycle_elapsed_ms",
    "client_observed_terminal_wait_ms",
)


@dataclass(frozen=True, slots=True)
class PairedSample:
    sample_ref: str
    agent_id: str
    case_id: str
    legacy: dict[str, Any]
    runtime: dict[str, Any]


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"report is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"report must be a JSON object: {path}")
    return payload


def _number_at(payload: dict[str, Any], path: str) -> int | None:
    value: Any = payload
    for key in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0, round(value))
    return None


def _stats(values: list[int]) -> dict[str, int | None]:
    if not values:
        return {"count": 0, "min": None, "median": None, "max": None}
    return {
        "count": len(values),
        "min": min(values),
        "median": round(median(values)),
        "max": max(values),
    }


def _relative_regression(runtime: int, legacy: int) -> float:
    return round(max(0, runtime - legacy) / max(1, legacy), 6)


def _report_pairs(path: Path) -> tuple[list[PairedSample], list[str]]:
    payload = _read_json_object(path)
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError(f"report results must be a list: {path}")
    sample_ref = path.parent.name or path.name
    grouped: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    issues: list[str] = []
    for item in results:
        if not isinstance(item, dict):
            issues.append(f"{sample_ref}: result entry is not an object")
            continue
        agent_id = item.get("agent_id")
        case_id = item.get("case_id")
        mode = item.get("mode")
        if not isinstance(agent_id, str) or not isinstance(case_id, str):
            issues.append(f"{sample_ref}: result identity is missing")
            continue
        if mode not in {"legacy", "runtime"}:
            issues.append(f"{sample_ref}:{case_id}: unsupported run mode")
            continue
        key = (agent_id, case_id)
        if mode in grouped.setdefault(key, {}):
            issues.append(f"{sample_ref}:{case_id}: duplicate {mode} result")
            continue
        grouped[key][mode] = item
    pairs: list[PairedSample] = []
    for (agent_id, case_id), modes in sorted(grouped.items()):
        legacy = modes.get("legacy")
        runtime = modes.get("runtime")
        if legacy is None or runtime is None:
            issues.append(f"{sample_ref}:{case_id}: incomplete Legacy/Runtime pair")
            continue
        pairs.append(
            PairedSample(
                sample_ref=sample_ref,
                agent_id=agent_id,
                case_id=case_id,
                legacy=legacy,
                runtime=runtime,
            )
        )
    return pairs, issues


def _sample_is_usable(sample: PairedSample) -> bool:
    for item in (sample.legacy, sample.runtime):
        result = item.get("result")
        events = item.get("events")
        if not item.get("expected_agent_matched"):
            return False
        if not isinstance(result, dict) or result.get("status") != "completed":
            return False
        if (
            not isinstance(events, dict)
            or events.get("strictly_increasing") is not True
        ):
            return False
    return True


def _case_report(
    samples: list[PairedSample], *, max_single_pair_regression_ratio: float
) -> dict[str, Any]:
    usable = [sample for sample in samples if _sample_is_usable(sample)]
    metrics: dict[str, dict[str, Any]] = {}
    single_sample_regressions: list[dict[str, Any]] = []
    for metric_key in METRIC_KEYS:
        legacy_values: list[int] = []
        runtime_values: list[int] = []
        deltas: list[int] = []
        for sample in usable:
            legacy_result = sample.legacy.get("result")
            runtime_result = sample.runtime.get("result")
            if not isinstance(legacy_result, dict) or not isinstance(
                runtime_result, dict
            ):
                continue
            legacy_value = _number_at(legacy_result, metric_key)
            runtime_value = _number_at(runtime_result, metric_key)
            if legacy_value is None or runtime_value is None:
                continue
            legacy_values.append(legacy_value)
            runtime_values.append(runtime_value)
            deltas.append(runtime_value - legacy_value)
            regression = _relative_regression(runtime_value, legacy_value)
            if regression > max_single_pair_regression_ratio:
                single_sample_regressions.append(
                    {
                        "sample_ref": sample.sample_ref,
                        "metric": metric_key,
                        "legacy": legacy_value,
                        "runtime": runtime_value,
                        "regression_ratio": regression,
                    }
                )
        metrics[metric_key] = {
            "legacy": _stats(legacy_values),
            "runtime": _stats(runtime_values),
            "runtime_minus_legacy": _stats(deltas),
        }
    return {
        "sample_count": len(samples),
        "usable_sample_count": len(usable),
        "unusable_sample_refs": [
            sample.sample_ref for sample in samples if sample not in usable
        ],
        "metrics": metrics,
        "single_sample_regressions": single_sample_regressions,
        "requires_investigation": bool(single_sample_regressions),
    }


def analyze_reports(
    report_paths: list[Path], *, max_single_pair_regression_ratio: float = 0.5
) -> dict[str, Any]:
    """Build a redacted, diagnostic-only comparison across E2E reports."""

    if not report_paths:
        raise ValueError("at least one report path is required")
    if max_single_pair_regression_ratio < 0:
        raise ValueError("max_single_pair_regression_ratio must be non-negative")
    grouped: dict[tuple[str, str], list[PairedSample]] = {}
    issues: list[str] = []
    for path in report_paths:
        resolved = path.resolve(strict=True)
        pairs, report_issues = _report_pairs(resolved)
        issues.extend(report_issues)
        for pair in pairs:
            grouped.setdefault((pair.agent_id, pair.case_id), []).append(pair)
    cases = [
        {
            "agent_id": agent_id,
            "case_id": case_id,
            **_case_report(
                samples,
                max_single_pair_regression_ratio=max_single_pair_regression_ratio,
            ),
        }
        for (agent_id, case_id), samples in sorted(grouped.items())
    ]
    return {
        "schema_version": "runtime_paired_sample_analysis.v1",
        "analyzed_at": datetime.now(UTC).isoformat(),
        "report_count": len(report_paths),
        "max_single_pair_regression_ratio": max_single_pair_regression_ratio,
        "cases": cases,
        "input_issues": issues,
        "diagnostic_only": True,
        "release_decision": "not_applicable",
        "warnings": [
            "does_not_replace_structural_parity_or_release_gates",
            "does_not_replace_independent_semantic_review",
            "does_not_replace_human_release_decision",
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        action="append",
        type=Path,
        required=True,
        help="Redacted report.json from one authorized E2E sample directory.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--max-single-pair-regression-ratio", type=float, default=0.5
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = analyze_reports(
        args.report,
        max_single_pair_regression_ratio=args.max_single_pair_regression_ratio,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "case_count": len(report["cases"]),
                "input_issue_count": len(report["input_issues"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        raise SystemExit(1) from exc
