from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from normalize_dataset import (
    DEFAULT_OUTPUT,
    IMAGE_RE,
    ROOT,
    clean_markdown,
    is_fragmented_multi_image,
    natural_key,
    read_text,
    sha256,
    write_json,
    write_jsonl,
)

PROJECT_ROOT = ROOT.parent
SCHEMA_VERSION = "1.0"

COURSE_NAMES = {
    "AE": "模拟电子技术",
    "COMM": "通信原理",
    "CT": "电路理论",
    "DE": "数字电子技术",
    "DSP": "数字信号处理",
    "SS": "信号与系统",
}

SOURCE_DIRS = {
    "CT": PROJECT_ROOT / "电路理论" / "课本" / "基础篇" / "3-重置md",
    "AE": PROJECT_ROOT / "模电" / "教材",
    "DE": PROJECT_ROOT / "数电" / "教材",
    "SS": PROJECT_ROOT / "信号与系统版本一",
    "DSP": PROJECT_ROOT / "数字信号处理",
    "COMM": PROJECT_ROOT / "通信原理",
}

DOTTED_THREE_RE = re.compile(
    r"^\s*(?:#{1,4}\s*)?\*?(?P<id>\d+\.\d+\.\d+)(?=\s|$)"
)
DOTTED_TWO_RE = re.compile(
    r"^\s*(?:#{1,4}\s*)?\*?(?P<id>\d+\.\d+)(?!\.\d)(?=\s|$)"
)
HYPHEN_RE = re.compile(
    r"^\s*(?:#{1,4}\s*)?\*?(?P<id>\d+[-－]\d+)(?=\s|$)"
)
LEVEL_TWO_RE = re.compile(r"^##(?!#)\s*")
FIGURE_REF_RE = re.compile(
    r"图(?:题)?\s*(?:P\s*)?(?P<id>\d+(?:[.\-－]\d+){1,2})",
    re.IGNORECASE,
)
REVERSED_FIGURE_REF_RE = re.compile(
    r"(?:习题|题|P)\s*(?P<id>\d+(?:[.\-－]\d+){1,2})\s*图",
    re.IGNORECASE,
)
FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?:"
    r"图(?:题)?\s*(?:P\s*)?\d+(?:[.\-－]\d+){1,2}"
    r"|(?:习题|题|P)\s*\d+(?:[.\-－]\d+){1,2}\s*图"
    r")(?:\s*[-—:：]?\s*[（(]?[a-zA-Z0-9一二三四五六七八九十]*[)）]?)?\s*$",
    re.IGNORECASE,
)
TABLE_REF_RE = re.compile(
    r"表(?:题)?\s*(?P<id>\d+(?:[.\-－]\d+){1,2})",
    re.IGNORECASE,
)
DEPENDENCY_RE = re.compile(
    r"(?:重做|同|参照|根据|利用).{0,18}(?:习题|上题|前题)\s*"
    r"\d+(?:[.\-－]\d+){1,2}"
)
ANSWER_MARKER_RE = re.compile(r"(?m)^\s*(?:参考答案|答案|解答|解)\s*[:：]")
MATH_HYPHEN_TOKEN_RE = re.compile(
    r"\\\(\s*(?P<chapter>\d+)\s*-\s*"
    r"(?:\{(?P<braced>\d+)(?P<suffix>[A-Za-z]*)\}|(?P<plain>\d+))"
    r"\s*\\\)"
)


@dataclass(frozen=True)
class ExerciseRegion:
    course: str
    source_path: Path
    start_line: int
    lines: list[str]


@dataclass
class ParsedQuestion:
    course: str
    source_path: Path
    source_problem_id: str
    chapter: int
    start_line: int
    raw_text: str
    image_paths: list[Path]
    image_tokens: set[str]


def project_relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT).as_posix()


def canonical_token(value: str) -> str:
    return re.sub(r"[.－]", "-", value.strip().upper().replace("P", ""))


def canonical_problem_key(course: str, value: str) -> str:
    match = re.search(r"\d+(?:[.\-－]\d+){1,2}", value)
    token = canonical_token(match.group(0)) if match else value.strip().casefold()
    return f"{course}:{token}"


def figure_tokens(text: str) -> set[str]:
    text = normalize_ocr_question_tokens(text)
    return {
        canonical_token(match.group("id"))
        for pattern in (FIGURE_REF_RE, REVERSED_FIGURE_REF_RE)
        for match in pattern.finditer(text)
    }


