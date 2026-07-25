from __future__ import annotations

from pathlib import Path

from app.contracts import KnowledgeHit, RetrievalContextPacket
from app.core.config import Settings
from app.services.citation_validator import CitationValidator
from app.services.knowledge_base import KnowledgeBaseService
from app.services.knowledge_resources import resolve_course_resource
from app.services.rag_index import IndexVersionInfo, MultimodalRAGIndexer
from app.services.rag_retrieval import RAGRetrievalService
from app.services.vector_store import QdrantVectorStoreAdapter
from pytest import MonkeyPatch

from tests.rag_fakes import (
    DeterministicFakeImageEmbeddingProvider,
    DeterministicFakeReranker,
    DeterministicFakeTextEmbeddingProvider,
)


def settings(tmp_path: Path) -> Settings:
    roots = {
        course: tmp_path / course
        for course in ("CT", "AE", "DE", "SS", "DSP", "COMM")
    }
    for root in roots.values():
        root.mkdir()
    (roots["CT"] / "chapter.md").write_text(
        "# 电容电路方法\n电容电压不能突变，分析时使用换路定律。", encoding="utf-8"
    )
    (roots["AE"] / "chapter.md").write_text(
        "# 负反馈\n负反馈可以稳定放大倍数。", encoding="utf-8"
    )
    (roots["DE"] / "chapter.md").write_text(
        "# D触发器时序\n分析建立时间和保持时间。", encoding="utf-8"
    )
    return Settings(
        app_env="test",
        rag_enabled=True,
        knowledge_ct_path=roots["CT"],
        knowledge_ae_path=roots["AE"],
        knowledge_de_path=roots["DE"],
        knowledge_ss_path=roots["SS"],
        knowledge_dsp_path=roots["DSP"],
        knowledge_comm_path=roots["COMM"],
        knowledge_chunk_size_chars=300,
        knowledge_index_path=tmp_path / "indexes",
        qdrant_local_path=tmp_path / "qdrant",
        qdrant_text_collection="text_test",
        qdrant_image_collection="image_test",
        reranker_enabled=True,
        rag_default_use_reranker=True,
        _env_file=None,
    )


def store_for(config: Settings) -> QdrantVectorStoreAdapter:
    return QdrantVectorStoreAdapter(
        mode="local",
        url="",
        api_key="",
        local_path=config.qdrant_local_path,
        text_collection=config.qdrant_text_collection,
        image_collection=config.qdrant_image_collection,
    )


