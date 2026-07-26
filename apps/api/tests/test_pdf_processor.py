from pathlib import Path

from app.multimodal import PDFProcessor
from pypdf import PdfWriter


def test_pdf_processor_limits_pages_and_marks_scanned_pages(tmp_path: Path) -> None:
    path = tmp_path / "two-pages.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    with path.open("wb") as stream:
        writer.write(stream)

    result = PDFProcessor(max_size_mb=1, max_pages=1).extract(path)

    assert result.page_count == 2
    assert result.truncated is True
    assert result.pages[0].needs_visual_processing is True
    assert result.pages[0].page_number == 1
