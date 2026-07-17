from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASE_ID_RE = re.compile(r"^(CT|AE|DE)_RET_[0-9]{3}$")
COURSES = {"CT", "AE", "DE"}


def validate_case(payload: Any, path: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return [f"{path}: top level must be an object"]
    required = {
        "case_id",
        "course_id",
        "query",
        "expected_sources",
        "forbidden_courses",
        "tags",
        "review_status",
    }
    missing = required - payload.keys()
    if missing:
        errors.append(f"{path}: missing {sorted(missing)}")
    case_id = payload.get("case_id")
    course_id = payload.get("course_id")
    if not isinstance(case_id, str) or CASE_ID_RE.fullmatch(case_id) is None:
        errors.append(f"{path}: invalid case_id")
    if course_id not in COURSES:
        errors.append(f"{path}: invalid course_id")
    elif isinstance(case_id, str) and not case_id.startswith(f"{course_id}_"):
        errors.append(f"{path}: case_id/course_id mismatch")
    if not isinstance(payload.get("query"), str) or not payload["query"].strip():
        errors.append(f"{path}: query must be non-empty")
    sources = payload.get("expected_sources")
    if not isinstance(sources, list) or not sources:
        errors.append(f"{path}: expected_sources must be non-empty")
    else:
        for source in sources:
            if not isinstance(source, dict):
                errors.append(f"{path}: source must be an object")
                continue
            if not all(source.get(key) for key in ("document_path", "chapter")):
                errors.append(f"{path}: source path/chapter must be non-empty")
            if not isinstance(source.get("required"), bool):
                errors.append(f"{path}: source.required must be boolean")
            source_path = str(source.get("document_path", ""))
            if Path(source_path).is_absolute() or ".." in Path(source_path).parts:
                errors.append(f"{path}: source path must be relative and safe")
    forbidden = payload.get("forbidden_courses")
    if not isinstance(forbidden, list) or any(
        item not in COURSES for item in forbidden
    ):
        errors.append(f"{path}: forbidden_courses invalid")
    if course_id in (forbidden or []):
        errors.append(f"{path}: own course cannot be forbidden")
    if payload.get("review_status") not in {"draft", "approved", "rejected"}:
        errors.append(f"{path}: invalid review_status")
    return errors


def main() -> int:
    paths = sorted((ROOT / "cases").glob("*/*.json"))
    errors: list[str] = []
    counts = {course: 0 for course in COURSES}
    ids: set[str] = set()
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: unreadable JSON: {exc}")
            continue
        errors.extend(validate_case(payload, path))
        case_id = payload.get("case_id") if isinstance(payload, dict) else None
        if isinstance(case_id, str):
            if case_id in ids:
                errors.append(f"{path}: duplicate case_id {case_id}")
            ids.add(case_id)
        course_id = payload.get("course_id") if isinstance(payload, dict) else None
        if course_id in counts:
            counts[course_id] += 1
    for course, count in counts.items():
        if count < 5:
            errors.append(f"{course}: expected at least 5 cases, got {count}")
    if errors:
        print("\n".join(errors))
        return 1
    print(
        f"validated {len(paths)} draft cases: "
        + ", ".join(f"{k}={counts[k]}" for k in sorted(counts))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
