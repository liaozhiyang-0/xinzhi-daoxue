from __future__ import annotations

import asyncio
import codecs
import io
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ValidationAppError
from app.models import (
    CourseMaterialReviewStatus,
    DocumentChunkModel,
    FileIngestionStatus,
    FileModel,
)
from app.multimodal.quality import PDF_PAGE_TEXT_REVIEW_THRESHOLD

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".pdf",
    ".doc",
    ".docx",
}
HEADING_RE = re.compile(
    r"^\s*(?:#{1,6}\s+.+|第[一二三四五六七八九十百千万0-9]+[章节篇]|"
    r"(?:例题|习题|练习|问题)\s*[0-9一二三四五六七八九十百千万]*)\s*$"
)
QUESTION_RE = re.compile(
    r"^\s*(?:(?:[0-9]{1,3}|[一二三四五六七八九十百千万]+)[.、)]|"
    r"[（(][0-9]{1,3}[）)]|(?:例题|习题|练习|问题)\s*)"
)


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    content: str
    ordinal: int
    page_number: int | None
    section: str
    char_start: int
    char_end: int
    source_ref: str


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    detected_content_type: str
    text: str
    page_count: int
    metadata: dict[str, object]
    chunks: list[ChunkDraft]
    status: FileIngestionStatus


def _normalise_text(value: str) -> str:
    value = value.replace("\x00", "")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _quality_report(
    text: str,
    chunks: list[ChunkDraft],
    *,
    page_char_counts: Iterable[int] = (),
    ocr_required: bool = False,
    low_text_page_count: int = 0,
    ocr_candidate_pages: Iterable[int] = (),
    warnings: Iterable[str] = (),
) -> dict[str, object]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    headings = [line[:160] for line in lines if HEADING_RE.match(line)]
    page_counts = tuple(page_char_counts)
    nonempty_pages = sum(count > 0 for count in page_counts)
    quality_status = "ready"
    if not text:
        quality_status = "failed" if ocr_required else "review"
    elif ocr_required or not chunks:
        quality_status = "review"
    return {
        "version": "1",
        "quality_status": quality_status,
        "text_char_count": len(text),
        "non_whitespace_char_count": len(re.sub(r"\s+", "", text)),
        "chunk_count": len(chunks),
        "heading_count": len(headings),
        "question_count": sum(bool(QUESTION_RE.match(line)) for line in lines),
        "heading_candidates": headings[:20],
        "page_count": len(page_counts),
        "nonempty_page_count": nonempty_pages,
        "page_coverage_ratio": (
            round(nonempty_pages / len(page_counts), 4) if page_counts else None
        ),
        "low_text_page_count": low_text_page_count,
        "ocr_candidate_pages": list(ocr_candidate_pages),
        "ocr_required": ocr_required,
        "ocr_status": "required" if ocr_required else "not_required",
        "ocr_confidence": None,
        "ocr_confidence_source": "not_available",
        "manual_review_required": ocr_required or not chunks,
        "warnings": list(warnings),
    }


def _decode_text(data: bytes) -> tuple[str, str]:
    candidates: list[tuple[str, bytes]] = []
    if data.startswith(codecs.BOM_UTF8):
        candidates.append(("utf-8-sig", data))
    elif data.startswith(codecs.BOM_UTF16_LE) or data.startswith(codecs.BOM_UTF16_BE):
        candidates.append(("utf-16", data))
    candidates.extend(
        [("utf-8", data), ("gb18030", data), ("big5", data), ("utf-16", data)]
    )
    for encoding, payload in candidates:
        try:
            text = payload.decode(encoding)
        except UnicodeDecodeError:
            continue
        if "\x00" not in text or encoding.startswith("utf-16"):
            return _normalise_text(text), encoding
    raise ValidationAppError("文本文件编码无法识别")


