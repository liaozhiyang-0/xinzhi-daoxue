# mypy: disable-error-code=import-untyped
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from normalize_dataset import DEFAULT_OUTPUT, ROOT

COURSES = ("CT", "AE", "DE", "SS", "DSP", "COMM")
PER_COURSE_QUOTA = 56
EXPECTED_ROLE_COUNTS = {
    "verified_original_answer": 121,
    "curated_answer_or_error": 36,
    "synthetic_boundary": 12,
    "question_only_filler": 167,
}
EXPECTED_REFERENCE_ANSWER_COUNT = 169


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


def normalized_text_hash(message: str) -> str:
    normalized = re.sub(r"\s+", "", message).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_contract(
    cases: list[dict[str, Any]],
    errors: list[str],
) -> None:
    api_root = ROOT.parent / "apps" / "api"
    sys.path.insert(0, str(api_root))
    try:
        from app.evaluation.contracts import EvaluationCase
    except Exception as exc:  # pragma: no cover
        errors.append(f"无法加载EvaluationCase: {exc}")
        return
    for case in cases:
        try:
            EvaluationCase.model_validate(case)
        except Exception as exc:
            errors.append(f"{case.get('case_id')}: 项目契约校验失败: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="校验六科均衡336题套件")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="统一格式目录",
    )
    args = parser.parse_args()
    dataset = args.dataset.resolve()
    suite = dataset / "balanced_336"
    errors: list[str] = []

    cases = load_cases(suite / "all_cases.json", errors)
    jsonl_cases = load_jsonl(suite / "all_cases.jsonl")
    if cases != jsonl_cases:
        errors.append("balanced_336/all_cases.json与JSONL不一致")
    if len(cases) != 336:
        errors.append(f"总题数必须为336，实际{len(cases)}")

    ids = [str(case.get("case_id") or "") for case in cases]
    duplicate_ids = sorted(
        case_id for case_id, count in Counter(ids).items() if count > 1
    )
    if duplicate_ids:
        errors.append(f"case_id重复: {duplicate_ids}")
    text_hashes = [
        normalized_text_hash(str(case.get("message") or "")) for case in cases
    ]
    duplicate_text_count = sum(
        count - 1 for count in Counter(text_hashes).values() if count > 1
    )
    if duplicate_text_count:
        errors.append(f"存在{duplicate_text_count}条完全重复题干")

    course_counts = Counter(str(case.get("course")) for case in cases)
    expected_courses = Counter(
        {course: PER_COURSE_QUOTA for course in COURSES}
    )
    if course_counts != expected_courses:
        errors.append(f"课程数量不均衡: {dict(course_counts)}")

    for course in COURSES:
        course_cases = load_cases(
            suite / "cases" / f"{course}.json",
            errors,
        )
        course_jsonl = load_jsonl(suite / "jsonl" / f"{course}.jsonl")
        expected = [
            case for case in cases if str(case.get("course")) == course
        ]
        if course_cases != expected:
            errors.append(f"{course}.json与总题集切片不一致")
        if course_cases != course_jsonl:
            errors.append(f"{course}.json与JSONL不一致")

    roles = Counter(
        str(
            (case.get("structured_input") or {}).get(
                "balanced_suite_role"
            )
        )
        for case in cases
    )
    if dict(roles) != EXPECTED_ROLE_COUNTS:
        errors.append(f"题目角色数量不符: {dict(roles)}")

    original = load_cases(dataset / "all_cases.json", errors)
    curated = load_cases(
        dataset / "curated_answer_sets" / "all_selected_cases.json",
        errors,
    )
    suite_ids = set(ids)
    missing_original = sorted(
        str(case["case_id"])
        for case in original
        if str(case["case_id"]) not in suite_ids
    )
    missing_curated = sorted(
        str(case["case_id"])
        for case in curated
        if str(case["case_id"]) not in suite_ids
    )
    if missing_original:
        errors.append(f"未完整纳入原答案题: {missing_original}")
    if missing_curated:
        errors.append(f"未完整纳入48题精选集: {missing_curated}")

    curated_source_ids = {
        str((case.get("structured_input") or {}).get("source_case_id") or "")
        for case in curated
    } - {""}
    duplicated_sources = sorted(curated_source_ids.intersection(suite_ids))
    if duplicated_sources:
        errors.append(f"精选派生题与无答案源题重复纳入: {duplicated_sources}")

    answer_count = 0
    for case in cases:
        case_id = str(case.get("case_id") or "<missing>")
        if str(case.get("reference_answer") or "").strip():
            answer_count += 1
        for ref in case.get("file_refs") or []:
            relative = str(ref.get("path") or "")
            path = (ROOT / relative).resolve()
            try:
                path.relative_to(ROOT)
            except ValueError:
                errors.append(f"{case_id}: 附件越出真实测试题目录")
                continue
            if not path.is_file():
                errors.append(f"{case_id}: 附件不存在: {relative}")
                continue
            if ref.get("sha256") != sha256(path):
                errors.append(f"{case_id}: 附件SHA-256不匹配: {relative}")
    if answer_count != EXPECTED_REFERENCE_ANSWER_COUNT:
        errors.append(
            "有参考答案或边界期望的题应为"
            f"{EXPECTED_REFERENCE_ANSWER_COUNT}，实际{answer_count}"
        )

    source_manifest = load_json(dataset / "dataset_manifest.json")
    fragmented_ids = set(
        source_manifest.get("fragmented_multi_image_case_ids") or []
    )
    surviving_fragmented = sorted(fragmented_ids.intersection(suite_ids))
    if surviving_fragmented:
        errors.append(f"均衡套件仍含严重割裂多图题: {surviving_fragmented}")

    validate_contract(cases, errors)

    manifest = load_json(suite / "manifest.json")
    if manifest.get("case_count") != len(cases):
        errors.append("manifest case_count不一致")
    if manifest.get("course_counts") != {
        course: PER_COURSE_QUOTA for course in COURSES
    }:
        errors.append("manifest course_counts不一致")
    if manifest.get("role_counts") != EXPECTED_ROLE_COUNTS:
        errors.append("manifest role_counts不一致")
    if manifest.get("reference_answer_count") != answer_count:
        errors.append("manifest reference_answer_count不一致")

    inventory = load_json(dataset / "question_bank_inventory.json")
    supplemental = load_cases(
        dataset / "supplemental" / "all_questions.json",
        errors,
    )
    boundary = [
        case
        for case in curated
        if "part3_boundary" in (case.get("tags") or [])
    ]
    independent = [*original, *supplemental, *boundary]
    independent_hashes = {
        normalized_text_hash(str(case.get("message") or ""))
        for case in independent
    }
    independent_course_counts = Counter(
        str(case["course"]) for case in independent
    )
    if inventory.get("independent_question_count") != len(
        independent_hashes
    ):
        errors.append("question_bank_inventory独立题数不一致")
    if inventory.get("independent_course_counts") != {
        course: independent_course_counts[course] for course in COURSES
    }:
        errors.append("question_bank_inventory课程题数不一致")
    recommended = inventory.get("recommended_balanced_suite") or {}
    if recommended.get("case_count") != len(cases):
        errors.append("question_bank_inventory推荐套件题数不一致")

    if errors:
        print(f"校验失败，共{len(errors)}项：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "passed",
                "case_count": len(cases),
                "course_counts": dict(course_counts),
                "role_counts": dict(roles),
                "reference_answer_count": answer_count,
                "question_only_count": len(cases) - answer_count,
                "duplicate_case_ids": 0,
                "duplicate_question_texts": 0,
                "project_contract_checked": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
