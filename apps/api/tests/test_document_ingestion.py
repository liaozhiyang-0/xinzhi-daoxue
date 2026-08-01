from __future__ import annotations

import io
import zipfile

from app.core.errors import ValidationAppError
from app.models import FileIngestionStatus
from app.services.document_ingestion import extract_document
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
    assert result.metadata == {"format": "docx", "paragraph_count": 2}
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
    assert result.text == ""


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