def normalized_text_hash(value: str) -> str:
    normalized = re.sub(r"\s+", "", value).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_ocr_question_tokens(text: str) -> str:
    def replace_math_token(match: re.Match[str]) -> str:
        number = match.group("braced") or match.group("plain")
        suffix = match.group("suffix") or ""
        separator = " " if suffix else ""
        return f"{match.group('chapter')}-{number}{separator}{suffix}"

    text = MATH_HYPHEN_TOKEN_RE.sub(replace_math_token, text)
    text = re.sub(
        r"(?m)^(\s*\d+-\d{2})(?=\d\s*(?:[μu]?[FHA]|Ω)\b)",
        r"\1 ",
        text,
    )
    return text


def strip_media_markup(text: str) -> str:
    cleaned = clean_markdown(normalize_ocr_question_tokens(text))
    lines = [
        line
        for line in cleaned.splitlines()
        if not FIGURE_CAPTION_RE.match(line)
    ]
    return "\n".join(lines).strip()


def first_problem_id(lines: list[str], pattern: re.Pattern[str]) -> str | None:
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group("id").replace("－", "-")
    return None


def regions_after_heading(
    course: str,
    source_path: Path,
    heading_re: re.Pattern[str],
    *,
    stop_at_next_level_two: bool,
) -> list[ExerciseRegion]:
    lines = read_text(source_path).splitlines()
    regions: list[ExerciseRegion] = []
    for index, line in enumerate(lines):
        if not heading_re.match(line):
            continue
        end = len(lines)
        if stop_at_next_level_two:
            for cursor in range(index + 1, len(lines)):
                if LEVEL_TWO_RE.match(lines[cursor]):
                    end = cursor
                    break
        regions.append(
            ExerciseRegion(
                course=course,
                source_path=source_path,
                start_line=index + 2,
                lines=lines[index + 1 : end],
            )
        )
    return regions


def collect_regions() -> list[ExerciseRegion]:
    regions: list[ExerciseRegion] = []

    ct_heading = re.compile(r"^\s*(?:##\s*)?习题\s*\d+\s*$")
    for path in sorted(
        SOURCE_DIRS["CT"].glob("*.md"),
        key=lambda p: natural_key(p.name),
    ):
        if path.name == "目录.md":
            continue
        lines = read_text(path).splitlines()
        for index, line in enumerate(lines):
            if not ct_heading.match(line):
                continue
            end = len(lines)
            for cursor in range(index + 1, len(lines)):
                if re.match(r"^\s*(?:##\s*)?习题\s*\d+\s*参考答案", lines[cursor]):
                    end = cursor
                    break
            regions.append(
                ExerciseRegion("CT", path, index + 2, lines[index + 1 : end])
            )

    ae_heading = re.compile(r"^##\s*习\s*题\s*$")
    for path in sorted(
        SOURCE_DIRS["AE"].glob("*.md"),
        key=lambda p: natural_key(p.name),
    ):
        regions.extend(
            regions_after_heading(
                "AE", path, ae_heading, stop_at_next_level_two=False
            )
        )

    for path in sorted(
        SOURCE_DIRS["DE"].glob("数电_第*章.md"),
        key=lambda p: natural_key(p.name),
    ):
        lines = read_text(path).splitlines()
        last_level_two = max(
            (index for index, line in enumerate(lines) if LEVEL_TWO_RE.match(line)),
            default=-1,
        )
        if last_level_two >= 0:
            regions.append(
                ExerciseRegion(
                    "DE",
                    path,
                    last_level_two + 2,
                    lines[last_level_two + 1 :],
                )
            )

    standard_heading = re.compile(r"^##\s*习\s*题\s*$")
    for course in ("SS", "DSP", "COMM"):
        for path in sorted(
            SOURCE_DIRS[course].glob("*.md"), key=lambda p: natural_key(p.name)
        ):
            regions.extend(
                regions_after_heading(
                    course,
                    path,
                    standard_heading,
                    stop_at_next_level_two=True,
                )
            )
    return regions


def resolve_image(source_path: Path, raw: str) -> Path:
    raw_path = raw.strip().strip("<>").split(maxsplit=1)[0]
    candidate = (source_path.parent / raw_path).resolve()
    if candidate.is_file():
        return candidate
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        alternate = candidate.with_suffix(suffix)
        if alternate.is_file():
            return alternate
    return candidate


