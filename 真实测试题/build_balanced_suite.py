from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

from normalize_dataset import DEFAULT_OUTPUT, write_json, write_jsonl

COURSES = ("CT", "AE", "DE", "SS", "DSP", "COMM")
PER_COURSE_QUOTA = 56
SUITE_NAME = "balanced_336"


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ValueError(f"{path} 顶层必须为 {{\"cases\": [...]}}")
    return cases


def normalized_text_hash(message: str) -> str:
    normalized = re.sub(r"\s+", "", message).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def stable_order_key(case: dict[str, Any]) -> str:
    value = f"balanced-336-v1:{case['course']}:{case['case_id']}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def with_role(case: dict[str, Any], role: str) -> dict[str, Any]:
    cloned = copy.deepcopy(case)
    cloned["structured_input"] = {
        **copy.deepcopy(case.get("structured_input") or {}),
        "balanced_suite_role": role,
    }
    cloned["tags"] = [
        *[
            tag
            for tag in (case.get("tags") or [])
            if tag != "balanced_336"
        ],
        "balanced_336",
    ]
    return cloned


def chapter_of(case: dict[str, Any]) -> int:
    value = (case.get("structured_input") or {}).get("chapter")
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        match = re.search(r"\d+", str(case.get("case_id") or ""))
        return int(match.group(0)) if match else 0


def select_question_only_fillers(
    *,
    course: str,
    count: int,
    supplemental: list[dict[str, Any]],
    excluded_source_ids: set[str],
    used_text_hashes: set[str],
) -> list[dict[str, Any]]:
    by_chapter: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for case in supplemental:
        if case.get("course") != course:
            continue
        if str(case["case_id"]) in excluded_source_ids:
            continue
        if str(case.get("reference_answer") or "").strip():
            continue
        text_hash = normalized_text_hash(str(case.get("message") or ""))
        if text_hash in used_text_hashes:
            continue
        by_chapter[chapter_of(case)].append(case)

    queues: dict[int, deque[dict[str, Any]]] = {}
    for chapter, cases in by_chapter.items():
        queues[chapter] = deque(sorted(cases, key=stable_order_key))

    selected: list[dict[str, Any]] = []
    chapters = sorted(queues)
    while len(selected) < count:
        progress = False
        for chapter in chapters:
            queue = queues[chapter]
            while queue:
                case = queue.popleft()
                text_hash = normalized_text_hash(str(case["message"]))
                if text_hash in used_text_hashes:
                    continue
                selected.append(with_role(case, "question_only_filler"))
                used_text_hashes.add(text_hash)
                progress = True
                break
            if len(selected) == count:
                break
        if not progress:
            raise ValueError(
                f"{course} 可用无答案题不足，需{count}题，实际选出{len(selected)}题"
            )
    return selected


