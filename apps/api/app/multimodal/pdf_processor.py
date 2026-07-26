from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class PDFPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1)
    text: str = ""
    needs_visual_processing: bool = False


class PDFExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_file: str
    page_count: int = Field(ge=0)
    pages: list[PDFPage] = Field(default_factory=list)
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


class PDFProcessor:
    """CPU text-layer extraction; visual rendering is explicitly selective."""

    def __init__(self, *, max_size_mb: int = 20, max_pages: int = 40) -> None:
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_pages = max_pages

    def extract(self, path: Path) -> PDFExtraction:
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.stat().st_size > self.max_size_bytes:
            raise ValueError("PDF 文件大小超过限制")
        try:
            from pypdf import PdfReader  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("PDF 文本提取需要安装 pypdf") from exc
        reader = PdfReader(str(path))
        total = len(reader.pages)
        limit = min(total, self.max_pages)
        pages: list[PDFPage] = []
        for index in range(limit):
            text = (reader.pages[index].extract_text() or "").strip()
            pages.append(
                PDFPage(
                    page_number=index + 1,
                    text=text,
                    needs_visual_processing=len(text) < 20,
                )
            )
        warnings = []
        if total > self.max_pages:
            warnings.append(
                f"PDF 共 {total} 页，仅处理前 {self.max_pages} 页；"
                "未默认逐页调用视觉模型"
            )
        return PDFExtraction(
            source_file=path.name,
            page_count=total,
            pages=pages,
            truncated=total > self.max_pages,
            warnings=warnings,
        )
