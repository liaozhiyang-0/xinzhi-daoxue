from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "case_id",
    "difficulty",
    "input_type",
    "question",
    "attachments",
    "expected",
    "tags",
    "source_type",
    "review_status",
}
EXPECTED_REQUIRED = {
    "final_answer",
    "required_points",
    "units",
    "reference_directions",
}


def validate_case(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        case = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: invalid JSON: {exc}"]
    missing = REQUIRED - set(case)
    if missing:
        errors.append(f"{path}: missing {sorted(missing)}")
    expected = case.get("expected")
    if not isinstance(expected, dict):
        errors.append(f"{path}: expected must be an object")
    else:
        missing_expected = EXPECTED_REQUIRED - set(expected)
        if missing_expected:
            errors.append(f"{path}: expected missing {sorted(missing_expected)}")
    if case.get("review_status") != "draft_not_reviewed":
        errors.append(f"{path}: samples must remain draft_not_reviewed")
    return errors


def main() -> int:
    paths = sorted((ROOT / "cases").glob("*/*.json"))
    errors = [error for path in paths for error in validate_case(path)]
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Validated {len(paths)} draft/sample cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