def nearby_figure_tokens(
    lines: list[str],
    line_index: int,
    image_text: str,
) -> set[str]:
    context = [image_text]
    for cursor in range(max(0, line_index - 1), min(len(lines), line_index + 3)):
        context.append(lines[cursor])
    return figure_tokens("\n".join(context))


def parse_region(
    region: ExerciseRegion,
    pattern: re.Pattern[str],
) -> tuple[list[ParsedQuestion], list[dict[str, Any]]]:
    if region.course in {"CT", "COMM"}:
        inline_re = re.compile(r"(?<![\d.])\*?(?P<id>\d+[-－]\d+)(?=\s)")
    elif region.course in {"AE", "DE"}:
        inline_re = re.compile(
            r"(?<![\d.])\*?(?P<id>\d+\.\d+\.\d+)(?=\s)"
        )
    else:
        inline_re = re.compile(
            r"(?<![\d.])\*?(?P<id>\d+\.\d+)(?!\.\d)(?=\s)"
        )

    expanded_lines: list[str] = []
    source_line_indexes: list[int] = []
    for source_index, line in enumerate(region.lines):
        line = normalize_ocr_question_tokens(line)
        split_points = [0]
        for match in inline_re.finditer(line):
            if match.start() == 0:
                continue
            prefix = line[: match.start()].rstrip()
            if prefix.endswith(
                ("。", "；", ";", "？", "?", "！", "!", ")", "）", "]", "】")
            ):
                split_points.append(match.start())
        split_points.append(len(line))
        for left, right in zip(split_points, split_points[1:], strict=False):
            segment = line[left:right].strip()
            if segment:
                expanded_lines.append(segment)
                source_line_indexes.append(source_index)
        if not line.strip():
            expanded_lines.append("")
            source_line_indexes.append(source_index)

    starts: list[tuple[int, str]] = []
    for index, line in enumerate(expanded_lines):
        match = pattern.match(line)
        if match:
            starts.append((index, match.group("id").replace("－", "-")))
    if not starts:
        return [], [
            {
                "course": region.course,
                "source": project_relative(region.source_path),
                "reason": "exercise_region_has_no_question_ids",
            }
        ]

    occurrences: list[dict[str, Any]] = []
    for line_index, line in enumerate(expanded_lines):
        for match in IMAGE_RE.finditer(line):
            path = resolve_image(region.source_path, match.group("path"))
            occurrences.append(
                {
                    "line_index": line_index,
                    "path": path,
                    "tokens": nearby_figure_tokens(
                        expanded_lines, line_index, match.group(0)
                    ),
                }
            )

    questions: list[ParsedQuestion] = []
    for position, (start, problem_id) in enumerate(starts):
        end = (
            starts[position + 1][0]
            if position + 1 < len(starts)
            else len(expanded_lines)
        )
        block_lines = expanded_lines[start:end]
        raw_text = "\n".join(block_lines).strip()
        chapter = int(re.match(r"\d+", problem_id).group(0))
        narrative_text = strip_media_markup(raw_text)
        wanted_tokens = figure_tokens(narrative_text)
        if not wanted_tokens and "图" in narrative_text:
            wanted_tokens.add(canonical_token(problem_id))

        image_paths: list[Path] = []
        image_tokens: set[str] = set()
        for occurrence in occurrences:
            tokens = occurrence["tokens"]
            physically_inside = start <= occurrence["line_index"] < end
            token_match = bool(wanted_tokens.intersection(tokens))
            token_points_elsewhere = bool(tokens) and not token_match
            if token_match or (physically_inside and not token_points_elsewhere):
                path = occurrence["path"]
                if path not in image_paths:
                    image_paths.append(path)
                image_tokens.update(tokens)

        questions.append(
            ParsedQuestion(
                course=region.course,
                source_path=region.source_path,
                source_problem_id=problem_id,
                chapter=chapter,
                start_line=region.start_line + source_line_indexes[start],
                raw_text=raw_text,
                image_paths=image_paths,
                image_tokens=image_tokens,
            )
        )
    return questions, []


