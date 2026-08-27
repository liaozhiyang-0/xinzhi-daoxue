from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "apps" / "api"
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
for import_root in (API_ROOT, SCRIPTS_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from app.services.course_asset_review import (  # noqa: E402
    build_course_asset_readiness,
)
from audit_course_assets import (  # type: ignore[import-not-found]  # noqa: E402
    DEFAULT_COURSES,
    build_report,
)

CONSISTENCY_SCHEMA_VERSION = "course_asset_readiness_consistency.v1"


def _compare(
    errors: list[str],
    label: str,
    static_value: Any,
    runtime_value: Any,
) -> None:
    if static_value != runtime_value:
        errors.append(
            f"{label}:static={static_value!r}:runtime={runtime_value!r}"
        )


def _course_report(
    static_course: dict[str, Any], runtime_course: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []
    _compare(
        errors,
        "runtime_loaded",
        static_course["course_asset_manifest_runtime_loaded"],
        runtime_course["runtime_loaded"],
    )
    _compare(
        errors,
        "runtime_source",
        static_course["course_asset_manifest_runtime_source"],
        runtime_course["runtime_source"],
    )

    static_queue = static_course["teacher_review_queue"]
    runtime_queue = runtime_course["teacher_review_queue"]
    _compare(
        errors,
        "teacher_review_queue.item_count",
        static_queue["item_count"],
        runtime_queue["item_count"],
    )
    _compare(
        errors,
        "teacher_review_queue.unresolved_signatures_without_proposal",
        static_queue["unresolved_signatures_without_proposal"],
        runtime_queue["unresolved_signatures_without_proposal"],
    )

    static_evidence = static_course["error_signature_evidence"]
    runtime_evidence = runtime_course["teacher_review_evidence"]
    _compare(
        errors,
        "error_signature_evidence.proposal_count",
        static_evidence["proposal_count"],
        runtime_queue["item_count"],
    )
    _compare(
        errors,
        "error_signature_evidence.teacher_review_pending_count",
        static_evidence["teacher_review_pending_count"],
        runtime_evidence["missing_count"],
    )
    _compare(
        errors,
        "error_signature_evidence.evidence_ready_count",
        static_evidence["evidence_ready_count"],
        runtime_evidence["deterministic_evidence_ready_count"],
    )
    if any(
        item.get("runtime_eligible") is not False
        for item in static_evidence["items"]
    ):
        errors.append("error_signature_evidence.runtime_eligible_must_remain_false")

    return {
        "course_id": runtime_course["course_id"],
        "status": "consistent" if not errors else "review",
        "errors": errors,
        "static_queue_item_count": static_queue["item_count"],
        "runtime_queue_item_count": runtime_queue["item_count"],
        "static_deterministic_evidence_ready_count": static_evidence[
            "evidence_ready_count"
        ],
        "runtime_deterministic_evidence_ready_count": runtime_evidence[
            "deterministic_evidence_ready_count"
        ],
        "runtime_eligible_candidate_count": sum(
            1 for item in static_evidence["items"] if item.get("runtime_eligible")
        ),
    }


def _boundary_report(
    static_boundary: dict[str, Any], runtime_boundaries: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []
    keys = (
        "package_status",
        "official_rules_verified",
        "official_score_claims_allowed",
        "demo_cases_included",
        "real_user_outcomes_included",
        "real_provider_results_included",
    )
    for key in keys:
        _compare(errors, key, static_boundary.get(key), runtime_boundaries.get(key))
    return {
        "status": "consistent" if not errors else "review",
        "errors": errors,
        "boundary_keys_checked": list(keys),
    }


def build_consistency_report(
    root: Path, courses: Sequence[str] = DEFAULT_COURSES
) -> dict[str, Any]:
    normalized_courses = tuple(sorted({course.strip().upper() for course in courses}))
    if not normalized_courses:
        raise ValueError("at least one course is required")
    static_report = build_report(root, normalized_courses)
    runtime_reports = {
        course: build_course_asset_readiness(root, course)
        for course in normalized_courses
    }
    course_reports = {
        course: _course_report(
            static_report["courses"][course], runtime_reports[course]
        )
        for course in normalized_courses
    }
    boundary_report = _boundary_report(
        static_report["contest_support_boundary"],
        runtime_reports[normalized_courses[0]]["contest_boundary"],
    )
    errors = [
        f"{course}:{error}"
        for course, report in course_reports.items()
        for error in report["errors"]
    ] + boundary_report["errors"]
    return {
        "schema_version": CONSISTENCY_SCHEMA_VERSION,
        "read_only": True,
        "status": "consistent" if not errors else "review",
        "courses": course_reports,
        "contest_boundary": boundary_report,
        "errors": errors,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only consistency audit for static and runtime readiness evidence"
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="project root",
    )
    parser.add_argument(
        "--course",
        action="append",
        choices=sorted(DEFAULT_COURSES),
        help="course to include; repeat to include multiple courses",
    )
    parser.add_argument("--output", type=Path, help="optional JSON output path")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_consistency_report(
        args.root.resolve(), args.course or DEFAULT_COURSES
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"readiness consistency audit written: {args.output}")
    return 0 if report["status"] == "consistent" else 1


if __name__ == "__main__":
    raise SystemExit(main())
