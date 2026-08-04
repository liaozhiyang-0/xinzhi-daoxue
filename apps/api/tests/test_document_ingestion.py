from __future__ import annotations

import io
import json
import zipfile

from app.core.errors import ValidationAppError
from app.models import FileIngestionStatus
from app.services.document_ingestion import extract_document
from PIL import Image
from pypdf import PdfWriter
from pytest import raises


def _docx_bytes(*paragraphs: str) -> bytes:
    body = "".join(
        f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>"
        for paragraph in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", document)
    return output.getvalue()


def test_text_ingestion_detects_gb18030_and_creates_chunks(settings) -> None:
    result = extract_document(
        "lesson.txt",
        "text/plain",
        "这是一个中文材料。".encode("gb18030"),
        settings,
    )

    assert result.status is FileIngestionStatus.READY
    assert result.text == "这是一个中文材料。"
    assert result.metadata["encoding"] == "gb18030"
    assert result.chunks[0].content == result.text


def test_csv_and_json_are_ingested_as_text(settings) -> None:
    csv_result = extract_document("table.csv", "text/csv", b"name,value\nA,1", settings)
    json_result = extract_document(
        "record.json", "application/json", b'{"name":"A"}', settings
    )

    assert csv_result.detected_content_type == "text/csv"
    assert csv_result.text == "name,value\nA,1"
    assert json_result.detected_content_type == "application/json"
    assert json_result.text == '{"name":"A"}'


def test_docx_ingestion_extracts_paragraphs(settings) -> None:
    result = extract_document(
        "lesson.docx",
        "application/octet-stream",
        _docx_bytes("第一段", "第二段"),
        settings,
    )

    assert result.status is FileIngestionStatus.READY
    assert result.text == "第一段\n\n第二段"
    assert result.metadata["format"] == "docx"
    assert result.metadata["paragraph_count"] == 2
    quality = result.metadata["quality_report"]
    assert quality["quality_status"] == "ready"
    assert quality["chunk_count"] == 1
    assert [chunk.ordinal for chunk in result.chunks] == [0]


def test_pdf_ingestion_reports_empty_pages_for_ocr_follow_up(settings) -> None:
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    writer.write(output)

    result = extract_document(
        "scan.pdf", "application/pdf", output.getvalue(), settings
    )

    assert result.status is FileIngestionStatus.FAILED
    assert result.page_count == 1
    assert result.metadata["ocr_required"] is True
    quality = result.metadata["quality_report"]
    assert quality["quality_status"] == "failed"
    assert quality["ocr_status"] == "required"
    assert quality["ocr_confidence"] is None
    assert result.text == ""


def test_pdf_ingestion_flags_low_text_pages_for_ocr_review(
    settings, monkeypatch
) -> None:
    class FakePage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class FakeReader:
        def __init__(self, _stream) -> None:
            self.pages = [FakePage("x"), FakePage("This page has enough text.")]

    monkeypatch.setattr("app.services.document_ingestion.PdfReader", FakeReader)
    result = extract_document(
        "noisy-scan.pdf", "application/pdf", b"%PDF-fake", settings
    )

    assert result.status is FileIngestionStatus.PARTIAL
    assert result.metadata["ocr_required"] is True
    assert result.metadata["low_text_page_count"] == 1
    assert result.metadata["ocr_candidate_pages"] == [1]
    quality = result.metadata["quality_report"]
    assert quality["quality_status"] == "review"
    assert quality["manual_review_required"] is True
    assert quality["ocr_confidence"] is None
    assert "low_text_pages_require_ocr_review" in quality["warnings"]


def test_text_quality_report_detects_headings_and_questions(settings) -> None:
    result = extract_document(
        "lesson.md",
        "text/markdown",
        "# KCL\n1. 求节点电流\n结点电流代数和为零。".encode(),
        settings,
    )

    quality = result.metadata["quality_report"]
    assert quality["quality_status"] == "ready"
    assert quality["heading_count"] == 1
    assert quality["question_count"] == 1
    assert quality["ocr_confidence"] is None


def test_document_signature_is_validated_before_parsing(settings) -> None:
    with raises(ValidationAppError):
        extract_document(
            "broken.docx", "application/octet-stream", b"not-a-docx", settings
        )


def test_document_upload_exposes_ingestion_and_chunks(client) -> None:
    response = client.post(
        "/api/v1/files",
        files={"upload": ("lesson.txt", "第一段\n\n第二段".encode(), "text/plain")},
    )

    assert response.status_code == 201, response.text
    uploaded = response.json()
    assert uploaded["ingestion_status"] == "ready"
    assert uploaded["extracted_text"] == "第一段\n\n第二段"
    assert uploaded["extraction_metadata"]["format"] == "txt"

    chunks = client.get(f"/api/v1/files/{uploaded['id']}/chunks")
    assert chunks.status_code == 200
    assert chunks.json()[0]["content"] == uploaded["extracted_text"]


def test_task_hydrates_uploaded_text_before_non_blocking_creation(client, api) -> None:
    uploaded = client.post(
        "/api/v1/files",
        files={"upload": ("task-note.txt", b"task attachment text", "text/plain")},
    ).json()
    session = api.create_session()
    response = client.post(
        "/api/v1/tasks",
        json=api.task_payload(
            session["id"],
            attachments=[
                {
                    key: uploaded[key]
                    for key in (
                        "filename",
                        "content_type",
                        "size_bytes",
                        "storage_key",
                        "checksum_sha256",
                    )
                }
                | {"file_id": uploaded["id"]}
            ],
        ),
    )

    assert response.status_code == 202, response.text
    task = client.get(f"/api/v1/tasks/{response.json()['id']}")
    assert task.status_code == 200
    input_content = task.json()["input_content"]
    assert "task attachment text" in input_content["canonical_input"]["uploaded_text"]
    assert input_content["attachments"][0]["ingestion_status"] == "ready"


def test_image_attachment_flows_through_task_creation(client, api) -> None:
    output = io.BytesIO()
    Image.new("RGB", (8, 6), "white").save(output, format="PNG")
    uploaded_response = client.post(
        "/api/v1/files",
        files={"upload": ("diagram.png", output.getvalue(), "image/png")},
    )
    assert uploaded_response.status_code == 201, uploaded_response.text
    uploaded = uploaded_response.json()
    session = api.create_session()
    response = client.post(
        "/api/v1/tasks",
        json=api.task_payload(
            session["id"],
            attachments=[
                {
                    key: uploaded[key]
                    for key in (
                        "filename",
                        "content_type",
                        "size_bytes",
                        "storage_key",
                        "checksum_sha256",
                    )
                }
                | {"file_id": uploaded["id"]}
            ],
        ),
    )

    assert response.status_code == 202, response.text
    task = api.wait_for_task(response.json()["id"])
    assert task["status"] in {"completed", "failed"}
    attachment = task["input_content"]["attachments"][0]
    assert attachment["file_id"] == uploaded["id"]
    assert attachment["content_type"] == "image/png"
    assert "path" not in attachment


def test_course_material_requires_identity_and_supports_publish_versions(
    client,
    app,
) -> None:
    missing = client.post(
        "/api/v1/files",
        data={"purpose": "course_material"},
        files={"upload": ("lesson.txt", b"KCL lesson", "text/plain")},
    )
    assert missing.status_code == 422

    uploaded = client.post(
        "/api/v1/files",
        data={
            "purpose": "course_material",
            "course_id": "CT",
            "material_key": "kcl-intro",
            "material_version": "1.0.0",
        },
        files={"upload": ("lesson.txt", b"KCL lesson", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    file_data = uploaded.json()
    assert file_data["knowledge_status"] == "draft"
    assert file_data["knowledge_index_status"] == "not_indexed"

    materials = client.get("/api/v1/knowledge/materials", params={"course_id": "CT"})
    assert materials.status_code == 200
    assert materials.json()[0]["material_version"] == "1.0.0"
    assert materials.json()[0]["chunk_count"] == 1
    assert materials.json()[0]["quality_status"] == "ready"
    assert materials.json()[0]["ocr_required"] is False
    assert materials.json()[0]["manual_review_required"] is False
    assert materials.json()[0]["ocr_candidate_pages"] == []
    assert materials.json()[0]["material_review_status"] == "not_required"

    material_chunks = client.get(
        f"/api/v1/knowledge/materials/{file_data['id']}/chunks"
    )
    assert material_chunks.status_code == 200, material_chunks.text
    assert material_chunks.json()[0]["content"] == "KCL lesson"

    published = client.post(
        f"/api/v1/knowledge/materials/{file_data['id']}/publish"
    )
    assert published.status_code == 200, published.text
    assert published.json()["knowledge_status"] == "published"
    assert published.json()["knowledge_index_status"] == "not_indexed"

    reviewed = client.post(
        f"/api/v1/knowledge/materials/{file_data['id']}/review",
        json={"status": "approved", "note": "  reviewed locally  "},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["material_review_status"] == "approved"
    assert reviewed.json()["material_review_note"] == "reviewed locally"
    assert reviewed.json()["material_reviewed_at"]

    manifest = client.post(
        "/api/v1/knowledge/materials/manifest", params={"course_id": "CT"}
    )
    assert manifest.status_code == 200, manifest.text
    assert manifest.json()["material_count"] == 1
    assert manifest.json()["chunk_count"] == 1
    manifest_path = (
        app.state.settings.knowledge_index_path
        / manifest.json()["manifest_filename"]
    )
    manifest_row = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_row["document_id"] == file_data["id"]

    state_path = (
        app.state.settings.knowledge_index_path / "rag_index_state.json"
    )
    state_path.write_text(
        json.dumps(
            {"material_checksums": {file_data["id"]: file_data["checksum_sha256"]}}
        ),
        encoding="utf-8",
    )
    indexed = client.get("/api/v1/knowledge/materials", params={"course_id": "CT"})
    assert indexed.json()[0]["knowledge_index_status"] == "indexed"

    withdrawn = client.post(
        f"/api/v1/knowledge/materials/{file_data['id']}/withdraw"
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["knowledge_status"] == "withdrawn"
    assert withdrawn.json()["knowledge_index_status"] == "stale"


def test_quality_flagged_course_material_enters_review_queue(
    client, monkeypatch
) -> None:
    class FakePage:
        def extract_text(self) -> str:
            return "x"

    class FakeReader:
        def __init__(self, _stream) -> None:
            self.pages = [FakePage()]

    monkeypatch.setattr("app.services.document_ingestion.PdfReader", FakeReader)
    uploaded = client.post(
        "/api/v1/files",
        data={
            "purpose": "course_material",
            "course_id": "CT",
            "material_key": "scan-review",
            "material_version": "1.0.0",
        },
        files={"upload": ("scan.pdf", b"%PDF-fake", "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    file_id = uploaded.json()["id"]

    materials = client.get("/api/v1/knowledge/materials", params={"course_id": "CT"})
    material = next(item for item in materials.json() if item["file_id"] == file_id)
    assert material["material_review_status"] == "pending"
    assert material["manual_review_required"] is True

    rejected = client.post(
        f"/api/v1/knowledge/materials/{file_id}/review",
        json={"status": "rejected", "note": "OCR required"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["material_review_status"] == "rejected"

    approved = client.post(
        f"/api/v1/knowledge/materials/{file_id}/review",
        json={"status": "approved"},
    )
    assert approved.status_code == 409