def parse_all_regions(
    regions: list[ExerciseRegion],
) -> tuple[list[ParsedQuestion], list[dict[str, Any]]]:
    patterns = {
        "AE": DOTTED_THREE_RE,
        "COMM": HYPHEN_RE,
        "CT": HYPHEN_RE,
        "DE": DOTTED_THREE_RE,
        "DSP": DOTTED_TWO_RE,
        "SS": DOTTED_TWO_RE,
    }
    questions: list[ParsedQuestion] = []
    exclusions: list[dict[str, Any]] = []
    for region in regions:
        parsed, region_exclusions = parse_region(region, patterns[region.course])
        questions.extend(parsed)
        exclusions.extend(region_exclusions)
    return questions, exclusions


def question_text(question: ParsedQuestion) -> str:
    text = strip_media_markup(question.raw_text)
    lines = text.splitlines()
    if lines:
        lines = [
            lines[0],
            *[
                line
                for line in lines[1:]
                if not re.match(r"^\s*#{1,4}\s+", line)
                and line.strip()
                not in {
                    "综合检测",
                    "基础练习",
                    "能力提升",
                    "思考题",
                    "复习思考题",
                }
            ],
        ]
    text = "\n".join(lines)
    text = re.sub(r"(?m)^\s*#{1,4}\s*", "", text)
    return text.strip()


def incompleteness_reasons(
    question: ParsedQuestion,
    message: str,
) -> list[str]:
    reasons: list[str] = []
    body = re.sub(
        rf"^\*?{re.escape(question.source_problem_id)}\s*", "", message
    ).strip()
    if len(re.sub(r"\s+", "", body)) < 10:
        reasons.append("question_text_too_short")
    if ANSWER_MARKER_RE.search(message):
        reasons.append("answer_marker_in_question")
    if DEPENDENCY_RE.search(message):
        reasons.append("depends_on_another_exercise")
    missing_paths = [path for path in question.image_paths if not path.is_file()]
    if missing_paths:
        reasons.append("missing_question_image")
    if is_fragmented_multi_image(question.image_paths):
        reasons.append("fragmented_multi_image_question")

    referenced_figures = figure_tokens(message)
    if referenced_figures - question.image_tokens:
        reasons.append("referenced_figure_not_extracted")

    table_refs = list(TABLE_REF_RE.finditer(message))
    if table_refs and "|" not in message:
        reasons.append("referenced_table_not_embedded")
    return sorted(set(reasons))


def copy_asset(source: Path, output: Path, course: str) -> Path:
    digest = sha256(source)
    safe_name = re.sub(r"[^0-9A-Za-z._-]+", "_", source.name)
    target = output / "supplemental_assets" / course / f"{digest[:16]}-{safe_name}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file() or sha256(target) != digest:
        shutil.copy2(source, target)
    return target


def make_case(
    question: ParsedQuestion,
    message: str,
    copied_assets: list[Path],
) -> dict[str, Any]:
    course = question.course
    problem_id = question.source_problem_id
    refs = [
        {
            "path": path.resolve().relative_to(ROOT).as_posix(),
            "media_type": mimetypes.guess_type(path.name)[0]
            or "application/octet-stream",
            "sha256": sha256(path),
            "role": "question",
        }
        for path in copied_assets
    ]
    input_type = (
        "text"
        if not refs
        else "text_and_image"
        if len(refs) == 1
        else "text_and_multi_image"
    )
    return {
        "case_id": f"KB-{course}-{problem_id.replace('.', '-').replace('－', '-')}",
        "title": f"{COURSE_NAMES[course]}课后习题 {problem_id}",
        "course": course,
        "task_family": "ACADEMIC_SOLVING",
        "intent": "solve_problem",
        "problem_type": None,
        "difficulty": "medium",
        "input_type": input_type,
        "message": message,
        "file_refs": refs,
        "structured_input": {
            "source_problem_id": problem_id,
            "chapter": question.chapter,
            "source_question_path": project_relative(question.source_path),
            "source_line": question.start_line,
            "source_collection": "local_course_knowledge",
        },
        "task_options": {
            "prefer_internal_agents": True,
            "use_local_rag": True,
            "response_depth": "full",
        },
        "expected_agent": "ACADEMIC_PROBLEM_SOLVER",
        "expected_course_pack": course,
        "expected_execution_paths": [],
        "expected_statuses": ["success", "partial"],
        "reference_answer": None,
        "tags": ["knowledge_exercise", "question_only", course.casefold()],
        "source": project_relative(question.source_path),
        "notes": "仅从课程知识库提取题目与题图，未提取或生成答案",
        "input_source": "private",
        "judge_type": "human",
        "provenance": {
            "source_type": "private",
            "source_name": f"{COURSE_NAMES[course]}本地课程知识库课后习题",
            "license_or_authorization": "",
            "publishable": False,
        },
        "official_scoring": False,
        "requires_manual_review": False,
    }


