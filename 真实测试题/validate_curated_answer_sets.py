# mypy: disable-error-code=import-untyped
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from normalize_dataset import DEFAULT_OUTPUT

PARTS = {
    "part1_standard_answers": 24,
    "part2_error_detection": 12,
    "part3_boundary": 12,
}
COURSES = {"CT", "AE", "DE", "SS", "DSP", "COMM"}
EXPECTED_PER_PART_COURSE = {
    "part1_standard_answers": 4,
    "part2_error_detection": 2,
    "part3_boundary": 2,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_cases(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    payload = load_json(path)
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        errors.append(f"{path}: 顶层必须为{{cases:[...]}}")
        return []
    return cases


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def validate_project_contract(
    cases: list[dict[str, Any]],
    errors: list[str],
) -> None:
    api_root = DEFAULT_OUTPUT.parents[1] / "apps" / "api"
    sys.path.insert(0, str(api_root))
    try:
        from app.contracts.learning import StudentAttempt
        from app.evaluation.contracts import EvaluationCase
    except Exception as exc:  # pragma: no cover
        errors.append(f"无法加载项目契约: {exc}")
        return

    for case in cases:
        case_id = str(case.get("case_id") or "<missing>")
        try:
            EvaluationCase.model_validate(case)
        except Exception as exc:
            errors.append(f"{case_id}: EvaluationCase校验失败: {exc}")
        attempt = (case.get("task_options") or {}).get("student_attempt")
        if attempt is not None:
            try:
                StudentAttempt.model_validate(attempt)
            except Exception as exc:
                errors.append(f"{case_id}: StudentAttempt校验失败: {exc}")


def validate_common(case: dict[str, Any], errors: list[str]) -> None:
    case_id = str(case.get("case_id") or "<missing>")
    if case.get("course") not in COURSES:
        errors.append(f"{case_id}: 非法课程 {case.get('course')}")
    if not str(case.get("message") or "").strip():
        errors.append(f"{case_id}: message为空")
    if not str(case.get("reference_answer") or "").strip():
        errors.append(f"{case_id}: 缺少参考答案或边界期望")
    if case.get("official_scoring") is not False:
        errors.append(f"{case_id}: 必须保持official_scoring=false")
    if case.get("provenance", {}).get("publishable") is not False:
        errors.append(f"{case_id}: 必须保持publishable=false")


def validate_derived(
    case: dict[str, Any],
    base_cases: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    case_id = str(case["case_id"])
    structured = case.get("structured_input") or {}
    source_id = str(structured.get("source_case_id") or "")
    if source_id not in base_cases:
        errors.append(f"{case_id}: source_case_id不存在: {source_id}")
        return
    base = base_cases[source_id]
    for field in ("course", "message", "file_refs", "source"):
        if case.get(field) != base.get(field):
            errors.append(f"{case_id}: 派生题的{field}与源题不一致")
    answer_provenance = structured.get("answer_provenance") or {}
    if answer_provenance.get("official") is not False:
        errors.append(f"{case_id}: 答案不得标记为官方答案")
    solution = case.get("reference_solution") or {}
    if not solution.get("steps") or not solution.get("final_answer"):
        errors.append(f"{case_id}: reference_solution结构不完整")


def main() -> int:
    parser = argparse.ArgumentParser(description="校验48题精选答案与边界测试集")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="统一格式目录",
    )
    args = parser.parse_args()
    dataset = args.dataset.resolve()
    curated = dataset / "curated_answer_sets"
    errors: list[str] = []

    supplemental = load_cases(
        dataset / "supplemental" / "all_questions.json",
        errors,
    )
    base_cases = {str(case["case_id"]): case for case in supplemental}

    by_part: dict[str, list[dict[str, Any]]] = {}
    for part, expected_count in PARTS.items():
        cases = load_cases(curated / f"{part}.json", errors)
        jsonl_cases = load_jsonl(curated / f"{part}.jsonl")
        if cases != jsonl_cases:
            errors.append(f"{part}.json与{part}.jsonl不一致")
        if len(cases) != expected_count:
            errors.append(
                f"{part}应有{expected_count}题，实际{len(cases)}题"
            )
        counts = Counter(str(case.get("course")) for case in cases)
        expected_course_count = EXPECTED_PER_PART_COURSE[part]
        if counts != Counter(
            {course: expected_course_count for course in COURSES}
        ):
            errors.append(f"{part}课程配额错误: {dict(counts)}")
        by_part[part] = cases

    all_cases = [
        case
        for part in PARTS
        for case in by_part.get(part, [])
    ]
    combined = load_cases(curated / "all_selected_cases.json", errors)
    combined_jsonl = load_jsonl(curated / "all_selected_cases.jsonl")
    if combined != all_cases:
        errors.append("all_selected_cases.json不等于三个部分顺序拼接")
    if combined != combined_jsonl:
        errors.append("all_selected_cases.json与JSONL不一致")

    ids = [str(case.get("case_id") or "") for case in all_cases]
    duplicate_ids = sorted(
        case_id for case_id, count in Counter(ids).items() if count > 1
    )
    if duplicate_ids:
        errors.append(f"case_id重复: {duplicate_ids}")
    if Counter(str(case["course"]) for case in all_cases) != Counter(
        {course: 8 for course in COURSES}
    ):
        errors.append("总题集必须每门课程8题")

    for case in all_cases:
        validate_common(case, errors)

    for case in by_part.get("part1_standard_answers", []):
        validate_derived(case, base_cases, errors)
        if (case.get("task_options") or {}).get("teaching_mode") != "direct_answer":
            errors.append(f"{case['case_id']}: 第一部分必须为direct_answer")
        if (case.get("task_options") or {}).get("student_attempt") is not None:
            errors.append(f"{case['case_id']}: 第一部分不得包含student_attempt")

    for case in by_part.get("part2_error_detection", []):
        validate_derived(case, base_cases, errors)
        options = case.get("task_options") or {}
        if options.get("teaching_mode") != "check_my_work":
            errors.append(f"{case['case_id']}: 第二部分必须为check_my_work")
        attempt = options.get("student_attempt")
        if not isinstance(attempt, dict) or not attempt.get("steps"):
            errors.append(f"{case['case_id']}: 学生错误步骤缺失")
        if not case.get("expected_error_type"):
            errors.append(f"{case['case_id']}: expected_error_type缺失")
        if case.get("first_confirmed_error_found") is not True:
            errors.append(
                f"{case['case_id']}: first_confirmed_error_found必须为true"
            )

    for case in by_part.get("part3_boundary", []):
        if case.get("difficulty") != "boundary":
            errors.append(f"{case['case_id']}: 第三部分difficulty必须为boundary")
        structured = case.get("structured_input") or {}
        if not structured.get("boundary_category"):
            errors.append(f"{case['case_id']}: boundary_category缺失")
        if not structured.get("expected_behavior"):
            errors.append(f"{case['case_id']}: expected_behavior缺失")
        if case.get("expected_execution_paths") != ["CONDITIONAL"]:
            errors.append(
                f"{case['case_id']}: 边界题必须期望CONDITIONAL路径"
            )
        if not case.get("forbidden_claims"):
            errors.append(f"{case['case_id']}: 边界题必须给出forbidden_claims")

    validate_project_contract(all_cases, errors)

    manifest = load_json(curated / "manifest.json")
    if manifest.get("part_counts") != PARTS:
        errors.append("manifest part_counts不一致")
    ratios = (manifest.get("selection_policy") or {}).get("part_ratios") or {}
    if ratios != {
        "part1_standard_answers": 0.5,
        "part2_error_detection": 0.25,
        "part3_boundary": 0.25,
    }:
        errors.append("manifest比例不是50%/25%/25%")

    if errors:
        print(f"校验失败，共{len(errors)}项：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "passed",
                "case_count": len(all_cases),
                "part_counts": {
                    part: len(cases) for part, cases in by_part.items()
                },
                "course_counts": dict(
                    sorted(
                        Counter(
                            str(case["course"]) for case in all_cases
                        ).items()
                    )
                ),
                "standard_answer_count": len(
                    by_part["part1_standard_answers"]
                ),
                "student_error_case_count": len(
                    by_part["part2_error_detection"]
                ),
                "boundary_case_count": len(by_part["part3_boundary"]),
                "project_contract_checked": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
