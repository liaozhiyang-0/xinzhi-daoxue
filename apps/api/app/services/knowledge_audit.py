from __future__ import annotations

import hashlib
import mimetypes
import re
import struct
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

COURSE_NAMES = {
    "CT": "电路理论",
    "AE": "模拟电子技术",
    "DE": "数字电子技术",
}
TEXT_EXTENSIONS = {".md", ".txt", ".json", ".csv"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
ARCHIVE_EXTENSIONS = {".zip", ".7z", ".rar"}
SUPPORTED_COURSES = frozenset({"CT", "AE", "DE"})
MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
CHAPTER_RE = re.compile(r"第[一二三四五六七八九十百零〇0-9]+章")
MOJIBAKE_MARKERS = ("�", "锟斤拷", "浣犲ソ", "鏈湴")
TEMPORARY_MARKERS = ("tmp", "temp", "draft", "草稿", "测试", "未完成", "副本")


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def checksum_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def posix_relative(path: Path, root: Path) -> str:
    resolved = path.resolve()
    root_resolved = root.resolve()
    return resolved.relative_to(root_resolved).as_posix()


def source_uri(course_id: str, relative_path: str) -> str:
    return f"kb://{course_id}/{relative_path}"


def image_uri(course_id: str, relative_path: str) -> str:
    return f"kb-image://{course_id}/{relative_path}"


@dataclass(frozen=True, slots=True)
class MarkdownImageReference:
    document_id: str
    document_relative_path: str
    image_relative_path: str
    alt_text: str
    nearby_text: str
    section: str
    line_number: int
    exists: bool


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    document_id: str
    course_id: str
    source_path: str
    relative_path: str
    file_name: str
    file_type: str
    mime_type: str
    file_size: int
    checksum: str
    title: str
    inferred_chapter: str
    content_type: str
    language: str
    source_type: str
    image_count: int
    referenced_images: tuple[str, ...]
    referring_documents: tuple[str, ...]
    parse_status: str
    quality_status: str
    index_status: str
    warnings: tuple[str, ...]
    modified_time: str
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["referenced_images"] = list(self.referenced_images)
        payload["referring_documents"] = list(self.referring_documents)
        payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True, slots=True)
class ImageEvidenceRecord:
    image_id: str
    course_id: str
    source_path: str
    resource_uri: str
    parent_document_id: str | None
    parent_chunk_id: str | None
    image_type: str
    image_caption: str
    description_source: str
    nearby_text: str
    page_or_section: str
    width: int | None
    height: int | None
    checksum: str
    parse_status: str
    quality_status: str
    warnings: tuple[str, ...]
    referring_documents: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        payload["referring_documents"] = list(self.referring_documents)
        return payload


@dataclass(frozen=True, slots=True)
class QualityIssue:
    severity: str
    course_id: str
    file_path: str
    issue_type: str
    description: str
    affects_index: bool
    suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CourseAuditSummary:
    course_id: str
    course_name: str
    root_path: str
    file_count: int
    text_count: int
    image_count: int
    other_count: int
    total_bytes: int
    directly_indexable_count: int
    needs_cleaning_count: int
    unavailable_count: int
    extension_counts: dict[str, int]
    top_directories: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["top_directories"] = list(self.top_directories)
        return payload


@dataclass(slots=True)
class AuditResult:
    manifest: list[ManifestEntry] = field(default_factory=list)
    images: list[ImageEvidenceRecord] = field(default_factory=list)
    issues: list[QualityIssue] = field(default_factory=list)
    courses: list[CourseAuditSummary] = field(default_factory=list)
    image_references: list[MarkdownImageReference] = field(default_factory=list)


def infer_content_type(path: Path, title: str, text: str = "") -> str:
    probe = f"{path.stem} {title} {text[:800]}".casefold()
    rules = (
        ("common_error", ("常见错误", "易错", "错误分析")),
        ("worked_example", ("例题", "例 ", "example")),
        ("solution", ("解答", "答案", "solution")),
        ("exercise", ("习题", "练习", "题目", "exercise")),
        ("experiment", ("实验", "仿真", "experiment")),
        ("formula", ("公式", "定理", "方程")),
        ("method", ("方法", "分析法", "步骤")),
        ("waveform", ("波形", "时序图")),
        ("circuit_diagram", ("电路图", "原理图", "连接图", "逻辑图")),
        ("table", ("表格", "真值表", "table")),
        ("chapter_summary", ("目录", "小结", "总结")),
        ("reference", ("参考文献", "附录", "索引")),
        ("concept", ("概念", "原理", "定义")),
    )
    for content_type, markers in rules:
        if any(marker in probe for marker in markers):
            return content_type
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        return "unknown"
    return "mixed" if len(text.strip()) >= 120 else "unknown"


