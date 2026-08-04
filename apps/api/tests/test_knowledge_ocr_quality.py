from __future__ import annotations

from app.services.knowledge_ocr_quality import build_ocr_quality_summary


def test_ocr_quality_summary_preserves_page_evidence_without_execution() -> None:
    payload = build_ocr_quality_summary(
        {
            "rows": [
                {
                    "queue_id": "OCR-1",
                    "course_id": "CT",
                    "document_id": "DOC-1",
                    "relative_path": "pdf/chapter-1.pdf",
                    "file_name": "chapter-1.pdf",
                    "page_count": 4,
                    "parse_status": "ocr_required",
                    "quality_status": "unavailable",
                    "index_status": "do_not_index",
                    "ocr_required": True,
                    "ocr_status": "required",
                    "ocr_candidate_pages": [2, 4, 4],
                    "low_text_page_count": 0,
                    "page_coverage_ratio": 0.5,
                    "manual_review_required": True,
                    "warnings": ["empty_pages_require_ocr"],
                    "priority": "high",
                    "review_action": "select_pages_for_ocr",
                }
            ],
            "cache_status": "hit",
            "cache_backend": "memory",
        },
        "CT",
    )

    assert payload["schema_version"] == "ocr_quality_summary.v1"
    assert payload["ocr_execution_performed"] is False
    assert payload["decision_evidence"]["status"] == "decision_file_missing"
    assert payload["audit_status"] == "available"
    assert payload["summary"]["candidate_page_count"] == 2
    assert payload["summary"]["total_known_page_count"] == 4
    assert payload["rows"][0]["ocr_candidate_pages"] == [2, 4]
    assert payload["rows"][0]["review_decision"] == "pending"


def test_ocr_quality_summary_marks_empty_scope_unavailable() -> None:
    payload = build_ocr_quality_summary({"rows": []}, "AE")

    assert payload["audit_status"] == "unavailable"
    assert payload["summary"]["candidate_document_count"] == 0
    assert payload["ocr_execution_performed"] is False


def test_ocr_quality_summary_flags_decided_rows_without_evidence() -> None:
    payload = build_ocr_quality_summary(
        {
            "rows": [
                {
                    "queue_id": "OCR-1",
                    "course_id": "AE",
                    "document_id": "DOC-1",
                    "relative_path": "pdf/chapter-1.pdf",
                    "file_name": "chapter-1.pdf",
                    "page_count": 1,
                    "ocr_candidate_pages": [1],
                    "review_decision": "request_ocr",
                    "evidence_refs": [],
                }
            ],
            "decision_reports": {
                "AE": {
                    "course_id": "AE",
                    "valid": True,
                    "review_complete": True,
                    "errors": [],
                }
            },
        },
        "AE",
    )

    assert payload["decision_evidence"]["status"] == "complete_without_evidence"
    assert payload["decision_evidence"]["rows_missing_evidence_refs"] == 1