def load_original_cases(output: Path) -> list[dict[str, Any]]:
    path = output / "all_cases.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"缺少 {path}；请先运行 normalize_dataset.py 生成核验后的原题库"
        )
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ValueError(f"{path} 顶层必须是 {{\"cases\": [...]}}")
    return cases


def build(output: Path) -> dict[str, Any]:
    original_cases = load_original_cases(output)
    generated_assets = output / "supplemental_assets"
    if generated_assets.is_dir():
        shutil.rmtree(generated_assets)
    original_keys = {
        canonical_problem_key(
            str(case["course"]),
            str((case.get("structured_input") or {}).get("source_problem_id") or ""),
        )
        for case in original_cases
    }
    original_hashes = {
        (str(case["course"]), normalized_text_hash(str(case.get("message") or "")))
        for case in original_cases
    }

    regions = collect_regions()
    parsed, exclusions = parse_all_regions(regions)
    accepted: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    seen_hashes: set[tuple[str, str]] = set()
    exclusion_counts: Counter[str] = Counter(item["reason"] for item in exclusions)

    for question in parsed:
        message = question_text(question)
        reasons = incompleteness_reasons(question, message)
        key = canonical_problem_key(question.course, question.source_problem_id)
        text_key = (question.course, normalized_text_hash(message))
        if key in original_keys or text_key in original_hashes:
            reasons.append("already_in_verified_test_bank")
        if key in seen_keys or text_key in seen_hashes:
            reasons.append("duplicate_supplemental_question")
        if reasons:
            unique_reasons = sorted(set(reasons))
            exclusion_counts.update(unique_reasons)
            exclusions.append(
                {
                    "course": question.course,
                    "source_problem_id": question.source_problem_id,
                    "source": project_relative(question.source_path),
                    "source_line": question.start_line,
                    "reasons": unique_reasons,
                }
            )
            continue

        copied_assets = [
            copy_asset(path, output, question.course) for path in question.image_paths
        ]
        case = make_case(question, message, copied_assets)
        accepted.append(case)
        seen_keys.add(key)
        seen_hashes.add(text_key)

    course_order = ("CT", "AE", "DE", "SS", "DSP", "COMM")
    accepted.sort(
        key=lambda case: (
            course_order.index(str(case["course"])),
            natural_key(str(case["case_id"])),
        )
    )
    by_course: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in accepted:
        by_course[str(case["course"])].append(case)

    supplemental_root = output / "supplemental"
    for course in course_order:
        cases = by_course[course]
        write_json(supplemental_root / "cases" / f"{course}.json", {"cases": cases})
        write_jsonl(supplemental_root / "jsonl" / f"{course}.jsonl", cases)
    write_json(supplemental_root / "all_questions.json", {"cases": accepted})
    write_jsonl(supplemental_root / "all_questions.jsonl", accepted)
    write_json(supplemental_root / "excluded_questions.json", {"items": exclusions})

    combined = [*original_cases, *accepted]
    write_json(output / "all_test_inputs.json", {"cases": combined})
    write_jsonl(output / "all_test_inputs.jsonl", combined)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "format": "EvaluationCase-compatible question-only JSON and JSONL",
        "question_only": True,
        "reference_answers_extracted": False,
        "exercise_region_count": len(regions),
        "parsed_question_count": len(parsed),
        "accepted_question_count": len(accepted),
        "course_counts": {
            course: len(by_course[course]) for course in course_order
        },
        "input_mode_counts": dict(
            sorted(Counter(case["input_type"] for case in accepted).items())
        ),
        "question_attachment_count": sum(
            len(case["file_refs"]) for case in accepted
        ),
        "excluded_question_count": len(exclusions),
        "exclusion_reason_counts": dict(sorted(exclusion_counts.items())),
        "source_directories": {
            course: project_relative(path) for course, path in SOURCE_DIRS.items()
        },
        "combined_test_input_count": len(combined),
        "verified_original_count": len(original_cases),
    }
    write_json(supplemental_root / "manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从六门课程知识库课后习题中提取题目和题图（不提取答案）"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="统一格式目录，默认：真实测试题/统一格式",
    )
    args = parser.parse_args()
    manifest = build(args.output.resolve())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
