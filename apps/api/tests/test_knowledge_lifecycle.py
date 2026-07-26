from __future__ import annotations

import json
from pathlib import Path

from app.contracts.knowledge import (
    DocumentManifest,
    KnowledgeCourseId,
    KnowledgeHit,
    RetrievalContextPacket,
)
from app.services.citation_validator import CitationValidator
from app.services.knowledge_index import KnowledgeIndexBuilder, load_jsonl


def _builder(tmp_path: Path) -> KnowledgeIndexBuilder:
    roots = {code: tmp_path / code for code in ("CT", "AE", "DE")}
    for root in roots.values():
        root.mkdir()
    return KnowledgeIndexBuilder(
        roots=roots,
        output_root=tmp_path / "index",
        max_parse_bytes=100_000,
        chunk_size=160,
        overlap_chars=10,
    )


def test_document_contract_rejects_absolute_path() -> None:
    try:
        DocumentManifest(
            document_id="DOC_1",
            course_id="CT",
            source_file="a.md",
            source_relative_path="C:/private/a.md",
            content_hash="abc",
        )
    except ValueError as exc:
        assert "相对路径" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("absolute source path should be rejected")


def test_incremental_build_reuses_then_retires_changed_version(tmp_path: Path) -> None:
    builder = _builder(tmp_path)
    source = tmp_path / "CT" / "chapter.md"
    source.write_text("# 节点法\n\n节点方程使用 KCL。", encoding="utf-8")

    audit_v1, first = builder.build()
    doc_v1 = next(item for item in audit_v1.manifest if item.active)
    assert doc_v1.document_version == "v1"
    _, second = builder.build()
    assert second.reused_chunk_count == first.chunk_count

    source.write_text(
        "# 节点法\n\n节点方程使用 KCL，并检查参考方向。", encoding="utf-8"
    )
    audit_v2, third = builder.build()
    active = next(item for item in audit_v2.manifest if item.active)
    retired = next(item for item in audit_v2.manifest if not item.active)
    assert active.document_version == "v2"
    assert retired.document_version == "v1"
    assert third.rebuilt_document_count == 1
    history = load_jsonl(builder.chunk_history_path)
    assert history and all(item["is_active"] is False for item in history)
    state = json.loads(builder.state_path.read_text(encoding="utf-8"))
    assert state["active_documents"] == 1


def test_citation_validator_marks_checksum_mismatch_as_stale() -> None:
    hit = KnowledgeHit(
        chunk_id="CHK_1",
        evidence_id="S1",
        document_id="DOC_1",
        course_id=KnowledgeCourseId.CIRCUIT_THEORY,
        course_name="电路理论",
        document_path="chapter.md",
        title="节点法",
        content="节点法使用 KCL",
        score=1,
        source_ref="kb://CT/chapter.md#chunk-1",
        document_checksum="old",
    )
    packet = RetrievalContextPacket(
        query="节点法",
        course_id="CT",
        intent="general_qa",
        evidence=[hit],
        source_refs=[hit.source_ref],
        evidence_status="sufficient",
        max_context_chars=1000,
    )
    result = CitationValidator().validate(
        "节点法使用 KCL [S1]",
        packet,
        manifests=[
            {
                "document_id": "DOC_1",
                "document_version": "v2",
                "checksum": "new",
                "active": True,
            }
        ],
        chunks=[{"chunk_id": "CHK_1", "is_active": True}],
    )
    assert result.support_status == "stale"
    assert result.supports[0].status == "stale"