def infer_chapter(path: Path, title: str, text: str = "") -> str:
    for value in (path.stem, title, text[:500]):
        match = CHAPTER_RE.search(value)
        if match:
            return match.group(0)
    return "UNKNOWN"


def extract_title(path: Path, text: str) -> str:
    match = HEADING_RE.search(text)
    if match:
        return " ".join(match.group(1).split())
    return path.stem.strip() or "UNKNOWN"


def detect_language(text: str) -> str:
    if re.search(r"[\u3400-\u9fff]", text):
        return "zh-CN"
    if re.search(r"[A-Za-z]", text):
        return "en"
    return "unknown"


def read_utf8(path: Path, max_bytes: int) -> tuple[str, str, list[str]]:
    if path.stat().st_size == 0:
        return "", "empty", ["empty_file"]
    if path.stat().st_size > max_bytes:
        return "", "too_large", ["file_exceeds_parse_limit"]
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeError:
        return "", "decode_error", ["utf8_decode_failed"]
    except OSError:
        return "", "read_error", ["file_read_failed"]
    warnings: list[str] = []
    if any(marker in text for marker in MOJIBAKE_MARKERS):
        warnings.append("possible_mojibake")
    if len(text.strip()) < 80:
        warnings.append("very_short_text")
    return text, "parsed", warnings


def markdown_image_references(
    *,
    course_id: str,
    document_path: Path,
    root: Path,
    document_id: str,
    text: str,
) -> list[MarkdownImageReference]:
    lines = text.splitlines()
    references: list[MarkdownImageReference] = []
    section = "UNKNOWN"
    for line_index, line in enumerate(lines):
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading:
            section = heading.group(1).strip()
        for match in MARKDOWN_IMAGE_RE.finditer(line):
            raw_target = match.group(2).strip().strip("<>").split("#", 1)[0]
            target = (document_path.parent / raw_target).resolve()
            exists = False
            relative = PurePosixPath(raw_target.replace("\\", "/")).as_posix()
            try:
                relative = target.relative_to(root.resolve()).as_posix()
                exists = target.is_file()
            except ValueError:
                exists = False
            nearby_lines = [
                item.strip()
                for item in lines[max(0, line_index - 2) : line_index + 3]
                if item.strip() and not MARKDOWN_IMAGE_RE.search(item)
            ]
            references.append(
                MarkdownImageReference(
                    document_id=document_id,
                    document_relative_path=posix_relative(document_path, root),
                    image_relative_path=relative,
                    alt_text=" ".join(match.group(1).split()),
                    nearby_text=" ".join(nearby_lines)[:500],
                    section=section,
                    line_number=line_index + 1,
                    exists=exists,
                )
            )
    return references


def read_image_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with path.open("rb") as handle:
            header = handle.read(32)
            if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
                return struct.unpack(">II", header[16:24])
            if header[:3] == b"GIF" and len(header) >= 10:
                return struct.unpack("<HH", header[6:10])
            if header.startswith(b"BM") and len(header) >= 26:
                return struct.unpack("<II", header[18:26])
            if header.startswith(b"\xff\xd8"):
                handle.seek(2)
                while True:
                    marker_start = handle.read(1)
                    if not marker_start:
                        break
                    if marker_start != b"\xff":
                        continue
                    marker = handle.read(1)
                    while marker == b"\xff":
                        marker = handle.read(1)
                    if marker in {bytes([item]) for item in range(0xC0, 0xC4)} | {
                        bytes([item]) for item in range(0xC5, 0xC8)
                    } | {bytes([item]) for item in range(0xC9, 0xCC)} | {
                        bytes([item]) for item in range(0xCD, 0xD0)
                    }:
                        segment = handle.read(7)
                        if len(segment) == 7:
                            height, width = struct.unpack(">HH", segment[3:7])
                            return width, height
                        break
                    size_data = handle.read(2)
                    if len(size_data) != 2:
                        break
                    size = struct.unpack(">H", size_data)[0]
                    handle.seek(max(0, size - 2), 1)
    except (OSError, ValueError, struct.error):
        return None, None
    return None, None


