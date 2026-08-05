from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import struct
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "统一格式"
SCHEMA_VERSION = "1.0"

COURSE_NAMES = {
    "AE": "模拟电子技术",
    "CT": "电路理论",
    "DE": "数字电子技术",
    "SS": "信号与系统",
}

IMAGE_RE = re.compile(
    r"!\[[^\]]*]\((?P<path>[^)]+)\)(?:\s*\{[^}]*\})?",
    flags=re.MULTILINE,
)
BLOCKING_FLAGS = {
    "fragmented_multi_image_question",
    "missing_reference_answer",
    "possibly_incomplete_question",
    "source_text_disagreement",
}
EXCLUDED_CASES = {
    "AE-1-5-6": "原题题干不完整且没有参考答案",
    "DE-2-2-2": "题目与参考答案中的文字及公式明显不一致",
    "DE-2-3-1": "题目与参考答案中的文字及公式明显不一致",
    "DE-10-2-3": "原题没有参考答案",
}
FRAGMENTED_MULTI_IMAGE_REASON = (
    "题面被拆成主图和互相依赖的微小公式或标签图片，信息严重割裂"
)
MIN_COHERENT_IMAGE_WIDTH = 120
MIN_COHERENT_IMAGE_HEIGHT = 80


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def root_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def audit_relative(path: Path) -> str:
    resolved = path.resolve()
    for base in (ROOT, ROOT.parent):
        try:
            return resolved.relative_to(base).as_posix()
        except ValueError:
            continue
    return path.name


def natural_key(value: str) -> list[int | str]:
    return [
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", value)
    ]


