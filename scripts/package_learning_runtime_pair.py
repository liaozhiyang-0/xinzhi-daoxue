"""Package a redacted Legacy/Runtime LearningLoop development pair.

The package is a reproducible structural review artifact, not a release
authorization.  It reads the two existing public-API E2E reports, keeps only
route/status/checkpoint/event summaries, and always marks semantic review and
human release approval as outstanding.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SEMANTIC_DIMENSIONS = (
    "task_fulfillment",
    "factual_correctness",
    "evidence_faithfulness",
    "safety",
)


def _read_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _single_result(report: dict[str, Any], label: str) -> dict[str, Any]:
    results = report.get("results")
    if not isinstance(results, list) or len(results) != 1:
        raise ValueError(f"{label} must contain exactly one result")
    result = results[0]
    if not isinstance(result, dict):
        raise ValueError(f"{label} result must be an object")
    return result


def _safe_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _safe_summary(value: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    summary: dict[str, Any] = {}
    for key in keys:
        item = value.get(key)
        if isinstance(item, (str, bool, int, float)) or item is None:
            summary[key] = item
    return summary


def _safe_nodes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    raw_nodes = value.get("node_statuses")
    if not isinstance(raw_nodes, list):
        return []
    nodes: list[dict[str, Any]] = []
    for item in raw_nodes:
        if not isinstance(item, dict):
            continue
        node_id = _safe_string(item.get("node_id"))
        if node_id is None:
            continue
        nodes.append(
            {
                "node_id": node_id,
                "status": _safe_string(item.get("status")),
                "effect_status": _safe_string(item.get("effect_status")),
                "attempt": item.get("attempt")
                if isinstance(item.get("attempt"), int)
                else None,
                "error_code": _safe_string(item.get("error_code")) or "",
            }
        )
    return nodes


def _safe_controls(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    controls: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        action = _safe_string(item.get("action"))
        if action is None:
            continue
        controls.append(
            {
                "action": action,
                "status": _safe_string(item.get("status")),
                "result_status": _safe_string(item.get("result_status")),
            }
        )
    return controls


def _safe_runtime(result: dict[str, Any]) -> dict[str, Any]:
    runtime = result.get("runtime")
    runtime = runtime if isinstance(runtime, dict) else {}
    history = result.get("runtime_status_history")
    status_history = (
        [item for item in history if isinstance(item, str)]
        if isinstance(history, list)
        else []
    )
    return {
        "status": _safe_string(runtime.get("status")),
        "run_kind": _safe_string(runtime.get("run_kind")),
        "state_version": runtime.get("state_version")
        if isinstance(runtime.get("state_version"), int)
        else None,
        "approval_required": runtime.get("approval_required")
        if isinstance(runtime.get("approval_required"), bool)
        else None,
        "resumable": runtime.get("resumable")
        if isinstance(runtime.get("resumable"), bool)
        else None,
        "status_history": status_history,
        "nodes": _safe_nodes(runtime),
        "controls": _safe_controls(result.get("controls")),
        "checkpoints": _safe_summary(
            result.get("checkpoints"),
            (
                "count",
                "strictly_increasing",
                "first_event_sequence",
                "last_event_sequence",
            ),
        ),
        "events": _safe_summary(
            result.get("events"),
            ("count", "strictly_increasing", "first_sequence", "last_sequence"),
        ),
    }


def _semantic_review_intake(case_id: str) -> dict[str, Any]:
    """Create a blank, explicitly non-authorizing semantic review intake."""

    return {
        "schema_version": "learning_runtime_semantic_review_intake.v1",
        "status": "pending_independent_review",
        "redaction_status": "redacted",
        "review_boundary": (
            "Structural summaries only. An independent reviewer must attach "
            "separately redacted domain outputs before judging semantics."
        ),
        "cases": [
            {
                "case_id": case_id,
                "review_material_required": True,
                "raw_action_payload_included": False,
            }
        ],
        "judgement_template": {
            case_id: {
                "dimensions": {dimension: None for dimension in SEMANTIC_DIMENSIONS},
                "decision": "needs_review",
                "judge_type": "human",
                "rubric_version": "learning-runtime-semantic-v1",
                "reviewer_ref": "TO_BE_COMPLETED_BY_INDEPENDENT_REVIEWER",
                "reviewed_at": "TO_BE_COMPLETED_WITH_ISO8601_TIMEZONE",
                "redaction_status": "redacted",
                "authorization_ref": "TO_BE_BOUND_TO_SEPARATE_RELEASE_RECORD",
            }
        },
    }


def build_pair_report(
    runtime_report: dict[str, Any],
    legacy_report: dict[str, Any],
    *,
    expected_case_id: str | None = None,
) -> dict[str, Any]:
    runtime = _single_result(runtime_report, "runtime_report")
    legacy = _single_result(legacy_report, "legacy_report")
    runtime_case = _safe_string(runtime.get("case_id"))
    legacy_case = _safe_string(legacy.get("case_id"))
    case_id = expected_case_id or runtime_case or legacy_case or ""
    reasons: list[str] = []
    if not case_id:
        reasons.append("case_id_missing")
    if runtime_case != case_id or legacy_case != case_id:
        reasons.append("case_id_mismatch")
    if runtime.get("mode") != "runtime":
        reasons.append("runtime_mode_mismatch")
    if legacy.get("mode") != "legacy":
        reasons.append("legacy_mode_mismatch")
    if runtime.get("task_id") != legacy.get("task_id"):
        reasons.append("source_task_id_mismatch")
    if runtime.get("result_status") != "completed":
        reasons.append("runtime_not_completed")
    if legacy.get("result_status") != "completed":
        reasons.append("legacy_not_completed")
    if runtime.get("observed_runtime_route") is not True:
        reasons.append("runtime_route_not_observed")
    if legacy.get("observed_runtime_route") is not False:
        reasons.append("legacy_route_not_observed")

    runtime_summary = _safe_runtime(runtime)
    legacy_summary = _safe_runtime(legacy)
    runtime_events = runtime_summary["events"]
    legacy_events = legacy_summary["events"]
    runtime_checkpoints = runtime_summary["checkpoints"]
    if runtime_events.get("strictly_increasing") is not True:
        reasons.append("runtime_event_order_invalid")
    if legacy_events.get("strictly_increasing") is not True:
        reasons.append("legacy_event_order_invalid")
    if not isinstance(runtime_checkpoints.get("count"), int) or runtime_checkpoints[
        "count"
    ] < 1:
        reasons.append("runtime_checkpoint_missing")
    if runtime_checkpoints.get("strictly_increasing") is not True:
        reasons.append("runtime_checkpoint_event_order_invalid")

    structural_passed = not reasons
    return {
        "schema_version": "learning_runtime_paired_evidence.v1",
        "evidence_kind": "development_paired",
        "case_id": case_id,
        "source_task_id": runtime.get("task_id"),
        "runtime": runtime_summary,
        "legacy": legacy_summary,
        "structural_checks": {
            "passed": structural_passed,
            "reasons": reasons,
        },
        "structural_release_eligible": False,
        "semantic_release_eligible": False,
        "canary_release_eligible": False,
        "release_ready": False,
        "semantic_review_required": True,
        "human_release_decision_required": True,
        "semantic_review": _semantic_review_intake(case_id),
        "blockers": [
            "development_mock_evidence_only",
            "learning_runtime_semantic_sidecar_missing",
            "learning_runtime_human_release_decision_missing",
            *reasons,
        ],
    }


def package_pair(
    runtime_path: Path,
    legacy_path: Path,
    output_path: Path,
    *,
    expected_case_id: str | None = None,
) -> dict[str, Any]:
    report = build_pair_report(
        _read_object(runtime_path, "runtime_report"),
        _read_object(legacy_path, "legacy_report"),
        expected_case_id=expected_case_id,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Package a redacted LearningLoop Legacy/Runtime pair."
    )
    parser.add_argument("--runtime-report", type=Path, required=True)
    parser.add_argument("--legacy-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id", default="")
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = package_pair(
        args.runtime_report,
        args.legacy_report,
        args.output,
        expected_case_id=args.case_id.strip() or None,
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "structural_checks": report["structural_checks"],
                "release_ready": report["release_ready"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["structural_checks"]["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