class KnowledgeAuditScanner:
    """Read-only scanner for original course libraries."""

    def __init__(self, roots: dict[str, Path], *, max_parse_bytes: int) -> None:
        invalid = set(roots) - SUPPORTED_COURSES
        if invalid:
            raise ValueError(f"不支持的课程编号: {sorted(invalid)}")
        self.roots = roots
        self.max_parse_bytes = max_parse_bytes

    def scan(
        self,
        course_ids: Iterable[str] | None = None,
        *,
        previous_manifest: Iterable[dict[str, Any]] | None = None,
    ) -> AuditResult:
        selected = [item.upper() for item in (course_ids or self.roots)]
        result = AuditResult()
        references: list[MarkdownImageReference] = []
        path_to_entry: dict[tuple[str, str], ManifestEntry] = {}
        checksum_to_paths: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
        names: defaultdict[tuple[str, str], list[str]] = defaultdict(list)

        for course_id in selected:
            root = self.roots[course_id]
            if not root.is_dir():
                result.issues.append(
                    QualityIssue(
                        "blocker",
                        course_id,
                        root.name,
                        "missing_course_root",
                        "课程根目录不存在",
                        True,
                        "配置正确的只读课程目录",
                    )
                )
                result.courses.append(
                    CourseAuditSummary(
                        course_id,
                        COURSE_NAMES[course_id],
                        root.name,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        {},
                        (),
                    )
                )
                continue

            course_entries: list[ManifestEntry] = []
            extension_counts: Counter[str] = Counter()
            directory_counts: Counter[str] = Counter()
            for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
                if not path.is_file() or path.is_symlink():
                    continue
                relative = posix_relative(path, root)
                extension = path.suffix.lower()
                extension_counts[extension or "[none]"] += 1
                directory_counts[relative.split("/", 1)[0]] += 1
                entry, file_references, file_issues = self._scan_file(
                    course_id, root, path, relative
                )
                course_entries.append(entry)
                references.extend(file_references)
                result.issues.extend(file_issues)
                path_to_entry[(course_id, relative.casefold())] = entry
                checksum_to_paths[entry.checksum].append((course_id, relative))
                names[(course_id, path.name.casefold())].append(relative)

            result.manifest.extend(course_entries)
            text_count = sum(
                item.source_type in {"markdown", "text"} for item in course_entries
            )
            image_count = sum(item.source_type == "image" for item in course_entries)
            result.courses.append(
                CourseAuditSummary(
                    course_id=course_id,
                    course_name=COURSE_NAMES[course_id],
                    root_path=root.name,
                    file_count=len(course_entries),
                    text_count=text_count,
                    image_count=image_count,
                    other_count=len(course_entries) - text_count - image_count,
                    total_bytes=sum(item.file_size for item in course_entries),
                    directly_indexable_count=sum(
                        item.index_status == "direct" for item in course_entries
                    ),
                    needs_cleaning_count=sum(
                        item.index_status in {"clean_before_index", "review"}
                        for item in course_entries
                    ),
                    unavailable_count=sum(
                        item.index_status == "do_not_index" for item in course_entries
                    ),
                    extension_counts=dict(sorted(extension_counts.items())),
                    top_directories=tuple(
                        item for item, _ in directory_counts.most_common(10)
                    ),
                )
            )

        result.image_references = references
        self._apply_image_relationships(result, path_to_entry)
        self._add_duplicate_issues(result, checksum_to_paths, names)
        self._add_near_duplicate_issues(result)
        self._append_missing_previous(result, previous_manifest)
        result.manifest.sort(key=lambda item: (item.course_id, item.relative_path))
        result.images.sort(key=lambda item: (item.course_id, item.source_path))
        result.issues.sort(
            key=lambda item: (
                {"blocker": 0, "high": 1, "medium": 2, "low": 3}.get(item.severity, 4),
                item.course_id,
                item.file_path,
                item.issue_type,
            )
        )
        return result

    def _scan_file(
        self, course_id: str, root: Path, path: Path, relative: str
    ) -> tuple[ManifestEntry, list[MarkdownImageReference], list[QualityIssue]]:
        stat = path.stat()
        extension = path.suffix.lower()
        digest = checksum_file(path)
        document_id = stable_id("DOC", course_id, relative.casefold())
        warnings: list[str] = []
        issues: list[QualityIssue] = []
        text = ""
        title = path.stem or "UNKNOWN"
        language = "unknown"
        references: list[MarkdownImageReference] = []

        if extension in TEXT_EXTENSIONS:
            text, parse_status, warnings = read_utf8(path, self.max_parse_bytes)
            if parse_status == "parsed":
                title = extract_title(path, text)
                language = detect_language(text)
                if extension == ".md":
                    references = markdown_image_references(
                        course_id=course_id,
                        document_path=path,
                        root=root,
                        document_id=document_id,
                        text=text,
                    )
            source_type = "markdown" if extension == ".md" else "text"
        elif extension in IMAGE_EXTENSIONS:
            parse_status = "metadata_only"
            source_type = "image"
        elif extension in DOCUMENT_EXTENSIONS:
            parse_status = "unsupported"
            source_type = "pdf" if extension == ".pdf" else "document"
            warnings.append("binary_document_not_parsed")
        elif extension in ARCHIVE_EXTENSIONS:
            parse_status = "unsupported"
            source_type = "archive"
            warnings.append("archive_not_parsed")
        else:
            parse_status = "unsupported"
            source_type = "other"
            warnings.append("unsupported_file_type")

        if not HEADING_RE.search(text) and source_type == "markdown":
            warnings.append("missing_markdown_heading")
        if any(marker in path.name.casefold() for marker in TEMPORARY_MARKERS):
            warnings.append("possible_temporary_or_draft")
        path_and_title = f"{relative} {title}"
        if any(
            other_id != course_id and other_name in path_and_title
            for other_id, other_name in COURSE_NAMES.items()
        ):
            warnings.append("possible_cross_course_placement")

        quality_status, index_status = self._quality_and_index_status(
            source_type, parse_status, warnings
        )
        for warning in warnings:
            issues.append(self._warning_issue(course_id, relative, warning))

        return (
            ManifestEntry(
                document_id=document_id,
                course_id=course_id,
                source_path=f"{root.name}/{relative}",
                relative_path=relative,
                file_name=path.name,
                file_type=extension.lstrip(".") or "unknown",
                mime_type=mimetypes.guess_type(path.name)[0]
                or "application/octet-stream",
                file_size=stat.st_size,
                checksum=digest,
                title=title,
                inferred_chapter=infer_chapter(path, title, text),
                content_type=infer_content_type(path, title, text),
                language=language,
                source_type=source_type,
                image_count=len(references),
                referenced_images=tuple(
                    dict.fromkeys(item.image_relative_path for item in references)
                ),
                referring_documents=(),
                parse_status=parse_status,
                quality_status=quality_status,
                index_status=index_status,
                warnings=tuple(dict.fromkeys(warnings)),
                modified_time=datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
            ),
            references,
            issues,
        )

    @staticmethod
    def _quality_and_index_status(
        source_type: str, parse_status: str, warnings: list[str]
    ) -> tuple[str, str]:
        if source_type == "image":
            return "review", "attachment_only"
        if parse_status != "parsed":
            return "unavailable", "do_not_index"
        if "possible_mojibake" in warnings or "utf8_decode_failed" in warnings:
            return "low", "review"
        if warnings:
            return "medium", "clean_before_index"
        return "high", "direct"

    @staticmethod
    def _warning_issue(course_id: str, relative: str, warning: str) -> QualityIssue:
        mapping: dict[str, tuple[str, str, bool, str]] = {
            "empty_file": ("high", "空文件", True, "人工确认后补充或排除"),
            "utf8_decode_failed": (
                "high",
                "UTF-8 解码失败",
                True,
                "确认编码并在索引层转换",
            ),
            "possible_mojibake": (
                "high",
                "疑似乱码",
                True,
                "人工核对原文并添加清洗规则",
            ),
            "very_short_text": (
                "medium",
                "文本过短",
                True,
                "检查是否为碎片、目录或占位文件",
            ),
            "missing_markdown_heading": (
                "medium",
                "Markdown 缺少标题",
                False,
                "在索引元数据覆盖层补充标题",
            ),
            "binary_document_not_parsed": (
                "medium",
                "PDF/DOCX 首版仅登记元数据",
                True,
                "优先使用已有提取文本，后续增加可替换解析器",
            ),
            "archive_not_parsed": (
                "low",
                "压缩包未展开",
                False,
                "确认内容已存在于当前只读目录后排除压缩包",
            ),
            "possible_temporary_or_draft": (
                "medium",
                "疑似临时、测试或草稿文件",
                True,
                "进入人工复核队列",
            ),
            "possible_cross_course_placement": (
                "high",
                "文件名或标题疑似属于其他课程",
                True,
                "人工核对课程归属；原文件保持原位",
            ),
        }
        severity, description, affects_index, suggestion = mapping.get(
            warning,
            ("low", warning, False, "人工复核"),
        )
        return QualityIssue(
            severity,
            course_id,
            relative,
            warning,
            description,
            affects_index,
            suggestion,
        )

    def _apply_image_relationships(
        self,
        result: AuditResult,
        path_to_entry: dict[tuple[str, str], ManifestEntry],
    ) -> None:
        refs_by_image: defaultdict[tuple[str, str], list[MarkdownImageReference]] = (
            defaultdict(list)
        )
        for reference in result.image_references:
            key = (
                self._course_for_document(result, reference.document_id),
                reference.image_relative_path.casefold(),
            )
            refs_by_image[key].append(reference)
            if not reference.exists:
                result.issues.append(
                    QualityIssue(
                        "high",
                        key[0],
                        reference.document_relative_path,
                        "broken_image_link",
                        f"图片链接失效: {reference.image_relative_path}",
                        True,
                        "核对原图片路径或在元数据层标记缺失",
                    )
                )

        updated_manifest: list[ManifestEntry] = []
        for entry in result.manifest:
            if entry.source_type != "image":
                updated_manifest.append(entry)
                continue
            refs = refs_by_image.get(
                (entry.course_id, entry.relative_path.casefold()), []
            )
            warnings = list(entry.warnings)
            if not refs:
                warnings.append("orphan_image")
                result.issues.append(
                    QualityIssue(
                        "medium",
                        entry.course_id,
                        entry.relative_path,
                        "orphan_image",
                        "图片未被任何 Markdown 文档引用",
                        True,
                        "保留原图并进入人工关联队列",
                    )
                )
            width, height = read_image_dimensions(
                self.roots[entry.course_id] / PurePosixPath(entry.relative_path)
            )
            if width is None or height is None:
                warnings.append("image_dimensions_unavailable")
            referring = tuple(
                dict.fromkeys(item.document_relative_path for item in refs)
            )
            parent = refs[0] if refs else None
            caption = ""
            description_source = "unavailable"
            nearby = ""
            section = entry.inferred_chapter
            if parent:
                caption = parent.alt_text or parent.nearby_text
                nearby = parent.nearby_text
                section = parent.section
                description_source = "source_text"
            result.images.append(
                ImageEvidenceRecord(
                    image_id=stable_id(
                        "IMG", entry.course_id, entry.relative_path.casefold()
                    ),
                    course_id=entry.course_id,
                    source_path=entry.relative_path,
                    resource_uri=image_uri(entry.course_id, entry.relative_path),
                    parent_document_id=parent.document_id if parent else None,
                    parent_chunk_id=None,
                    image_type=infer_content_type(
                        Path(entry.relative_path), caption, nearby
                    ),
                    image_caption=caption,
                    description_source=description_source,
                    nearby_text=nearby,
                    page_or_section=section,
                    width=width,
                    height=height,
                    checksum=entry.checksum,
                    parse_status=("context_linked" if parent else "metadata_only"),
                    quality_status="medium" if parent else "review",
                    warnings=tuple(dict.fromkeys(warnings)),
                    referring_documents=referring,
                )
            )
            updated_manifest.append(
                replace(
                    entry,
                    referring_documents=referring,
                    warnings=tuple(dict.fromkeys(warnings)),
                )
            )
            path_to_entry[(entry.course_id, entry.relative_path.casefold())] = (
                updated_manifest[-1]
            )
        result.manifest = updated_manifest

    @staticmethod
    def _course_for_document(result: AuditResult, document_id: str) -> str:
        for entry in result.manifest:
            if entry.document_id == document_id:
                return entry.course_id
        return "UNKNOWN"

    @staticmethod
    def _add_duplicate_issues(
        result: AuditResult,
        checksum_to_paths: dict[str, list[tuple[str, str]]],
        names: dict[tuple[str, str], list[str]],
    ) -> None:
        for paths in checksum_to_paths.values():
            if len(paths) < 2:
                continue
            joined = "、".join(f"{course}:{path}" for course, path in paths[:8])
            for course_id, relative in paths:
                result.issues.append(
                    QualityIssue(
                        "medium",
                        course_id,
                        relative,
                        "exact_duplicate",
                        f"与其他文件内容完全重复: {joined}",
                        True,
                        "索引层按 checksum 去重，原文件保持不变",
                    )
                )
        for (course_id, _), named_paths in names.items():
            if len(named_paths) < 2:
                continue
            for relative in named_paths:
                result.issues.append(
                    QualityIssue(
                        "low",
                        course_id,
                        relative,
                        "same_name_conflict",
                        "同一课程内存在同名文件",
                        False,
                        "使用相对路径和稳定 document_id 区分",
                    )
                )

    def _add_near_duplicate_issues(self, result: AuditResult) -> None:
        signatures: list[tuple[ManifestEntry, set[str]]] = []
        for entry in result.manifest:
            if entry.source_type not in {"markdown", "text"} or not entry.active:
                continue
            path = self.roots[entry.course_id] / PurePosixPath(entry.relative_path)
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            paragraphs = {
                " ".join(paragraph.casefold().split())
                for paragraph in re.split(r"\n\s*\n", text)
                if len(" ".join(paragraph.split())) >= 80
            }
            if paragraphs:
                signatures.append((entry, paragraphs))
        for index, (left, left_parts) in enumerate(signatures):
            for right, right_parts in signatures[index + 1 :]:
                union = left_parts | right_parts
                similarity = (
                    len(left_parts & right_parts) / len(union) if union else 0.0
                )
                if similarity < 0.85:
                    continue
                for entry, other in ((left, right), (right, left)):
                    result.issues.append(
                        QualityIssue(
                            "medium",
                            entry.course_id,
                            entry.relative_path,
                            "near_duplicate_document",
                            (
                                f"与 {other.course_id}:{other.relative_path} "
                                f"段落相似度 {similarity:.1%}"
                            ),
                            True,
                            "索引层保留来源并按 chunk 内容去重",
                        )
                    )

    @staticmethod
    def _append_missing_previous(
        result: AuditResult,
        previous_manifest: Iterable[dict[str, Any]] | None,
    ) -> None:
        if previous_manifest is None:
            return
        current_ids = {entry.document_id for entry in result.manifest}
        for raw in previous_manifest:
            document_id = str(raw.get("document_id", ""))
            if not document_id or document_id in current_ids:
                continue
            payload = dict(raw)
            payload.update(
                {
                    "active": False,
                    "parse_status": "missing",
                    "quality_status": "unavailable",
                    "index_status": "do_not_index",
                    "warnings": [*payload.get("warnings", []), "source_file_missing"],
                }
            )
            try:
                result.manifest.append(
                    ManifestEntry(
                        **{
                            **payload,
                            "referenced_images": tuple(
                                payload.get("referenced_images", [])
                            ),
                            "referring_documents": tuple(
                                payload.get("referring_documents", [])
                            ),
                            "warnings": tuple(payload.get("warnings", [])),
                        }
                    )
                )
            except TypeError:
                continue
            result.issues.append(
                QualityIssue(
                    "high",
                    str(payload.get("course_id", "UNKNOWN")),
                    str(payload.get("relative_path", "UNKNOWN")),
                    "source_file_missing",
                    "上次索引存在，但本次扫描未找到原文件",
                    True,
                    "从活动索引移除并人工确认原文件状态",
                )
            )