def build(output: Path) -> dict[str, Any]:
    original = load_cases(output / "all_cases.json")
    supplemental = load_cases(
        output / "supplemental" / "all_questions.json"
    )
    curated = load_cases(
        output / "curated_answer_sets" / "all_selected_cases.json"
    )

    selected: list[dict[str, Any]] = []
    for case in original:
        selected.append(with_role(case, "verified_original_answer"))
    for case in curated:
        role = (
            "synthetic_boundary"
            if "part3_boundary" in (case.get("tags") or [])
            else "curated_answer_or_error"
        )
        selected.append(with_role(case, role))

    excluded_source_ids = {
        str((case.get("structured_input") or {}).get("source_case_id") or "")
        for case in curated
    } - {""}
    used_text_hashes = {
        normalized_text_hash(str(case.get("message") or ""))
        for case in selected
    }

    current_counts = Counter(str(case["course"]) for case in selected)
    filler_counts: dict[str, int] = {}
    for course in COURSES:
        needed = PER_COURSE_QUOTA - current_counts[course]
        if needed < 0:
            raise ValueError(
                f"{course}已有{current_counts[course]}题，超过每科配额"
                f"{PER_COURSE_QUOTA}"
            )
        filler_counts[course] = needed
        selected.extend(
            select_question_only_fillers(
                course=course,
                count=needed,
                supplemental=supplemental,
                excluded_source_ids=excluded_source_ids,
                used_text_hashes=used_text_hashes,
            )
        )

    course_order = {course: index for index, course in enumerate(COURSES)}
    role_order = {
        "verified_original_answer": 0,
        "curated_answer_or_error": 1,
        "synthetic_boundary": 2,
        "question_only_filler": 3,
    }
    selected.sort(
        key=lambda case: (
            course_order[str(case["course"])],
            role_order[
                str(
                    (case.get("structured_input") or {}).get(
                        "balanced_suite_role"
                    )
                )
            ],
            stable_order_key(case),
        )
    )

    suite_root = output / SUITE_NAME
    by_course: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in selected:
        by_course[str(case["course"])].append(case)
    for course in COURSES:
        write_json(
            suite_root / "cases" / f"{course}.json",
            {"cases": by_course[course]},
        )
        write_jsonl(
            suite_root / "jsonl" / f"{course}.jsonl",
            by_course[course],
        )
    write_json(suite_root / "all_cases.json", {"cases": selected})
    write_jsonl(suite_root / "all_cases.jsonl", selected)

    role_counts = Counter(
        str(
            (case.get("structured_input") or {}).get(
                "balanced_suite_role"
            )
        )
        for case in selected
    )
    answer_counts = Counter(
        str(case["course"])
        for case in selected
        if str(case.get("reference_answer") or "").strip()
    )
    manifest = {
        "schema_version": "1.0",
        "suite_name": SUITE_NAME,
        "case_count": len(selected),
        "per_course_quota": PER_COURSE_QUOTA,
        "course_counts": {
            course: len(by_course[course]) for course in COURSES
        },
        "role_counts": dict(sorted(role_counts.items())),
        "reference_answer_count": sum(answer_counts.values()),
        "reference_answer_course_counts": {
            course: answer_counts[course] for course in COURSES
        },
        "question_only_count": sum(
            not str(case.get("reference_answer") or "").strip()
            for case in selected
        ),
        "filler_course_counts": filler_counts,
        "input_mode_counts": dict(
            sorted(Counter(str(case["input_type"]) for case in selected).items())
        ),
        "selection_policy": {
            "include_all_verified_original_answers": True,
            "include_all_curated_answer_error_and_boundary_cases": True,
            "replace_curated_source_questions_instead_of_duplicating_them": True,
            "fill_question_only_by_chapter_round_robin": True,
            "stable_selection_seed": "balanced-336-v1",
        },
        "official_scoring": False,
    }
    write_json(suite_root / "manifest.json", manifest)

    boundary_cases = [
        case
        for case in curated
        if "part3_boundary" in (case.get("tags") or [])
    ]
    independent_questions = [*original, *supplemental, *boundary_cases]
    independent_course_counts = Counter(
        str(case["course"]) for case in independent_questions
    )
    inventory = {
        "counting_rule": (
            "按独立题干计数；36道精选答案/查错派生题不重复计算，"
            "12道合成边界题作为新题计算"
        ),
        "independent_question_count": len(
            {
                normalized_text_hash(str(case.get("message") or ""))
                for case in independent_questions
            }
        ),
        "independent_course_counts": {
            course: independent_course_counts[course] for course in COURSES
        },
        "base_test_input_count": len(original) + len(supplemental),
        "verified_original_answer_count": len(original),
        "supplemental_question_only_count": len(supplemental),
        "curated_derived_source_question_count": len(
            {
                str(
                    (case.get("structured_input") or {}).get(
                        "source_case_id"
                    )
                )
                for case in curated
                if (case.get("structured_input") or {}).get(
                    "source_case_id"
                )
            }
        ),
        "synthetic_boundary_question_count": len(boundary_cases),
        "recommended_balanced_suite": {
            "path": f"{SUITE_NAME}/all_cases.json",
            "case_count": len(selected),
            "per_course_count": PER_COURSE_QUOTA,
            "reference_answer_count": sum(answer_counts.values()),
            "question_only_count": len(selected) - sum(answer_counts.values()),
        },
    }
    write_json(output / "question_bank_inventory.json", inventory)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="生成六门课程各56题、共336题的均衡测试套件"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="统一格式目录",
    )
    args = parser.parse_args()
    manifest = build(args.output.resolve())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