def _chunk_blocks(
    blocks: list[tuple[str, int | None, str]], settings: Settings
) -> tuple[str, list[ChunkDraft]]:
    joined = "\n\n".join(text for text, _, _ in blocks if text.strip())
    joined = _normalise_text(joined)[: settings.document_max_extracted_chars]
    if not joined:
        return "", []
    chunks: list[ChunkDraft] = []
    start = 0
    ordinal = 0
    while start < len(joined):
        end = min(len(joined), start + settings.document_chunk_size_chars)
        content = joined[start:end].strip()
        if content:
            page_number: int | None = None
            consumed = 0
            for block_text, block_page, _ in blocks:
                block_end = consumed + len(block_text)
                if consumed <= start < block_end or consumed < end <= block_end:
                    page_number = block_page
                    break
                consumed = block_end + 2
            chunks.append(
                ChunkDraft(
                    content=content,
                    ordinal=ordinal,
                    page_number=page_number,
                    section="",
                    char_start=start,
                    char_end=min(end, len(joined)),
                    source_ref=(
                        f"file://chunk/{ordinal}"
                        + (f"#page={page_number}" if page_number else "")
                    ),
                )
            )
            ordinal += 1
        if end >= len(joined):
            break
        start = max(start + 1, end - settings.document_chunk_overlap_chars)
    return joined, chunks


def _extract_docx(data: bytes, settings: Settings) -> ExtractionResult:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml_data = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise ValidationAppError("DOCX 文件结构无效") from exc
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        raise ValidationAppError("DOCX 文档内容无法解析") from exc
    blocks: list[tuple[str, int | None, str]] = []
    for paragraph in root.iter(f"{W_NS}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{W_NS}t"))
        text = _normalise_text(text)
        if text:
            blocks.append((text, None, ""))
    text, chunks = _chunk_blocks(blocks, settings)
    status = FileIngestionStatus.READY if text else FileIngestionStatus.PARTIAL
    return ExtractionResult(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        text,
        0,
        {
            "format": "docx",
            "paragraph_count": len(blocks),
            "quality_report": _quality_report(text, chunks),
        },
        chunks,
        status,
    )


def _extract_doc(data: bytes, settings: Settings, converter: str) -> ExtractionResult:
    executable = shutil.which(converter)
    if executable is None:
        raise ValidationAppError("DOC 文件需要服务器安装 LibreOffice 才能解析")
    with tempfile.TemporaryDirectory(prefix="xzd-doc-") as directory:
        source = Path(directory) / "source.doc"
        source.write_bytes(data)
        completed = subprocess.run(
            [
                executable,
                "--headless",
                "--convert-to",
                "docx",
                "--outdir",
                directory,
                str(source),
            ],
            capture_output=True,
            text=True,
            timeout=settings.document_extraction_timeout_seconds,
            check=False,
        )
        converted = Path(directory) / "source.docx"
        if completed.returncode != 0 or not converted.is_file():
            raise ValidationAppError("DOC 文件转换失败，请检查文件是否损坏")
        result = _extract_docx(converted.read_bytes(), settings)
        return ExtractionResult(
            "application/msword",
            result.text,
            result.page_count,
            {**result.metadata, "format": "doc", "converter": converter},
            result.chunks,
            result.status,
        )


def _extract_pdf(data: bytes, settings: Settings) -> ExtractionResult:
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # pypdf raises several parser-specific exceptions
        raise ValidationAppError("PDF 文件结构无效") from exc
    if len(reader.pages) > settings.document_max_pages:
        raise ValidationAppError(
            f"PDF 页数超过限制（最多 {settings.document_max_pages} 页）"
        )
    blocks: list[tuple[str, int | None, str]] = []
    empty_pages = 0
    page_char_counts: list[int] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            page_text = _normalise_text(page.extract_text() or "")
        except Exception:
            page_text = ""
        if not page_text:
            empty_pages += 1
        page_char_counts.append(len(page_text))
        blocks.append((page_text, index, f"page={index}"))
    low_text_pages = [
        index
        for index, count in enumerate(page_char_counts, start=1)
        if 0 < count < PDF_PAGE_TEXT_REVIEW_THRESHOLD
    ]
    ocr_candidate_pages = sorted(
        {
            *low_text_pages,
            *[
                index
                for index, count in enumerate(page_char_counts, start=1)
                if count == 0
            ],
        }
    )
    ocr_required = bool(ocr_candidate_pages)
    text, chunks = _chunk_blocks(blocks, settings)
    status = FileIngestionStatus.READY
    if ocr_required:
        status = FileIngestionStatus.PARTIAL if text else FileIngestionStatus.FAILED
    return ExtractionResult(
        "application/pdf",
        text,
        len(reader.pages),
        {
            "format": "pdf",
            "empty_page_count": empty_pages,
            "low_text_page_count": len(low_text_pages),
            "ocr_candidate_pages": ocr_candidate_pages,
            "ocr_required": ocr_required,
            "quality_report": _quality_report(
                text,
                chunks,
                page_char_counts=page_char_counts,
                ocr_required=ocr_required,
                low_text_page_count=len(low_text_pages),
                ocr_candidate_pages=ocr_candidate_pages,
                warnings=tuple(
                    item
                    for item in (
                        "empty_pages_require_ocr" if empty_pages else "",
                        "low_text_pages_require_ocr_review"
                        if low_text_pages
                        else "",
                    )
                    if item
                ),
            ),
        },
        chunks,
        status,
    )


