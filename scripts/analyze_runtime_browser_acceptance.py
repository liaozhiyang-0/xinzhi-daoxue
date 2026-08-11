"""Aggregate redacted authenticated Runtime browser-acceptance reports.

This script is diagnostic only. It never starts an API, calls a Provider,
changes Runtime configuration, or makes a release decision. Reports that did
not reach a terminal task state with the expected identity and Agent are kept
as harness/identity issues instead of being counted as Runtime failures.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class BrowserSample:
    report_ref: str
    report_status: str
    task_status: str
    agent_id: str
    identity_role: str
    result_provider: str
    proposal_count: int
    event_count: int
    events_strictly_increasing: bool
    page_error_count: int
    request_failure_count: int
    task_error: str
    runtime_failure_signals: tuple[dict[str, Any], ...]

    @property
    def structurally_clean(self) -> bool:
        return (
            self.events_strictly_increasing
            and self.page_error_count == 0
            and self.request_failure_count == 0
        )


def _read_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"report is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"report must be a JSON object: {path}")
    return payload


def _bounded_text(value: Any, limit: int = 500) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _failure_signals(evidence: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    raw_events = evidence.get("runtime_events")
    if not isinstance(raw_events, list):
        return ()
    signals: list[dict[str, Any]] = []
    for item in raw_events:
        if not isinstance(item, dict):
            continue
        error_code = _bounded_text(item.get("error_code"), 120)
        status = _bounded_text(item.get("status"), 80)
        reason_codes = item.get("reason_codes")
        if not error_code and status != "failed":
            continue
        signals.append(
            {
                "sequence": item.get("sequence"),
                "event_type": _bounded_text(item.get("event_type"), 120),
                "runtime_event": _bounded_text(item.get("runtime_event"), 120),
                "node_id": _bounded_text(item.get("node_id"), 160),
                "status": status,
                "error_code": error_code,
                "reason_codes": (
                    [
                        _bounded_text(code, 120)
                        for code in reason_codes[:8]
                        if isinstance(code, str)
                    ]
                    if isinstance(reason_codes, list)
                    else []
                ),
            }
        )
    return tuple(signals[:32])


def _to_sample(
    path: Path,
    payload: dict[str, Any],
    *,
    expected_agent_id: str,
    expected_identity: str,
) -> tuple[BrowserSample | None, str | None]:
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        return None, f"{path.parent.name}: missing evidence"
    task = evidence.get("task")
    identity = evidence.get("identity")
    if not isinstance(task, dict) or not isinstance(identity, dict):
        return None, f"{path.parent.name}: missing task or identity evidence"
    agent_id = _bounded_text(task.get("agent_id"), 120)
    identity_role = _bounded_text(identity.get("role"), 80)
    task_status = _bounded_text(task.get("status"), 80)
    if agent_id != expected_agent_id or identity_role != expected_identity:
        return None, (
            f"{path.parent.name}: expected {expected_identity}/"
            f"{expected_agent_id}, got {identity_role}/{agent_id}"
        )
    if task_status not in {"completed", "failed", "cancelled"}:
        return None, f"{path.parent.name}: task did not reach a terminal state"
    raw_event_count = evidence.get("event_count")
    event_count = (
        raw_event_count
        if isinstance(raw_event_count, int) and not isinstance(raw_event_count, bool)
        else 0
    )
    observations = payload.get("approval_observations")
    proposal_count = (
        sum(
            1
            for item in observations
            if isinstance(item, dict) and item.get("plan_proposal_id")
        )
        if isinstance(observations, list)
        else 0
    )
    page_errors = evidence.get("page_errors", payload.get("page_errors", []))
    request_failures = evidence.get(
        "request_failures", payload.get("request_failures", [])
    )
    sample = BrowserSample(
        report_ref=path.parent.name,
        report_status=_bounded_text(payload.get("status"), 80),
        task_status=task_status,
        agent_id=agent_id,
        identity_role=identity_role,
        result_provider=_bounded_text(task.get("result_provider"), 100),
        proposal_count=proposal_count,
        event_count=event_count,
        events_strictly_increasing=(
            evidence.get("event_sequences_strictly_increasing") is True
        ),
        page_error_count=len(page_errors) if isinstance(page_errors, list) else 0,
        request_failure_count=(
            len(request_failures) if isinstance(request_failures, list) else 0
        ),
        task_error=_bounded_text(task.get("error_message")),
        runtime_failure_signals=_failure_signals(evidence),
    )
    return sample, None


def analyze_reports(
    report_paths: list[Path],
    *,
    expected_agent_id: str,
    expected_identity: str,
) -> dict[str, Any]:
    """Aggregate valid terminal samples without making a release decision."""

    if not report_paths:
        raise ValueError("at least one report path is required")
    samples: list[BrowserSample] = []
    issues: list[str] = []
    for path in report_paths:
        resolved = path.resolve(strict=True)
        sample, issue = _to_sample(
            resolved,
            _read_report(resolved),
            expected_agent_id=expected_agent_id,
            expected_identity=expected_identity,
        )
        if sample is not None:
            samples.append(sample)
        if issue is not None:
            issues.append(issue)
    completed = [sample for sample in samples if sample.task_status == "completed"]
    failed = [sample for sample in samples if sample.task_status == "failed"]
    structurally_clean = [sample for sample in samples if sample.structurally_clean]
    failure_reasons = Counter(
        sample.task_error or "task_failed_without_message" for sample in failed
    )
    proposal_distribution = Counter(str(sample.proposal_count) for sample in samples)
    return {
        "schema_version": "runtime_browser_acceptance_analysis.v1",
        "analyzed_at": datetime.now(UTC).isoformat(),
        "expected_agent_id": expected_agent_id,
        "expected_identity": expected_identity,
        "report_count": len(report_paths),
        "valid_sample_count": len(samples),
        "excluded_report_count": len(issues),
        "completed_count": len(completed),
        "failed_count": len(failed),
        "success_rate": round(len(completed) / len(samples), 6) if samples else None,
        "structurally_clean_count": len(structurally_clean),
        "proposal_count_distribution": dict(sorted(proposal_distribution.items())),
        "failure_reasons": dict(failure_reasons),
        "failure_signals": [
            {
                "report_ref": sample.report_ref,
                "signals": list(sample.runtime_failure_signals),
            }
            for sample in failed
            if sample.runtime_failure_signals
        ],
        "samples": [
            {
                "report_ref": sample.report_ref,
                "report_status": sample.report_status,
                "task_status": sample.task_status,
                "result_provider": sample.result_provider,
                "proposal_count": sample.proposal_count,
                "event_count": sample.event_count,
                "events_strictly_increasing": sample.events_strictly_increasing,
                "page_error_count": sample.page_error_count,
                "request_failure_count": sample.request_failure_count,
                "structurally_clean": sample.structurally_clean,
            }
            for sample in samples
        ],
        "input_issues": issues,
        "diagnostic_only": True,
        "release_decision": "not_applicable",
        "warnings": [
            "does_not_replace_semantic_quality_review",
            "does_not_replace_provider_health_or_release_gates",
            "does_not_replace_human_approval",
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="append", type=Path, required=True)
    parser.add_argument("--expected-agent-id", required=True)
    parser.add_argument("--expected-identity", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = analyze_reports(
        args.report,
        expected_agent_id=args.expected_agent_id,
        expected_identity=args.expected_identity,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "valid_sample_count": report["valid_sample_count"],
                "completed_count": report["completed_count"],
                "failed_count": report["failed_count"],
                "excluded_report_count": report["excluded_report_count"],
                "diagnostic_only": True,
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
