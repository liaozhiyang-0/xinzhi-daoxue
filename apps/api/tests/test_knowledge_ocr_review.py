from __future__ import annotations

from pathlib import Path

from app.services.knowledge_audit import KnowledgeAuditScanner
from app.services.knowledge_ocr_review import (
    build_ocr_decision_template,
    build_ocr_review_queue,
    validate_ocr_decisions,
)


def _roots(tmp_path: Path) -> dict[str, Path]:
    roots = {
        course: tmp_path / course
        for course in ("CT", "AE", "DE", "SS", "DSP", "COMM")
    }
    for root in roots.values():
        root.mkdir()
    return roots


def test_queue_contains_only_pdf_review_candidates(
    tmp_path: Path, monkeypatch: object
) -> None:
    roots = _roots(tmp_path)
    (roots["CT"] / "scan.pdf").write_bytes(b"pdf")
    (roots["CT"] / "notes.md").write_text("# Notes\ntext", encoding="utf-8")

    class FakePage:
        def extract_text(self) -> str:
            return ""

    class FakeReader:
        pages = [FakePage(), FakePage()]

    monkeypatch.setattr(
        "app.services.knowledge_audit.PdfReader", lambda _path: FakeReader()
    )
    audit = KnowledgeAuditScanner(roots, max_parse_bytes=1024 * 1024).scan(["CT"])
    queue = build_ocr_review_queue(audit)

    assert queue["schema_version"] == "ocr_review_queue.v1"
    assert queue["mode"] == "read_only_draft"
    assert queue["runtime_loaded"] is False
    assert queue["ocr_execution_performed"] is False
    assert queue["summary"]["candidate_count"] == 1
    row = queue["rows"][0]
    assert row["review_status"] == "pending_teacher_review"
    assert row["review_action"] == "select_pages_for_ocr"
    assert row["ocr_candidate_pages"] == [1, 2]
    assert row["ocr_confidence"] is None
    assert row["ocr_confidence_source"] == "not_available"

    template = build_ocr_decision_template(queue, "CT")
    assert template["decisions"][0]["decision"] == "pending"
    report = validate_ocr_decisions(queue, template)
    assert report["valid"] is True
    assert report["review_complete"] is False
    assert report["rows"][0]["review_decision"] == "pending"

    template["decisions"][0].update(
        {
            "decision": "request_ocr",
            "reviewer": "teacher-1",
            "reviewed_at": "2026-08-04T10:00:00+08:00",
        }
    )
    report = validate_ocr_decisions(queue, template)
    assert report["valid"] is True
    assert report["review_complete"] is True
    assert report["decision_counts"] == {"request_ocr": 1}
    assert report["rows"][0]["reviewer"] == "teacher-1"

    template["decisions"][0]["checksum"] = "stale"
    report = validate_ocr_decisions(queue, template)
    assert report["valid"] is False
    assert any(item.startswith("stale_checksum:") for item in report["errors"])


def test_queue_preserves_oversized_pdf_action(
    tmp_path: Path, monkeypatch: object
) -> None:
    roots = _roots(tmp_path)
    scanner = KnowledgeAuditScanner(roots, max_parse_bytes=1)
    pdf = roots["AE"] / "large.pdf"
    pdf.write_bytes(b"pdf")

    class FakeReader:
        pages = [object(), object(), object()]

    monkeypatch.setattr(
        "app.services.knowledge_audit.PdfReader", lambda _path: FakeReader()
    )
    audit = scanner.scan(["AE"])

    queue = build_ocr_review_queue(audit)
    row = queue["rows"][0]

    assert row["parse_status"] == "too_large"
    assert row["page_count"] == 3
    assert row["review_action"] == "split_or_review_parse_limit"
    assert row["priority"] == "high"
    assert row["manual_review_required"] is True