def test_server_qdrant_can_ignore_system_proxy(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    class FakeQdrantClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.vector_store.QdrantClient", FakeQdrantClient)
    store = QdrantVectorStoreAdapter(
        mode="server",
        url="http://127.0.0.1:6333",
        api_key="",
        local_path=tmp_path / "qdrant",
        text_collection="text",
        image_collection="image",
        trust_env=False,
    )

    assert store.client is not None
    assert captured["trust_env"] is False


def seed(store: QdrantVectorStoreAdapter) -> None:
    text = DeterministicFakeTextEmbeddingProvider()
    image = DeterministicFakeImageEmbeddingProvider()
    store.ensure_collections(4, 4, recreate=True)
    text_records = [
        {
            "chunk_id": "ct-1",
            "document_id": "ct-doc",
            "course_id": "CT",
            "chapter": "第一章",
            "title": "电容电路方法",
            "content_type": "method",
            "text": "电容电压不能突变，分析时使用换路定律。",
            "source_uri": "kb://CT/chapter.md#chunk-1",
            "relative_path": "chapter.md",
            "checksum": "ct",
            "parent_section": "电容电路方法",
        },
        {
            "chunk_id": "ae-1",
            "document_id": "ae-doc",
            "course_id": "AE",
            "chapter": "第一章",
            "title": "负反馈",
            "content_type": "concept",
            "text": "负反馈可以稳定放大倍数。",
            "source_uri": "kb://AE/chapter.md#chunk-1",
            "relative_path": "chapter.md",
            "checksum": "ae",
            "parent_section": "负反馈",
        },
    ]
    store.upsert_text(
        text_records, text.embed_documents([item["text"] for item in text_records])
    )
    image_record = {
        "image_id": "ct-image",
        "course_id": "CT",
        "parent_document_id": "ct-doc",
        "parent_chunk_id": "ct-1",
        "image_type": "circuit_diagram",
        "caption": "电容电路图",
        "resource_uri": "kb-image://CT/images/circuit.png",
        "relative_path": "images/circuit.png",
        "description_source": "source_text",
    }
    store.upsert_images(
        [image_record],
        [image.embed_image(b"\x01")],
        text.embed_documents(["电容电路图"]),
    )


def test_qdrant_named_vectors_upsert_filter_and_persist(tmp_path: Path) -> None:
    config = settings(tmp_path)
    store = store_for(config)
    seed(store)
    query = DeterministicFakeTextEmbeddingProvider().embed_query("电容电路")

    hits = store.search_text(query, course_id="CT", limit=3)
    assert [item.item_id for item in hits] == ["ct-1"]
    assert not store.search_text(query, course_id="DE", limit=3)
    assert store.health()["text_vector_count"] == 2
    store.close()

    reopened = store_for(config)
    assert reopened.health()["image_vector_count"] == 1
    reopened.close()


def test_multimodal_rrf_text_to_image_image_to_image_and_rerank(
    tmp_path: Path,
) -> None:
    config = settings(tmp_path)
    store = store_for(config)
    seed(store)
    service = RAGRetrievalService(
        config,
        KnowledgeBaseService(config),
        DeterministicFakeTextEmbeddingProvider(),
        DeterministicFakeImageEmbeddingProvider(),
        DeterministicFakeReranker(),
        store,
    )

    text_result = service.search(
        query_text="电容电路为什么不能突变",
        course_id="CT",
        intent="explain_concept",
        target_agent_id="LEARN_01_KNOWLEDGE_QA_V1",
    )
    assert text_result.rag_status == "ready"
    assert text_result.hits[0].chunk_id == "ct-1"
    assert "dense_rank" in text_result.hits[0].score_components
    assert text_result.hits[0].score_components["rerank_score"] > 0
    assert text_result.image_hits[0].image_id == "ct-image"
    assert "text_visual" in text_result.image_hits[0].retrieval_channels

    image_result = service.search(
        query_image=b"\x01",
        course_id="CT",
        target_agent_id="SOLVER_CT_V1",
    )
    assert image_result.query_modalities == ["image"]
    assert image_result.image_hits[0].image_id == "ct-image"
    assert image_result.hits[0].chunk_id == "ct-1"
    assert not service.search(query_text="电容", course_id="DE").hits
    service.close()


def test_failed_model_is_explicitly_degraded_without_hash_fallback(
    tmp_path: Path,
) -> None:
    config = settings(tmp_path)
    store = store_for(config)
    seed(store)
    service = RAGRetrievalService(
        config,
        KnowledgeBaseService(config),
        DeterministicFakeTextEmbeddingProvider(fail=True),
        DeterministicFakeImageEmbeddingProvider(fail=True),
        DeterministicFakeReranker(),
        store,
    )

    result = service.search(query_text="电容电压", course_id="CT")

    assert result.rag_status == "degraded"
    assert result.embedding_status == "failed"
    assert result.retrieval_mode == "multimodal_hybrid_rrf_v2"
    assert any("degraded" in warning for warning in result.warnings)
    service.close()


def test_citation_validator_and_safe_resource_paths(tmp_path: Path) -> None:
    config = settings(tmp_path)
    hit = KnowledgeHit(
        evidence_id="S1",
        course_id="CT",
        course_name="电路理论",
        document_path="chapter.md",
        title="电容",
        content="内容",
        score=1,
        source_ref="kb://CT/chapter.md#chunk-1",
    )
    packet = RetrievalContextPacket(
        query="问题",
        course_id="CT",
        intent="general_qa",
        evidence=[hit],
        source_refs=[hit.source_ref],
        evidence_status="partial",
        max_context_chars=1000,
    )
    valid = CitationValidator().validate("依据 [S1]。", packet)
    invalid = CitationValidator().validate("依据 [S9]。", packet)

    assert valid.valid
    assert invalid.invalid_ids == ("S9",)
    assert resolve_course_resource(
        config, course_id="CT", relative_path="chapter.md", text_only=True
    ).is_file()
    try:
        resolve_course_resource(
            config, course_id="CT", relative_path="../.env", text_only=True
        )
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal should be rejected")


def test_index_version_changes_with_model_revision() -> None:
    base = dict(
        schema_version="2",
        chunker_version="semantic_v2",
        cleaning_version="clean_v1",
        text_embedding_model="fake-bge",
        image_embedding_model="fake-siglip",
        text_dimension=4,
        image_dimension=4,
        text_normalize=True,
        image_normalize=True,
    )
    first = IndexVersionInfo(
        **base, text_embedding_revision="one", image_embedding_revision="one"
    )
    second = IndexVersionInfo(
        **base, text_embedding_revision="two", image_embedding_revision="one"
    )
    assert first.version_id != second.version_id


def test_incremental_multimodal_index_reuses_unchanged_points(
    tmp_path: Path,
) -> None:
    config = settings(tmp_path)
    chunk_path = config.knowledge_index_path / "cache" / "knowledge_base_chunks.jsonl"
    chunk_path.parent.mkdir(parents=True)
    chunk_path.write_text(
        '{"chunk_id":"ct-1","document_id":"doc-1","document_checksum":"sum-1",'
        '"course_id":"CT","relative_path":"chapter.md","title":"method",'
        '"chapter":"one","content_type":"method","chunk_index":1,'
        '"text":"circuit method","source_uri":"kb://CT/chapter.md#chunk-1"}\n',
        encoding="utf-8",
    )
    image_source = config.knowledge_paths["CT"] / "diagram.png"
    image_source.write_bytes(b"fake-image-1")
    image_path = config.knowledge_index_path / "knowledge_base_image_evidence.jsonl"
    image_path.write_text(
        '{"image_id":"img-1","course_id":"CT","source_path":"diagram.png",'
        '"resource_uri":"kb-image://CT/diagram.png","checksum":"image-sum-1",'
        '"parent_document_id":"doc-1","parent_chunk_id":"ct-1",'
        '"image_caption":"circuit diagram","nearby_text":"method"}\n',
        encoding="utf-8",
    )
    store = store_for(config)
    indexer = MultimodalRAGIndexer(
        config,
        DeterministicFakeTextEmbeddingProvider(),
        DeterministicFakeImageEmbeddingProvider(),
        store,
    )

    first = indexer.build(incremental=True)
    second = indexer.build(incremental=True)

    assert (first.text_points, first.image_points) == (1, 1)
    assert (second.text_points, second.image_points) == (0, 0)
    assert (second.reused_text_points, second.reused_image_points) == (1, 1)
    store.close()
