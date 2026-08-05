from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from normalize_dataset import is_fragmented_multi_image

ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "统一格式"
EXPECTED_COUNTS = {"AE": 39, "CT": 2, "DE": 32, "SS": 48}
EXPECTED_SOURCE_COUNT = 166
EXPECTED_EXCLUDED_COUNT = 45
EXPECTED_FRAGMENTED_MULTI_IMAGE_EXCLUSION_COUNT = 41
SUPPLEMENTAL_COURSES = ("CT", "AE", "DE", "SS", "DSP", "COMM")
KNOWLEDGE_SOURCE_PREFIXES = {
    "CT": "电路理论/课本/基础篇/3-重置md/",
    "AE": "模电/教材/",
    "DE": "数电/教材/",
    "SS": "信号与系统版本一/",
    "DSP": "数字信号处理/",
    "COMM": "通信原理/",
}
VALID_DIFFICULTIES = {"easy", "medium", "hard", "boundary"}
VALID_INPUT_TYPES = {"text", "text_and_image", "text_and_multi_image"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def validate_case(
    case: dict[str, Any],
    errors: list[str],
    *,
    question_only: bool = False,
) -> None:
    case_id = str(case.get("case_id") or "<missing>")
    required = {
        "case_id",
        "title",
        "course",
        "task_family",
        "intent",
        "input_type",
        "message",
        "file_refs",
        "expected_agent",
        "reference_answer",
        "provenance",
    }
    missing = sorted(required - case.keys())
    if missing:
        errors.append(f"{case_id}: 缺少字段 {missing}")
    if not str(case.get("message") or "").strip():
        errors.append(f"{case_id}: message为空")
    valid_courses = (
        set(SUPPLEMENTAL_COURSES) if question_only else set(EXPECTED_COUNTS)
    )
    if case.get("course") not in valid_courses:
        errors.append(f"{case_id}: 非法course={case.get('course')!r}")
    if case.get("difficulty") not in VALID_DIFFICULTIES:
        errors.append(f"{case_id}: 非法difficulty={case.get('difficulty')!r}")

    refs = case.get("file_refs")
    if not isinstance(refs, list):
        errors.append(f"{case_id}: file_refs必须为列表")
        refs = []
    expected_mode = (
        "text"
        if not refs
        else "text_and_image"
        if len(refs) == 1
        else "text_and_multi_image"
    )
    if case.get("input_type") not in VALID_INPUT_TYPES:
        errors.append(f"{case_id}: 非法input_type={case.get('input_type')!r}")
    if case.get("input_type") != expected_mode:
        errors.append(
            f"{case_id}: input_type={case.get('input_type')}，"
            f"但附件数{len(refs)}应为{expected_mode}"
        )

    for ref in refs:
        relative = str(ref.get("path") or "")
        candidate = (ROOT / relative).resolve()
        try:
            candidate.relative_to(ROOT)
        except ValueError:
            errors.append(f"{case_id}: 附件越出真实测试题目录: {relative}")
            continue
        if not candidate.is_file():
            errors.append(f"{case_id}: 附件不存在: {relative}")
            continue
        expected_hash = str(ref.get("sha256") or "")
        if expected_hash != sha256(candidate):
            errors.append(f"{case_id}: 附件SHA-256不匹配: {relative}")
        if ref.get("role") != "question":
            errors.append(f"{case_id}: 附件role必须为question: {relative}")
    resolved_refs = [
        (ROOT / str(ref.get("path") or "")).resolve()
        for ref in refs
        if str(ref.get("path") or "")
    ]
    if is_fragmented_multi_image(resolved_refs):
        errors.append(f"{case_id}: 存在信息严重割裂的多图输入")

    answer_refs = (
        (case.get("structured_input") or {}).get("reference_answer_assets") or []
    )
    for ref in answer_refs:
        relative = str(ref.get("path") or "")
        candidate = (ROOT / relative).resolve()
        try:
            candidate.relative_to(ROOT)
        except ValueError:
            errors.append(f"{case_id}: 答案附件越出真实测试题目录: {relative}")
            continue
        if not candidate.is_file():
            errors.append(f"{case_id}: 答案附件不存在: {relative}")
            continue
        if ref.get("sha256") != sha256(candidate):
            errors.append(f"{case_id}: 答案附件SHA-256不匹配: {relative}")
        if ref.get("role") != "reference_answer":
            errors.append(f"{case_id}: 答案附件role错误: {relative}")

    review = bool(case.get("requires_manual_review"))
    answer_missing = not str(case.get("reference_answer") or "").strip()
    if question_only:
        if not answer_missing:
            errors.append(f"{case_id}: question_only样例不得包含参考答案")
        if answer_refs:
            errors.append(f"{case_id}: question_only样例不得包含答案附件")
        if "question_only" not in (case.get("tags") or []):
            errors.append(f"{case_id}: 缺少question_only标签")
        if review:
            errors.append(f"{case_id}: 已过滤问题题，不应再标记requires_manual_review")
        if case.get("judge_type") != "human":
            errors.append(f"{case_id}: 无答案补充题judge_type必须为human")
        structured = case.get("structured_input") or {}
        source_path = str(structured.get("source_question_path") or "")
        prefix = KNOWLEDGE_SOURCE_PREFIXES.get(str(case.get("course")), "")
        if not source_path.startswith(prefix):
            errors.append(
                f"{case_id}: source_question_path不在对应课程知识库: {source_path}"
            )
    elif answer_missing and not review:
        errors.append(f"{case_id}: 缺少参考答案但未标记requires_manual_review")
    provenance = case.get("provenance") or {}
    if provenance.get("source_type") != "private":
        errors.append(f"{case_id}: 真实题库provenance.source_type必须为private")
    if provenance.get("publishable") is not False:
        errors.append(f"{case_id}: 私有题库必须标记publishable=false")


def load_cases_wrapper(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    payload = load_json(path)
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        errors.append(f"{path.name}顶层必须为{{cases:[...]}}")
        return []
    return cases


def validate_supplemental(
    dataset: Path,
    original_cases: list[dict[str, Any]],
    errors: list[str],
    *,
    project_contract: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = dataset / "supplemental"
    cases = load_cases_wrapper(root / "all_questions.json", errors)
    jsonl_cases = load_jsonl(root / "all_questions.jsonl")
    if cases != jsonl_cases:
        errors.append(
            "supplemental/all_questions.json与all_questions.jsonl内容不一致"
        )

    ids = [str(case.get("case_id") or "") for case in cases]
    duplicate_ids = sorted(
        case_id for case_id, count in Counter(ids).items() if count > 1
    )
    if duplicate_ids:
        errors.append(f"补充题case_id重复: {duplicate_ids}")
    original_ids = {str(case.get("case_id")) for case in original_cases}
    collisions = sorted(original_ids.intersection(ids))
    if collisions:
        errors.append(f"补充题与原题case_id冲突: {collisions}")

    for case in cases:
        validate_case(case, errors, question_only=True)
    for course in SUPPLEMENTAL_COURSES:
        course_cases = load_cases_wrapper(root / "cases" / f"{course}.json", errors)
        course_jsonl = load_jsonl(root / "jsonl" / f"{course}.jsonl")
        expected = [
            case for case in cases if str(case.get("course")) == course
        ]
        if course_cases != expected:
            errors.append(f"supplemental/{course}.json与总题集课程切片不一致")
        if course_cases != course_jsonl:
            errors.append(
                f"supplemental/{course}.json与{course}.jsonl内容不一致"
            )

    manifest = load_json(root / "manifest.json")
    if manifest.get("accepted_question_count") != len(cases):
        errors.append("supplemental/manifest.json题数与数据不一致")
    actual_counts = Counter(str(case.get("course")) for case in cases)
    manifest_counts = manifest.get("course_counts") or {}
    if dict(actual_counts) != manifest_counts:
        errors.append(
            "supplemental/manifest.json课程题数与数据不一致："
            f"{manifest_counts} != {dict(actual_counts)}"
        )
    if manifest.get("reference_answers_extracted") is not False:
        errors.append("supplemental manifest必须声明reference_answers_extracted=false")

    combined = load_cases_wrapper(dataset / "all_test_inputs.json", errors)
    combined_jsonl = load_jsonl(dataset / "all_test_inputs.jsonl")
    if combined != [*original_cases, *cases]:
        errors.append("all_test_inputs.json不等于核验原题加补充题")
    if combined != combined_jsonl:
        errors.append("all_test_inputs.json与all_test_inputs.jsonl内容不一致")

    if project_contract:
        validate_project_contract(cases, errors)
    return cases, manifest


def validate_project_contract(
    cases: list[dict[str, Any]], errors: list[str]
) -> None:
    api_root = ROOT.parent / "apps" / "api"
    sys.path.insert(0, str(api_root))
    try:
        from app.evaluation.contracts import EvaluationCase
    except Exception as exc:  # pragma: no cover - depends on local environment
        errors.append(f"无法加载项目EvaluationCase契约: {exc}")
        return
    for case in cases:
        try:
            EvaluationCase.model_validate(case)
        except Exception as exc:
            case_id = case.get("case_id", "<missing>")
            errors.append(f"{case_id}: 项目契约校验失败: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="校验统一真实测试集")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="统一格式目录",
    )
    parser.add_argument(
        "--project-contract",
        action="store_true",
        help="额外使用仓库EvaluationCase Pydantic契约校验",
    )
    args = parser.parse_args()
    dataset = args.dataset.resolve()
    errors: list[str] = []

    wrapper = load_json(dataset / "all_cases.json")
    cases = wrapper.get("cases") if isinstance(wrapper, dict) else None
    if not isinstance(cases, list):
        print("ERROR: all_cases.json顶层必须为{cases:[...]}", file=sys.stderr)
        return 1
    jsonl_cases = load_jsonl(dataset / "all_cases.jsonl")
    if cases != jsonl_cases:
        errors.append("all_cases.json与all_cases.jsonl内容不一致")

    ids = [str(case.get("case_id") or "") for case in cases]
    duplicate_ids = sorted(
        case_id for case_id, count in Counter(ids).items() if count > 1
    )
    if duplicate_ids:
        errors.append(f"case_id重复: {duplicate_ids}")
    if len(cases) != sum(EXPECTED_COUNTS.values()):
        errors.append(
            f"总题数应为{sum(EXPECTED_COUNTS.values())}，实际为{len(cases)}"
        )
    actual_counts = Counter(str(case.get("course")) for case in cases)
    if dict(actual_counts) != EXPECTED_COUNTS:
        errors.append(
            f"课程题数不符，期望{EXPECTED_COUNTS}，实际{dict(actual_counts)}"
        )

    for case in cases:
        validate_case(case, errors)
    for course, expected_count in EXPECTED_COUNTS.items():
        course_wrapper = load_json(dataset / "cases" / f"{course}.json")
        course_cases = course_wrapper.get("cases", [])
        course_jsonl = load_jsonl(dataset / "jsonl" / f"{course}.jsonl")
        if len(course_cases) != expected_count:
            errors.append(
                f"{course}.json应有{expected_count}题，实际{len(course_cases)}"
            )
        if course_cases != course_jsonl:
            errors.append(f"{course}.json与{course}.jsonl内容不一致")

    if args.project_contract:
        validate_project_contract(cases, errors)

    manifest = load_json(dataset / "dataset_manifest.json")
    if manifest.get("case_count") != len(cases):
        errors.append("dataset_manifest.json的case_count与数据不一致")
    if manifest.get("source_case_count") != EXPECTED_SOURCE_COUNT:
        errors.append(
            "dataset_manifest.json的source_case_count应为"
            f"{EXPECTED_SOURCE_COUNT}"
        )
    if manifest.get("excluded_case_count") != EXPECTED_EXCLUDED_COUNT:
        errors.append(
            "dataset_manifest.json的excluded_case_count应为"
            f"{EXPECTED_EXCLUDED_COUNT}"
        )
    fragmented_ids = manifest.get("fragmented_multi_image_case_ids") or []
    if (
        manifest.get("fragmented_multi_image_exclusion_count")
        != EXPECTED_FRAGMENTED_MULTI_IMAGE_EXCLUSION_COUNT
    ):
        errors.append(
            "严重割裂多图题应剔除"
            f"{EXPECTED_FRAGMENTED_MULTI_IMAGE_EXCLUSION_COUNT}题"
        )
    surviving_fragmented = sorted(set(ids).intersection(fragmented_ids))
    if surviving_fragmented:
        errors.append(f"严重割裂多图题仍在统一题集: {surviving_fragmented}")

    supplemental_cases, supplemental_manifest = validate_supplemental(
        dataset,
        cases,
        errors,
        project_contract=args.project_contract,
    )

    if errors:
        print(f"校验失败，共{len(errors)}项：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    review_count = sum(bool(case.get("requires_manual_review")) for case in cases)
    attachment_count = sum(len(case["file_refs"]) for case in cases)
    reference_asset_count = sum(
        len(
            (case.get("structured_input") or {}).get(
                "reference_answer_assets", []
            )
        )
        for case in cases
    )
    print(
        json.dumps(
            {
                "status": "passed",
                "case_count": len(cases),
                "course_counts": dict(actual_counts),
                "attachment_count": attachment_count,
                "reference_answer_asset_count": reference_asset_count,
                "manual_review_count": review_count,
                "supplemental_question_count": len(supplemental_cases),
                "supplemental_course_counts": supplemental_manifest.get(
                    "course_counts", {}
                ),
                "supplemental_attachment_count": sum(
                    len(case["file_refs"]) for case in supplemental_cases
                ),
                "combined_test_input_count": len(cases)
                + len(supplemental_cases),
                "project_contract_checked": args.project_contract,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