def extract_document(
    filename: str, content_type: str, data: bytes, settings: Settings
) -> ExtractionResult:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
        return ExtractionResult(
            content_type,
            "",
            0,
            {"format": "binary"},
            [],
            FileIngestionStatus.READY,
        )
    if extension == ".pdf" and not data.startswith(b"%PDF"):
        raise ValidationAppError("PDF 文件签名无效")
    if extension == ".docx" and not data.startswith(b"PK"):
        raise ValidationAppError("DOCX 文件签名无效")
    if extension == ".doc" and not data.startswith(b"\xd0\xcf\x11\xe0"):
        raise ValidationAppError("DOC 文件签名无效")
    if extension in {".txt", ".md", ".csv", ".json"}:
        text, encoding = _decode_text(data)
        text, chunks = _chunk_blocks([(text, None, "")], settings)
        detected_content_type = {
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".csv": "text/csv",
            ".json": "application/json",
        }[extension]
        return ExtractionResult(
            detected_content_type,
            text,
            0,
            {
                "format": extension.removeprefix("."),
                "encoding": encoding,
                "quality_report": _quality_report(text, chunks),
            },
            chunks,
            FileIngestionStatus.READY if text else FileIngestionStatus.PARTIAL,
        )
    if extension == ".pdf":
        return _extract_pdf(data, settings)
    if extension == ".docx":
        return _extract_docx(data, settings)
    return _extract_doc(data, settings, settings.document_converter_command)


class DocumentIngestionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def ingest(
        self, model: FileModel, data: bytes, db: AsyncSession
    ) -> None:
        model.ingestion_status = FileIngestionStatus.PROCESSING
        model.extraction_started_at = datetime.now(UTC)
        await db.flush()
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    extract_document,
                    model.filename,
                    model.content_type,
                    data,
                    self.settings,
                ),
                timeout=self.settings.document_extraction_timeout_seconds,
            )
            model.detected_content_type = result.detected_content_type
            model.ingestion_status = result.status
            model.page_count = result.page_count
            model.extracted_text = result.text
            model.extraction_metadata = result.metadata
            if model.purpose == "course_material":
                quality_report = result.metadata.get("quality_report", {})
                requires_review = (
                    result.status != FileIngestionStatus.READY
                    or not isinstance(quality_report, dict)
                    or bool(quality_report.get("manual_review_required"))
                )
                model.material_review_status = (
                    CourseMaterialReviewStatus.PENDING
                    if requires_review
                    else CourseMaterialReviewStatus.NOT_REQUIRED
                )
            model.extraction_error = (
                "扫描版 PDF 存在未提取页面，已保留可读文本；OCR 尚未配置"
                if result.metadata.get("ocr_required")
                else None
            )
            model.extraction_completed_at = datetime.now(UTC)
            db.add_all(
                DocumentChunkModel(
                    file_id=model.id,
                    ordinal=item.ordinal,
                    page_number=item.page_number,
                    section=item.section,
                    content=item.content,
                    char_start=item.char_start,
                    char_end=item.char_end,
                    source_ref=item.source_ref,
                )
                for item in result.chunks
            )
        except Exception as exc:
            model.ingestion_status = FileIngestionStatus.FAILED
            if model.purpose == "course_material":
                model.material_review_status = CourseMaterialReviewStatus.PENDING
            model.extraction_error = str(exc)
            model.extraction_metadata = {"format": Path(model.filename).suffix.lower()}
            model.extraction_completed_at = datetime.now(UTC)
