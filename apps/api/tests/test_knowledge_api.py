from pathlib import Path

from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from pypdf import PdfWriter


def make_client(tmp_path: Path) -> TestClient:
    ct = tmp_path / "ct"
    ae = tmp_path / "ae"
    de = tmp_path / "de"
    ss = tmp_path / "ss"
    dsp = tmp_path / "dsp"
    comm = tmp_path / "comm"
    for path in (ct, ae, de, ss, dsp, comm):
        path.mkdir()
    (ct / "chapter.md").write_text(
        "## 节点电压法\n节点电压法以独立节点电压作为未知量列写方程。"
        "\n例如 I=10/5=2A。",
        encoding="utf-8",
    )
    chapter = ct / "chapter.md"
    chapter.write_text(
        chapter.read_text(encoding="utf-8")
        + "\nNodal voltage method writes circuit equations.",
        encoding="utf-8",
    )
    (ct / "diagram.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 24)
    settings = Settings(
        app_env="test",
        test_database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        redis_url="redis://127.0.0.1:1/0",
        minio_endpoint="127.0.0.1:1",
        local_storage_path=tmp_path / "storage",
        knowledge_ct_path=ct,
        knowledge_ae_path=ae,
        knowledge_de_path=de,
        knowledge_ss_path=ss,
        knowledge_dsp_path=dsp,
        knowledge_comm_path=comm,
        knowledge_ocr_decisions_path=tmp_path / "ocr-decisions",
        knowledge_ocr_review_cache_path=tmp_path / "ocr-review-snapshots",
        knowledge_chunk_size_chars=300,
        knowledge_chunk_overlap_chars=20,
        rag_enabled=False,
        _env_file=None,
    )
    return TestClient(create_app(settings))


def test_knowledge_sources_and_search_api(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        sources = client.get("/api/v1/knowledge/sources")
        assert sources.status_code == 200
        assert sources.json()[0]["document_count"] == 1

        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": "节点电压法", "course_ids": ["CT"], "top_k": 3},
        )
        assert response.status_code == 200
        assert response.json()["hits"][0]["title"] == "节点电压法"


def test_ocr_review_queue_is_teacher_read_only_snapshot(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get(
            "/api/v1/knowledge/ocr-review-queue", params={"course_id": "ct"}
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["schema_version"] == "ocr_review_queue.v1"
        assert payload["mode"] == "read_only_draft"
        assert payload["ocr_execution_performed"] is False
        assert payload["summary"]["candidate_count"] == 0
        assert payload["decision_reports"] == {}
        assert payload["cache_status"] == "miss"

        cached = client.get(
            "/api/v1/knowledge/ocr-review-queue", params={"course_id": "ct"}
        )
        assert cached.status_code == 200
        assert cached.json()["cache_status"] == "hit"
        assert cached.json()["cache_backend"] == "memory"

        invalid = client.get(
            "/api/v1/knowledge/ocr-review-queue",
            params={"course_id": "unknown"},
        )
        assert invalid.status_code == 400


def test_ocr_review_decision_save_requires_evidence_and_invalidates_cache(
    tmp_path: Path,
) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with make_client(tmp_path) as client:
        with (tmp_path / "ct" / "scan.pdf").open("wb") as handle:
            writer.write(handle)
        queue_response = client.get(
            "/api/v1/knowledge/ocr-review-queue", params={"course_id": "CT"}
        )
        assert queue_response.status_code == 200
        queue = queue_response.json()
        assert queue["summary"]["candidate_count"] == 1
        row = queue["rows"][0]
        base_request = {
            "source_fingerprint": queue["source_fingerprint"],
            "reviewer": "teacher-test",
            "decisions": [
                {
                    "queue_id": row["queue_id"],
                    "checksum": row["checksum"],
                    "decision": "request_ocr",
                    "evidence_refs": [],
                    "note": "select the blank page for teacher-approved OCR",
                }
            ],
        }

        missing_evidence = client.put(
            "/api/v1/knowledge/ocr-review-decisions/CT", json=base_request
        )
        assert missing_evidence.status_code == 422
        assert "evidence_refs_required" in missing_evidence.text

        stale = {**base_request, "source_fingerprint": "0" * 64}
        stale_response = client.put(
            "/api/v1/knowledge/ocr-review-decisions/CT", json=stale
        )
        assert stale_response.status_code == 409

        base_request["decisions"][0]["evidence_refs"] = [
            "kb://CT/scan.pdf#page=1"
        ]
        saved = client.put(
            "/api/v1/knowledge/ocr-review-decisions/CT", json=base_request
        )
        assert saved.status_code == 200, saved.text
        saved_payload = saved.json()
        assert saved_payload["decision_reports"]["CT"]["valid"] is True
        assert saved_payload["decision_reports"]["CT"]["review_complete"] is True
        assert saved_payload["rows"][0]["review_decision"] == "request_ocr"
        assert saved_payload["rows"][0]["evidence_refs"] == [
            "kb://CT/scan.pdf#page=1"
        ]
        assert saved_payload["source_fingerprint"] != queue["source_fingerprint"]

        unchanged_save = {
            **base_request,
            "source_fingerprint": saved_payload["source_fingerprint"],
            "reviewer": "another-teacher",
        }
        unchanged = client.put(
            "/api/v1/knowledge/ocr-review-decisions/CT", json=unchanged_save
        )
        assert unchanged.status_code == 200, unchanged.text
        assert unchanged.json()["rows"][0]["reviewer"] == "teacher-test"

        quality = client.get(
            "/api/v1/knowledge/ocr-quality-summary", params={"course_id": "CT"}
        )
        assert quality.status_code == 200
        assert quality.json()["decision_evidence"]["status"] == (
            "complete_with_evidence"
        )
        assert (tmp_path / "ocr-decisions" / "CT.yaml").is_file()


def test_mock_task_records_local_knowledge_hits(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        session = client.post(
            "/api/v1/sessions",
            json={"user_id": "kb-user", "course_id": "CT", "title": "知识库"},
        ).json()
        task = client.post(
            "/api/v1/tasks",
            json={
                "session_id": session["id"],
                "user_id": "kb-user",
                "course_id": "CT",
                "canonical_input": {"text": "节点电压法如何列方程"},
            },
        ).json()
        for _ in range(100):
            current = client.get(f"/api/v1/tasks/{task['id']}").json()
            if current["status"] == "completed":
                break
        assert current["status"] == "completed"
        result = current["result_content"]
        assert result["metrics"]["retrieval_calls"] == 1
        assert result["citations"] == []
        assert result["structured_result"]["knowledge"]["hits"]
        assert result["structured_result"]["execution_summary"]["rag_mode"] == (
            "method_reference"
        )
        assert all(
            item["role"] == "method_reference"
            for item in result["structured_result"]["evidence_view"]
        )
        artifact = client.get(f"/api/v1/artifacts/{current['artifact_ids'][0]}").json()
        assert "knowledge_sources" not in artifact["content"]
        events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
        assert "knowledge.retrieved" in [event["event_type"] for event in events]


def test_rag_health_search_and_safe_resource_api(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        health = client.get("/api/v1/knowledge/health")
        assert health.status_code == 200
        assert health.json()["rag_status"] == "disabled"
        assert "qdrant_api_key" not in health.text

        response = client.post(
            "/api/v1/knowledge/rag-search",
            json={"query_text": "鑺傜偣鐢靛帇娉?", "course_id": "CT", "top_k": 3},
        )
        assert response.status_code == 200
        response = client.post(
            "/api/v1/knowledge/rag-search",
            json={
                "query_text": "nodal voltage method",
                "course_id": "CT",
                "top_k": 3,
            },
        )
        assert response.status_code == 200
        assert response.json()["rag_status"] == "disabled"
        assert response.json()["hits"]

        image = client.get("/api/v1/knowledge/images/CT/diagram.png")
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/png"
        assert image.headers["cache-control"] == "private, no-store"

        document = client.get(
            "/api/v1/knowledge/documents/CT/chapter.md",
            params={"normalize_math": "true", "chunk": "chunk-1"},
        )
        assert document.status_code == 200
        assert r"$I=\frac{10}{5}=2A$" in document.text
        assert document.headers["cache-control"] == "private, no-store"
        document = client.get("/api/v1/knowledge/documents/CT/chapter.md")
        assert document.status_code == 200
        assert "text/markdown" in document.headers["content-type"]
        chunk_page = client.get(
            "/api/v1/knowledge/document-pages/CT/chapter.md",
            params={"chunk": "chunk-1", "limit": 4000},
        )
        assert chunk_page.status_code == 200
        assert chunk_page.headers["cache-control"] == "private, no-store"
        assert chunk_page.json()["anchor_status"] == "matched"
        assert r"$I=\frac{10}{5}=2A$" in chunk_page.json()["content"]
        traversal = client.get("/api/v1/knowledge/documents/CT/../.env")
        assert traversal.status_code in {400, 404}


def test_document_page_anchors_and_pages_even_when_chunk_is_stale(
    tmp_path: Path,
) -> None:
    anchor = "随机过程除了广义平稳外还必须满足进一步的约束条件"
    document_path = tmp_path / "ct" / "chapter.md"
    with make_client(tmp_path) as client:
        document_path.write_text(
            "# 完整教材\n"
            + ("前段教材内容。\n" * 900)
            + f"\n## 命中章节\n{anchor}，并满足 $I=10/5=2A$。\n"
            + ("后段教材内容。\n" * 900),
            encoding="utf-8",
        )

        response = client.get(
            "/api/v1/knowledge/document-pages/CT/chapter.md",
            params={
                "normalize_math": "true",
                "chunk": "chunk-9999",
                "anchor": anchor,
                "limit": 4000,
            },
        )

        assert response.status_code == 200
        page = response.json()
        assert page["requested_chunk"] == "chunk-9999"
        assert page["anchor_status"] == "matched"
        assert anchor in page["content"]
        assert r"$I=\frac{10}{5}=2A$" in page["content"]
        assert page["previous_offset"] is not None
        assert page["next_offset"] is not None
        assert page["end_offset"] - page["start_offset"] >= 4000

        next_response = client.get(
            "/api/v1/knowledge/document-pages/CT/chapter.md",
            params={"offset": page["next_offset"], "limit": 4000},
        )
        assert next_response.status_code == 200
        next_page = next_response.json()
        assert next_page["start_offset"] >= page["end_offset"]
        assert next_page["anchor_status"] == "not_requested"


def test_document_page_defaults_to_bounded_chunk_context(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get(
            "/api/v1/knowledge/document-pages/CT/chapter.md",
            params={"chunk": "chunk-1"},
        )

        assert response.status_code == 200
        page = response.json()
        assert page["anchor_status"] == "matched"
        assert page["end_offset"] - page["start_offset"] <= 8_000
        assert r"$I=\frac{10}{5}=2A$" in page["content"]


def test_document_page_prefers_evidence_anchor_over_stale_chunk_context(
    tmp_path: Path,
) -> None:
    target = "ANCHOR_KCL_TARGET"
    document_path = tmp_path / "ct" / "chapter.md"
    with make_client(tmp_path) as client:
        document_path.write_text(
            ("prefix material\n" * 80) + f"{target}: KCL evidence\n" + ("tail\n" * 80),
            encoding="utf-8",
        )

        response = client.get(
            "/api/v1/knowledge/document-pages/CT/chapter.md",
            params={
                "chunk": "chunk-1",
                "anchor": target,
                "limit": 4000,
                "normalize_math": "false",
            },
        )

        assert response.status_code == 200
        page = response.json()
        assert page["anchor_status"] == "matched"
        assert target in page["content"]
        assert "KCL evidence" in page["content"]


def test_document_page_reports_missing_anchor_without_hiding_document(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        response = client.get(
            "/api/v1/knowledge/document-pages/CT/chapter.md",
            params={"anchor": "不存在于本地版本的索引片段"},
        )

        assert response.status_code == 200
        page = response.json()
        assert page["anchor_status"] == "not_found"
        assert page["content"]
        assert page["start_offset"] == 0