def clean_markdown(text: str) -> str:
    text = IMAGE_RE.sub("", text)
    text = re.sub(r"(?m)^##\s+第.+章\s*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def markdown_image_paths(text: str, source_path: Path) -> list[Path]:
    values: list[Path] = []
    for match in IMAGE_RE.finditer(text):
        raw = match.group("path").strip().strip("<>")
        raw = raw.split(maxsplit=1)[0]
        if raw.startswith(("http://", "https://", "data:")):
            continue
        candidate = (source_path.parent / raw).resolve()
        if candidate not in values:
            values.append(candidate)
    return values


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_dimensions(path: Path) -> tuple[int, int] | None:
    """Read PNG or JPEG dimensions without adding an image dependency."""
    if not path.is_file():
        return None
    suffix = path.suffix.casefold()
    if suffix in {".jpg", ".jpeg"}:
        start_of_frame = {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }
        with path.open("rb") as stream:
            if stream.read(2) != b"\xff\xd8":
                return None
            while True:
                marker_start = stream.read(1)
                if not marker_start:
                    return None
                if marker_start != b"\xff":
                    continue
                marker = stream.read(1)
                while marker == b"\xff":
                    marker = stream.read(1)
                if not marker:
                    return None
                marker_value = marker[0]
                if marker_value in {0xD8, 0xD9}:
                    continue
                length_raw = stream.read(2)
                if len(length_raw) != 2:
                    return None
                length = struct.unpack(">H", length_raw)[0]
                if length < 2:
                    return None
                if marker_value in start_of_frame:
                    frame = stream.read(5)
                    if len(frame) != 5:
                        return None
                    height, width = struct.unpack(">HH", frame[1:5])
                    return width, height
                stream.seek(length - 2, 1)
    if suffix != ".png":
        return None
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", header[16:24])


def fragmented_multi_image_audit(
    paths: Iterable[Path],
) -> dict[str, Any] | None:
    """Identify a multi-image prompt containing tiny dependent fragments."""
    values = list(paths)
    if len(values) <= 1:
        return None
    dimensions = [image_dimensions(path) for path in values]
    if any(value is None for value in dimensions):
        return None
    measured = [
        {
            "path": audit_relative(path),
            "width": int(size[0]),
            "height": int(size[1]),
        }
        for path, size in zip(values, dimensions, strict=True)
        if size is not None
    ]
    fragments = [
        item
        for item in measured
        if item["width"] < MIN_COHERENT_IMAGE_WIDTH
        or item["height"] < MIN_COHERENT_IMAGE_HEIGHT
    ]
    if not fragments:
        return None
    return {
        "policy": "multi_image_with_tiny_dependent_fragment",
        "minimum_coherent_width": MIN_COHERENT_IMAGE_WIDTH,
        "minimum_coherent_height": MIN_COHERENT_IMAGE_HEIGHT,
        "asset_dimensions": measured,
        "fragment_count": len(fragments),
    }


def is_fragmented_multi_image(paths: Iterable[Path]) -> bool:
    return fragmented_multi_image_audit(paths) is not None


def file_refs(paths: Iterable[Path]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for path in paths:
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        refs.append(
            {
                "path": root_relative(path),
                "media_type": media_type,
                "sha256": sha256(path) if path.is_file() else "",
                "role": "question",
            }
        )
    return refs


def input_type_for(refs: list[dict[str, str]]) -> str:
    if not refs:
        return "text"
    if len(refs) == 1:
        return "text_and_image"
    return "text_and_multi_image"


def make_case(
    *,
    case_id: str,
    title: str,
    course: str,
    source_problem_id: str,
    chapter: int,
    message: str,
    answer: str | None,
    attachments: Iterable[Path],
    answer_attachments: Iterable[Path] = (),
    question_path: Path,
    answer_path: Path | None,
    problem_type: str | None = None,
    difficulty: str = "medium",
    flags: Iterable[str] = (),
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quality_flags = sorted(set(flags))
    refs = file_refs(attachments)
    structured_input: dict[str, Any] = {
        "source_problem_id": source_problem_id,
        "chapter": chapter,
        "source_question_path": root_relative(question_path),
    }
    if answer_path is not None:
        structured_input["source_answer_path"] = root_relative(answer_path)
    answer_refs = file_refs(answer_attachments)
    for ref in answer_refs:
        ref["role"] = "reference_answer"
    if answer_refs:
        structured_input["reference_answer_assets"] = answer_refs
    if metadata:
        structured_input["source_metadata"] = metadata
    blocking_review = bool(BLOCKING_FLAGS.intersection(quality_flags))

    return {
        "case_id": case_id,
        "title": title.strip() or f"{COURSE_NAMES[course]} {source_problem_id}",
        "course": course,
        "task_family": "ACADEMIC_SOLVING",
        "intent": "solve_problem",
        "problem_type": problem_type or None,
        "difficulty": difficulty,
        "input_type": input_type_for(refs),
        "message": message.strip(),
        "file_refs": refs,
        "structured_input": structured_input,
        "task_options": {
            "prefer_internal_agents": True,
            "use_local_rag": True,
            "response_depth": "full",
        },
        "expected_agent": "ACADEMIC_PROBLEM_SOLVER",
        "expected_course_pack": course,
        "expected_execution_paths": [],
        "expected_statuses": ["success", "partial"],
        "reference_answer": answer.strip() if answer and answer.strip() else None,
        "tags": [
            "real_test_bank",
            course.casefold(),
            *(["quality_flagged"] if quality_flags else []),
            *(["needs_review"] if blocking_review else []),
        ],
        "source": root_relative(question_path),
        "notes": (
            "quality_flags=" + ",".join(quality_flags) if quality_flags else None
        ),
        "input_source": "private",
        "judge_type": "hybrid",
        "provenance": {
            "source_type": "private",
            "source_name": f"{COURSE_NAMES[course]}真实测试题库",
            "license_or_authorization": "",
            "publishable": False,
        },
        "official_scoring": False,
        "requires_manual_review": blocking_review,
    }


def section(text: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
        text,
    )
    return match.group("body").strip() if match else ""


def markdown_document_body(text: str) -> str:
    """Remove the title and leading metadata, while keeping answer sections."""
    lines = text.splitlines()
    index = 0
    if lines and re.match(r"^#\s+", lines[0]):
        index = 1
    while index < len(lines) and (
        not lines[index].strip() or re.match(r"^\s*-\s+", lines[index])
    ):
        index += 1
    return "\n".join(lines[index:]).strip()


def first_line_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        value = re.sub(r"^[#\s]+", "", line).strip()
        if value:
            return value[:160]
    return fallback


def normalize_ct() -> list[dict[str, Any]]:
    base = ROOT / "电路理论测试集" / "题目整理"
    paths = sorted(
        base.rglob("题目与答案.md"),
        key=lambda item: natural_key(item.as_posix()),
    )
    cases: list[dict[str, Any]] = []
    for path in paths:
        match = re.fullmatch(r"(?P<chapter>\d+)-(?P<number>\d+)", path.parent.name)
        if match is None:
            raise ValueError(f"无法识别电路题号目录: {path.parent}")
        chapter = int(match.group("chapter"))
        number = int(match.group("number"))
        problem_id = f"{chapter}-{number}"
        raw = read_text(path)
        question = section(raw, "题目")
        answer = section(raw, "解答")
        image_block = section(raw, "原题图片")
        attachments = markdown_image_paths(image_block, path)
        flags: list[str] = []
        fragmentation_audit = fragmented_multi_image_audit(attachments)
        if fragmentation_audit is not None:
            flags.append("fragmented_multi_image_question")
        if not answer:
            flags.append("missing_reference_answer")
        if any(not item.is_file() for item in attachments):
            flags.append("missing_question_asset")
        cases.append(
            make_case(
                case_id=f"CT-C{chapter:02d}-Q{number:02d}",
                title=f"电路理论 第{chapter}章 题{problem_id}",
                course="CT",
                source_problem_id=problem_id,
                chapter=chapter,
                message=clean_markdown(question),
                answer=clean_markdown(answer),
                attachments=attachments,
                answer_attachments=markdown_image_paths(answer, path),
                question_path=path,
                answer_path=path,
                flags=flags,
                metadata=(
                    {"fragmented_multi_image_audit": fragmentation_audit}
                    if fragmentation_audit is not None
                    else None
                ),
            )
        )
    return cases


def analog_image_token(path: Path) -> str | None:
    match = re.search(r"(\d+\.\d+(?:\.\d+)?[a-z]?)", path.stem, flags=re.I)
    return match.group(1).casefold() if match else None


def question_figure_tokens(text: str, problem_id: str) -> set[str]:
    values = {problem_id.casefold()}
    for token in re.findall(
        r"图(?:题|解)?\s*(\d+\.\d+(?:\.\d+)?[a-z]?)",
        text,
        flags=re.I,
    ):
        values.add(token.casefold())
    return values


def normalize_ae() -> list[dict[str, Any]]:
    path = ROOT / "模电测试集" / "模电测试集.md"
    lines = read_text(path).splitlines()
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^(\d+\.\d+\.\d+)\s", line)
        if match:
            starts.append((index, match.group(1)))

    all_images: list[tuple[int, Path]] = []
    for index, line in enumerate(lines):
        for image in markdown_image_paths(line, path):
            all_images.append((index, image))

    spans: list[dict[str, Any]] = []
    for position, (start, problem_id) in enumerate(starts):
        next_start = (
            starts[position + 1][0]
            if position + 1 < len(starts)
            else len(lines)
        )
        answer_start = next(
            (
                index
                for index in range(start + 1, next_start)
                if re.match(r"^\s*解[:：]", lines[index])
            ),
            None,
        )
        question_end = answer_start if answer_start is not None else start + 1
        question_raw = "\n".join(lines[start:question_end])
        tokens = question_figure_tokens(question_raw, problem_id)
        previous_start = starts[position - 1][0] if position else 0
        attachments: list[Path] = []
        attachment_lines: list[int] = []
        for image_line, image_path in all_images:
            in_question = start <= image_line < question_end
            token = analog_image_token(image_path)
            is_preceding_prompt = (
                previous_start <= image_line < start
                and token is not None
                and token in tokens
            )
            if in_question or is_preceding_prompt:
                if image_path not in attachments:
                    attachments.append(image_path)
                    attachment_lines.append(image_line)
        spans.append(
            {
                "start": start,
                "next_start": next_start,
                "answer_start": answer_start,
                "problem_id": problem_id,
                "question_raw": question_raw,
                "attachments": attachments,
                "attachment_lines": attachment_lines,
            }
        )

    cases: list[dict[str, Any]] = []
    for position, item in enumerate(spans):
        problem_id = str(item["problem_id"])
        chapter = int(problem_id.split(".", maxsplit=1)[0])
        answer_start = item["answer_start"]
        answer_end = int(item["next_start"])
        answer: str | None
        if position + 1 < len(spans):
            next_preceding = [
                value
                for value in spans[position + 1]["attachment_lines"]
                if value < spans[position + 1]["start"]
            ]
            if next_preceding:
                answer_end = min(answer_end, min(next_preceding))
        if answer_start is not None:
            answer_raw = "\n".join(lines[answer_start:answer_end])
            answer = clean_markdown(answer_raw)
        else:
            answer_raw = "\n".join(
                lines[int(item["start"]) + 1 : answer_end]
            )
            inferred = clean_markdown(answer_raw)
            answer = inferred or None
        question = clean_markdown(str(item["question_raw"]))
        flags: list[str] = []
        if not answer:
            flags.append("missing_reference_answer")
        elif answer_start is None:
            flags.append("answer_boundary_inferred")
        if problem_id == "1.5.6":
            flags.append("possibly_incomplete_question")
        if any(not path_item.is_file() for path_item in item["attachments"]):
            flags.append("missing_question_asset")
        cases.append(
            make_case(
                case_id="AE-" + problem_id.replace(".", "-"),
                title=f"模拟电子技术 题{problem_id}",
                course="AE",
                source_problem_id=problem_id,
                chapter=chapter,
                message=question,
                answer=answer,
                attachments=item["attachments"],
                answer_attachments=markdown_image_paths(answer_raw, path),
                question_path=path,
                answer_path=path,
                flags=flags,
            )
        )
    return cases


def flexible_problem_pattern(problem_id: str) -> re.Pattern[str]:
    components = [re.escape(part) for part in problem_id.split(".")]
    return re.compile(r"^\s*" + r"\s*\.\s*".join(components) + r"\s")


def normalize_de() -> list[dict[str, Any]]:
    base = ROOT / "数电测试集"
    question_path = base / "数电测试集题目.md"
    answer_path = base / "数电测试集答案.md"
    question_lines = read_text(question_path).splitlines()
    answer_lines = read_text(answer_path).splitlines()

    question_starts: list[tuple[int, int, str]] = []
    for index, line in enumerate(question_lines):
        match = re.match(r"^(\d+)\.\s+(\d+\.\d+\.\d+)\s", line)
        if match:
            question_starts.append((index, int(match.group(1)), match.group(2)))

    manual_patterns = {
        "3.2.11": re.compile(r"^表题解\s+3\.2\.11\s*$"),
        "6.1.7": re.compile(r"^解:\s*因为该同步时序电路使用"),
        "7.1.4": re.compile(r"^解:\s*\(1\)\s*设.*ROM"),
    }
    inferred_ids = set(manual_patterns)
    answer_starts: dict[str, int] = {}
    for _, _, problem_id in question_starts:
        pattern = manual_patterns.get(problem_id, flexible_problem_pattern(problem_id))
        found = next(
            (
                index
                for index, line in enumerate(answer_lines)
                if pattern.search(line)
            ),
            None,
        )
        if found is not None:
            answer_starts[problem_id] = found

    cases: list[dict[str, Any]] = []
    for position, (start, ordinal, problem_id) in enumerate(question_starts):
        end = (
            question_starts[position + 1][0]
            if position + 1 < len(question_starts)
            else len(question_lines)
        )
        question_raw = "\n".join(question_lines[start:end])
        question_raw = re.sub(
            rf"^\s*{ordinal}\.\s+",
            "",
            question_raw,
            count=1,
        )
        attachments = markdown_image_paths(question_raw, question_path)
        corrected_attachments: list[Path] = []
        extension_corrected = False
        for attachment in attachments:
            if attachment.is_file():
                corrected_attachments.append(attachment)
                continue
            alternatives = [
                attachment.with_suffix(extension)
                for extension in (".png", ".jpg", ".jpeg", ".webp")
                if attachment.with_suffix(extension).is_file()
            ]
            if len(alternatives) == 1:
                corrected_attachments.append(alternatives[0])
                extension_corrected = True
            else:
                corrected_attachments.append(attachment)
        attachments = corrected_attachments
        question = clean_markdown(question_raw)

        answer: str | None = None
        answer_assets: list[Path] = []
        flags: list[str] = []
        answer_start = answer_starts.get(problem_id)
        if answer_start is not None:
            following_starts = [
                value
                for _, _, later_id in question_starts[position + 1 :]
                if (value := answer_starts.get(later_id)) is not None
                and value > answer_start
            ]
            answer_end = (
                min(following_starts) if following_starts else len(answer_lines)
            )
            answer_chunk = "\n".join(answer_lines[answer_start:answer_end])
            answer_assets = markdown_image_paths(answer_chunk, answer_path)
            if problem_id not in inferred_ids:
                solution_match = re.search(r"(?m)^\s*解[:：]", answer_chunk)
                if solution_match:
                    answer_chunk = answer_chunk[solution_match.start() :]
            answer = clean_markdown(answer_chunk)
        else:
            flags.append("missing_reference_answer")
        if problem_id in inferred_ids:
            flags.append("answer_boundary_inferred")
        if extension_corrected:
            flags.append("asset_extension_corrected")
        if problem_id in {"2.2.2", "2.3.1"}:
            flags.append("source_text_disagreement")
        if any(not item.is_file() for item in attachments):
            flags.append("missing_question_asset")

        chapter = int(problem_id.split(".", maxsplit=1)[0])
        cases.append(
            make_case(
                case_id="DE-" + problem_id.replace(".", "-"),
                title=f"数字电子技术 题{problem_id}",
                course="DE",
                source_problem_id=problem_id,
                chapter=chapter,
                message=question,
                answer=answer,
                attachments=attachments,
                answer_attachments=answer_assets,
                question_path=question_path,
                answer_path=answer_path,
                flags=flags,
                metadata={"source_ordinal": ordinal},
            )
        )
    return cases


def difficulty_for(value: str | None) -> str:
    return {
        "基础": "easy",
        "综合": "medium",
        "提高": "hard",
    }.get((value or "").strip(), "medium")


def ss_duplicate_summary() -> dict[str, Any]:
    base = ROOT / "信号与系统测试集"
    duplicate = base / "signal_systems_original_question_bank_48"
    canonical_files = [
        path
        for path in base.rglob("*")
        if path.is_file() and duplicate not in path.parents
    ]
    matched = 0
    missing: list[str] = []
    different: list[str] = []
    for canonical in canonical_files:
        relative = canonical.relative_to(base)
        counterpart = duplicate / relative
        if not counterpart.is_file():
            missing.append(relative.as_posix())
        elif sha256(canonical) != sha256(counterpart):
            different.append(relative.as_posix())
        else:
            matched += 1
    exact = not missing and not different and bool(canonical_files)
    return {
        "path": root_relative(duplicate),
        "status": "exact_duplicate" if exact else "not_exact_duplicate",
        "verified_duplicate_file_count": matched,
        "canonical_file_count": len(canonical_files),
        "missing_counterpart_count": len(missing),
        "different_file_count": len(different),
        "reason": (
            "与信号与系统测试集顶层规范副本逐文件SHA-256一致"
            if exact
            else "重复目录与顶层副本存在差异，转换仍以顶层manifest为准"
        ),
    }


def normalize_ss() -> list[dict[str, Any]]:
    base = ROOT / "信号与系统测试集"
    manifest_path = base / "manifest.jsonl"
    rows = [
        json.loads(line)
        for line in read_text(manifest_path).splitlines()
        if line.strip()
    ]
    cases: list[dict[str, Any]] = []
    for row in rows:
        problem_id = str(row["id"])
        chapter = int(row["chapter"])
        question_path = base / str(row["question_file"])
        answer_path = base / str(row["answer_file"])
        question_raw = section(read_text(question_path), "题目")
        answer_raw = markdown_document_body(read_text(answer_path))
        attachments = markdown_image_paths(question_raw, question_path)

        chapter_root = base / str(
            row.get("chapter_root") or f"chapters/chapter{chapter}"
        )
        for image in row.get("images") or []:
            candidate = (chapter_root / str(image)).resolve()
            if candidate not in attachments:
                attachments.append(candidate)

        flags: list[str] = []
        if not answer_raw:
            flags.append("missing_reference_answer")
        if any(not item.is_file() for item in attachments):
            flags.append("missing_question_asset")
        metadata = {
            key: row[key]
            for key in (
                "source_book",
                "source_problem",
                "source_pages",
                "adaptation",
                "preservation",
            )
            if row.get(key) not in (None, "")
        }
        cases.append(
            make_case(
                case_id=problem_id,
                title=str(row.get("title") or problem_id),
                course="SS",
                source_problem_id=str(row.get("source_problem") or problem_id),
                chapter=chapter,
                message=clean_markdown(question_raw),
                answer=clean_markdown(answer_raw),
                attachments=attachments,
                answer_attachments=markdown_image_paths(answer_raw, answer_path),
                question_path=question_path,
                answer_path=answer_path,
                problem_type=str(row.get("type") or "") or None,
                difficulty=difficulty_for(row.get("difficulty")),
                flags=flags,
                metadata=metadata,
            )
        )
    return cases


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, cases: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for case in cases:
            stream.write(json.dumps(case, ensure_ascii=False) + "\n")


def build(output: Path) -> dict[str, Any]:
    raw_by_course = {
        "AE": normalize_ae(),
        "CT": normalize_ct(),
        "DE": normalize_de(),
        "SS": normalize_ss(),
    }
    fragmented_cases = {
        str(case["case_id"]): FRAGMENTED_MULTI_IMAGE_REASON
        for case in raw_by_course["CT"]
        if "fragmented_multi_image_question" in str(case.get("notes") or "")
    }
    fragmented_case_audits = [
        {
            "case_id": str(case["case_id"]),
            **dict(
                ((case.get("structured_input") or {}).get("source_metadata") or {}).get(
                    "fragmented_multi_image_audit"
                )
                or {}
            ),
        }
        for case in raw_by_course["CT"]
        if str(case["case_id"]) in fragmented_cases
    ]
    excluded_cases = {**EXCLUDED_CASES, **fragmented_cases}
    by_course = {
        course: [
            case
            for case in cases
            if case["case_id"] not in excluded_cases
        ]
        for course, cases in raw_by_course.items()
    }
    all_cases = [
        case
        for course in ("CT", "AE", "DE", "SS")
        for case in by_course[course]
    ]

    for course, cases in by_course.items():
        write_json(output / "cases" / f"{course}.json", {"cases": cases})
        write_jsonl(output / "jsonl" / f"{course}.jsonl", cases)
    write_json(output / "all_cases.json", {"cases": all_cases})
    write_jsonl(output / "all_cases.jsonl", all_cases)

    input_modes = Counter(case["input_type"] for case in all_cases)
    review_cases = [
        case["case_id"] for case in all_cases if case["requires_manual_review"]
    ]
    flag_counts: Counter[str] = Counter()
    for case in all_cases:
        notes = case.get("notes") or ""
        if notes.startswith("quality_flags="):
            flag_counts.update(
                filter(
                    None,
                    notes.removeprefix("quality_flags=").split(","),
                )
            )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "format": "EvaluationCase-compatible JSON and JSONL",
        "case_count": len(all_cases),
        "source_case_count": sum(len(cases) for cases in raw_by_course.values()),
        "course_counts": {
            course: len(cases) for course, cases in by_course.items()
        },
        "excluded_case_count": len(excluded_cases),
        "excluded_cases": [
            {"case_id": case_id, "reason": reason}
            for case_id, reason in sorted(excluded_cases.items())
        ],
        "fragmented_multi_image_exclusion_count": len(fragmented_cases),
        "fragmented_multi_image_case_ids": sorted(fragmented_cases),
        "fragmented_multi_image_audits": fragmented_case_audits,
        "retained_coherent_multi_image_case_ids": sorted(
            str(case["case_id"])
            for case in all_cases
            if len(case.get("file_refs") or []) > 1
        ),
        "fragmented_multi_image_policy": {
            "scope": "CT source bank",
            "rule": (
                "exclude prompts with multiple PNG assets when any asset is "
                "smaller than the coherent-image width or height threshold"
            ),
            "minimum_coherent_width": MIN_COHERENT_IMAGE_WIDTH,
            "minimum_coherent_height": MIN_COHERENT_IMAGE_HEIGHT,
            "raw_sources_preserved": True,
        },
        "input_mode_counts": dict(sorted(input_modes.items())),
        "manual_review_count": len(review_cases),
        "manual_review_case_ids": review_cases,
        "quality_flag_counts": dict(sorted(flag_counts.items())),
        "canonical_sources": {
            "AE": "模电测试集/模电测试集.md",
            "CT": "电路理论测试集/题目整理",
            "DE": [
                "数电测试集/数电测试集题目.md",
                "数电测试集/数电测试集答案.md",
            ],
            "SS": "信号与系统测试集/manifest.jsonl",
        },
        "ignored_duplicate_tree": ss_duplicate_summary(),
    }
    write_json(output / "dataset_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="将四门真实题库转换为统一评测格式")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="输出目录，默认：真实测试题/统一格式",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    manifest = build(output)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
