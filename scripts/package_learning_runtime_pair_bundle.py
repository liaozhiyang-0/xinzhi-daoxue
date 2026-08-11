"""Package multiple redacted LearningLoop Legacy/Runtime pairs.

The bundle is a development evaluation artifact.  It combines the existing
single-case package format without copying raw action payloads, and it always
stays outside the authorized Runtime release gate until a separate structural
suite, semantic sidecar, and release decision exist.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.package_learning_runtime_pair import (  # noqa: E402
    _read_object,
    build_pair_report,
)

BUNDLE_SCHEMA_VERSION = "learning_runtime_paired_evidence_bundle.v1"


def _unique_extend(target: list[str], values: object) -> None:
    if not isinstance(values, list):
        return
    for value in values:
        if isinstance(value, str) and value and value not in target:
            target.append(value)


def _merge_semantic_review(cases: list[dict[str, Any]]) -> dict[str, Any]:
    case_records: list[dict[str, Any]] = []
    judgement_template: dict[str, Any] = {}
    for case in cases:
        review = case.get("semantic_review")
        if not isinstance(review, dict):
            continue
        raw_cases = review.get("cases")
        if isinstance(raw_cases, list):
            case_records.extend(
                item for item in raw_cases if isinstance(item, dict)
            )
        raw_template = review.get("judgement_template")
        if isinstance(raw_template, dict):
            for case_id, value in raw_template.items():
                if isinstance(case_id, str) and isinstance(value, dict):
                    judgement_template[case_id] = value
    return {
        "schema_version": "learning_runtime_semantic_review_intake.v1",
        "status": "pending_independent_review",
        "redaction_status": "redacted",
        "review_boundary": (
            "Structural summaries only. Independent reviewers must attach "
            "separately redacted domain outputs for every case."
        ),
        "cases": case_records,
        "judgement_template": judgement_template,
    }


def build_bundle(
    runtime_reports: list[dict[str, Any]],
    legacy_reports: list[dict[str, Any]],
    *,
    bundle_id: str,
) -> dict[str, Any]:
    if not bundle_id.strip():
        raise ValueError("bundle_id must be a non-empty string")
    if not runtime_reports or len(runtime_reports) != len(legacy_reports):
        raise ValueError(
            "runtime and legacy reports must contain the same non-zero count"
        )

    cases: list[dict[str, Any]] = []
    case_ids: set[str] = set()
    blockers: list[str] = []
    identities: list[dict[str, Any]] = []
    bundle_reasons: list[str] = []
    for runtime_report, legacy_report in zip(
        runtime_reports, legacy_reports, strict=True
    ):
        case = build_pair_report(runtime_report, legacy_report)
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            bundle_reasons.append("learning_runtime_case_id_missing")
        elif case_id in case_ids:
            bundle_reasons.append(f"duplicate_case_id:{case_id}")
        else:
            case_ids.add(case_id)
        identity = case.get("capability_identity")
        if isinstance(identity, dict):
            identities.append(identity)
        else:
            bundle_reasons.append("learning_runtime_identity_missing")
        structural = case.get("structural_checks")
        if not isinstance(structural, dict) or structural.get("passed") is not True:
            bundle_reasons.append(f"case_structural_check_failed:{case_id}")
        _unique_extend(blockers, case.get("blockers"))
        cases.append(case)

    if identities and any(identity != identities[0] for identity in identities[1:]):
        bundle_reasons.append("learning_runtime_identity_mismatch")
    if not cases:
        bundle_reasons.append("learning_runtime_cases_missing")
    if bundle_reasons:
        _unique_extend(blockers, bundle_reasons)
    _unique_extend(blockers, [
        "learning_runtime_development_paired_evidence_only",
        "learning_runtime_semantic_sidecar_missing",
        "learning_runtime_human_release_decision_missing",
    ])

    identity = identities[0] if identities and not bundle_reasons else None
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "evidence_kind": "development_paired",
        "bundle_id": bundle_id.strip(),
        "case_count": len(cases),
        "case_ids": sorted(case_ids),
        "capability_identity": identity,
        "source_task_ids": [
            case.get("source_task_id")
            for case in cases
            if isinstance(case.get("source_task_id"), str)
        ],
        "cases": cases,
        "structural_checks": {
            "passed": not bundle_reasons,
            "reasons": bundle_reasons,
        },
        "structural_release_eligible": False,
        "semantic_release_eligible": False,
        "canary_release_eligible": False,
        "release_ready": False,
        "semantic_review_required": True,
        "human_release_decision_required": True,
        "semantic_review": _merge_semantic_review(cases),
        "blockers": blockers,
    }


def package_bundle(
    runtime_paths: list[Path],
    legacy_paths: list[Path],
    output_path: Path,
    *,
    bundle_id: str,
) -> dict[str, Any]:
    runtime_reports = [
        _read_object(path, f"runtime report {index}")
        for index, path in enumerate(runtime_paths)
    ]
    legacy_reports = [
        _read_object(path, f"legacy report {index}")
        for index, path in enumerate(legacy_paths)
    ]
    bundle = build_bundle(
        runtime_reports,
        legacy_reports,
        bundle_id=bundle_id,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return bundle


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Package multiple redacted LearningLoop pairs."
    )
    parser.add_argument("--runtime-report", action="append", required=True)
    parser.add_argument("--legacy-report", action="append", required=True)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(args: argparse.Namespace) -> int:
    bundle = package_bundle(
        [Path(path) for path in args.runtime_report],
        [Path(path) for path in args.legacy_report],
        args.output,
        bundle_id=args.bundle_id,
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "case_count": bundle["case_count"],
                "structural_checks": bundle["structural_checks"],
                "release_ready": bundle["release_ready"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if bundle["structural_checks"]["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main(_parser().parse_args()))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
