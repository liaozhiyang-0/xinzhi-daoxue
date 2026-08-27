from __future__ import annotations

import gc
import json
import warnings
from pathlib import Path

from app.contracts import KnowledgeHit, RetrievalContextPacket, RetrievalResult
from app.core.config import Settings
from app.services.citation_validator import CitationValidator
from app.services.knowledge_base import KnowledgeBaseService
from app.services.knowledge_resources import resolve_course_resource
from app.services.rag_index import IndexVersionInfo, MultimodalRAGIndexer
from app.services.rag_retrieval import RAGRetrievalService, _Candidate
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
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        config = settings(tmp_path)
        store = store_for(config)
        seed(store)
        query = DeterministicFakeTextEmbeddingProvider().embed_query("电容电路")

        hits = store.search_text(query, course_id="CT", limit=3)
        assert [item.item_id for item in hits] == ["ct-1"]
        assert not store.search_text(query, course_id="DE", limit=3)
        assert store.health()["text_vector_count"] == 2
        metrics = store.metrics()
        assert metrics["ensure_collections"]["count"] == 1
        assert metrics["upsert_text"]["count"] == 1
        assert metrics["search_text"]["count"] == 2
        assert store.health()["backend"] == "embedded_sqlite"
        store.close()

        reopened = store_for(config)
        assert reopened.health()["image_vector_count"] == 1
        reopened.close()
        gc.collect()

    assert not any("unclosed database" in str(item.message) for item in caught)


def test_vector_health_exposes_embedding_dimension_mismatch(tmp_path: Path) -> None:
    store = QdrantVectorStoreAdapter(
        mode="local",
        url="",
        api_key="",
        local_path=tmp_path / "qdrant",
        text_collection="text_test",
        image_collection="image_test",
    )
    store.ensure_collections(512, 768)

    health = store.health(
        expected_text_dimension=384,
        expected_image_dimension=768,
    )

    assert health["connected"] is True
    assert health["compatible"] is False
    assert health["reason"] == "vector_dimension_mismatch"
    assert health["collection_dimensions"]["text_test"]["text_dense"] == 512
    assert health["dimension_mismatches"] == [
        {
            "collection": "text_test",
            "vector_name": "text_dense",
            "expected": 384,
            "actual": 512,
        },
        {
            "collection": "image_test",
            "vector_name": "image_caption_dense",
            "expected": 384,
            "actual": 512,
        },
    ]
    store.close()


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
        target_agent_id="ACADEMIC_PROBLEM_SOLVER",
    )
    assert image_result.query_modalities == ["image"]
    assert image_result.image_hits[0].image_id == "ct-image"
    assert image_result.hits[0].chunk_id == "ct-1"
    assert not service.search(query_text="电容", course_id="DE").hits
    service.close()


def test_rag_filters_low_relevance_candidates_before_exposing_evidence(
    tmp_path: Path,
) -> None:
    config = settings(tmp_path).model_copy(update={"rag_min_retrieval_score": 1.0})
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

    result = service.search(query_text="电容电压", course_id="CT", include_images=False)

    assert result.hits == []
    assert "no_relevant_course_evidence" in result.warnings
    assert result.trace["filtered_low_relevance"] >= 1
    service.close()
    store.close()


def test_rag_rejects_stale_vectors_for_revoked_material(
    tmp_path: Path,
) -> None:
    config = settings(tmp_path)
    config.knowledge_index_path.mkdir(parents=True, exist_ok=True)
    (config.knowledge_index_path / "rag_index_state.json").write_text(
        json.dumps(
            {
                "index_version": "v1",
                "material_revocation_version": "revoked-1",
                "revoked_material_chunk_ids": ["ct-1"],
            }
        ),
        encoding="utf-8",
    )
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

    result = service.search(
        query_text="电容电路为什么不能突变",
        course_id="CT",
        intent="explain_concept",
        target_agent_id="LEARN_01_KNOWLEDGE_QA_V1",
    )

    assert all(hit.chunk_id != "ct-1" for hit in result.hits)
    assert all(image.image_id != "ct-image" for image in result.image_hits)
    assert "revoked_course_material_filtered" in " ".join(result.warnings)
    assert service._index_version().endswith("material-revocation:revoked-1")
    service.close()


def test_rag_revokes_sparse_uploaded_material_by_source_uri() -> None:
    candidate = _Candidate(
        KnowledgeHit(
            evidence_id="material-0",
            course_id="CT",
            course_name="电路理论",
            document_path="materials/file-1/lesson.txt",
            title="上传课程资料",
            content_type="course_material",
            content="KCL lesson",
            score=1.0,
            source_ref="kb-material://CT/file-1#chunk-0",
        ),
        {},
    )

    assert RAGRetrievalService._candidate_is_revoked(
        "material-file-1-0",
        candidate,
        revoked_chunk_ids=set(),
        revoked_material_ids={"file-1"},
    )
    assert RAGRetrievalService._candidate_is_revoked(
        "material-file-1-0",
        candidate,
        revoked_chunk_ids=set(),
        revoked_material_ids={"__revocation_state_unavailable__"},
    )


def test_visual_parent_retrieval_respects_content_type_policy(
    tmp_path: Path,
) -> None:
    config = settings(tmp_path)
    store = store_for(config)
    store.ensure_collections(4, 4, recreate=True)
    text = DeterministicFakeTextEmbeddingProvider()
    image = DeterministicFakeImageEmbeddingProvider()
    store.upsert_text(
        [
            {
                "chunk_id": "allowed",
                "document_id": "doc",
                "course_id": "CT",
                "chapter": "chapter",
                "title": "allowed",
                "content_type": "concept",
                "text": "capacitor concept",
                "source_uri": "kb://CT/allowed",
                "relative_path": "chapter.md",
                "checksum": "x",
                "parent_section": "chapter",
            },
            {
                "chunk_id": "blocked",
                "document_id": "doc",
                "course_id": "CT",
                "chapter": "chapter",
                "title": "blocked",
                "content_type": "waveform",
                "text": "capacitor waveform",
                "source_uri": "kb://CT/blocked",
                "relative_path": "chapter.md",
                "checksum": "x",
                "parent_section": "chapter",
            },
        ],
        text.embed_documents(["capacitor concept", "capacitor waveform"]),
    )

    class ParentOnlyStore:
        def __init__(self, wrapped: QdrantVectorStoreAdapter) -> None:
            self.wrapped = wrapped

        def __getattr__(self, name: str) -> object:
            return getattr(self.wrapped, name)

        def search_text(self, *args: object, **kwargs: object) -> list[object]:
            return []

        def search_images(self, *args: object, **kwargs: object) -> list[object]:
            return [
                type(
                    "ImageHit",
                    (),
                    {
                        "item_id": "image",
                        "score": 1.0,
                        "payload": {
                            "image_id": "image",
                            "course_id": "CT",
                            "parent_chunk_id": "blocked",
                            "resource_uri": "kb-image://CT/image",
                        },
                    },
                )()
            ]

    service = RAGRetrievalService(
        config,
        KnowledgeBaseService(config),
        text,
        image,
        DeterministicFakeReranker(),
        ParentOnlyStore(store),
    )
    result = service.search(
        query_text="capacitor",
        course_id="CT",
        content_types=("concept",),
        include_images=True,
        image_top_k=1,
    )

    assert all(hit.content_type == "concept" for hit in result.hits)
    service.close()
    store.close()


def test_disabled_rag_still_applies_agent_content_type_policy(
    tmp_path: Path,
) -> None:
    config = settings(tmp_path).model_copy(update={"rag_enabled": False})
    hits = [
        KnowledgeHit(
            evidence_id="concept-1",
            course_id="CT",
            course_name="电路理论",
            document_path="chapter.md",
            title="concept",
            content_type="concept",
            content="capacitor concept",
            score=1.0,
            source_ref="kb://CT/concept",
        ),
        KnowledgeHit(
            evidence_id="waveform-1",
            course_id="CT",
            course_name="电路理论",
            document_path="chapter.md",
            title="waveform",
            content_type="waveform",
            content="capacitor waveform",
            score=0.9,
            source_ref="kb://CT/waveform",
        ),
    ]

    class LexicalOnly:
        def search_result(
            self,
            _query: str,
            _course_ids: list[str],
            _top_k: int | None,
        ) -> RetrievalResult:
            return RetrievalResult(
                query="capacitor",
                normalized_query="capacitor",
                course_ids=["CT"],
                hits=hits,
                latency_ms=0,
                retrieval_mode="sparse_bm25_v1",
            )

    service = RAGRetrievalService(
        config,
        LexicalOnly(),
        None,
        None,
        None,
        None,
    )
    result = service.search(
        query_text="capacitor",
        course_id="CT",
        content_types=("concept",),
    )

    assert [hit.evidence_id for hit in result.hits] == ["concept-1"]


def test_retrieval_warmup_loads_enabled_models_before_first_query(
    tmp_path: Path,
) -> None:
    config = settings(tmp_path).model_copy(
        update={
            "rag_warmup_image_model": True,
            "rag_warmup_reranker": True,
        }
    )
    text = DeterministicFakeTextEmbeddingProvider()
    image = DeterministicFakeImageEmbeddingProvider()
    reranker = DeterministicFakeReranker()
    service = RAGRetrievalService(
        config,
        KnowledgeBaseService(config),
        text,
        image,
        reranker,
        store_for(config),
    )

    result = service.warmup()
    health = service.health()

    assert result["status"] == "ready"
    assert result["failed_components"] == []
    assert set(result["components"]) == {"text", "image", "reranker"}
    assert text.loaded and image.loaded and reranker.loaded
    assert health["warmup"]["status"] == "ready"
    assert health["text_model_loaded"] is True
    assert health["image_model_loaded"] is True
    assert health["reranker_loaded"] is True
    service.close()


def test_retrieval_warmup_reports_optional_model_failure(
    tmp_path: Path,
) -> None:
    config = settings(tmp_path).model_copy(
        update={
            "rag_warmup_image_model": True,
            "rag_warmup_reranker": False,
            "rag_warmup_strict": False,
        }
    )
    service = RAGRetrievalService(
        config,
        KnowledgeBaseService(config),
        DeterministicFakeTextEmbeddingProvider(),
        DeterministicFakeImageEmbeddingProvider(fail=True),
        DeterministicFakeReranker(),
        store_for(config),
    )

    result = service.warmup()

    assert result["status"] == "degraded"
    assert result["failed_components"] == ["image"]
    assert result["components"]["text"]["warmup_status"] == "ready"
    assert result["components"]["image"]["warmup_status"] == "failed"
    health = service.health()
    assert health["rag_status"] == "degraded"
    assert "image_model_not_loaded" in health["degraded_reasons"]
    assert health["vector_store_backend"] == "embedded_sqlite"
    assert isinstance(health["vector_store_metrics"], dict)
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


def test_rag_index_includes_published_course_material_chunks(tmp_path: Path) -> None:
    config = settings(tmp_path)
    chunk_path = config.knowledge_index_path / "cache" / "course_material_chunks.jsonl"
    chunk_path.parent.mkdir(parents=True)
    chunk_path.write_text(
        json.dumps(
            {
                "chunk_id": "material-file-1-0",
                "document_id": "file-1",
                "document_checksum": "material-sum-1",
                "course_id": "CT",
                "relative_path": "materials/file-1/lesson.txt",
                "title": "kcl-intro",
                "chapter": "KCL",
                "content_type": "course_material",
                "chunk_index": 0,
                "text": "KCL course material",
                "source_uri": "kb-material://CT/file-1#chunk-0",
                "related_images": [],
                "metadata": {"material_file_id": "file-1"},
                "is_active": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    store = store_for(config)
    indexer = MultimodalRAGIndexer(
        config,
        DeterministicFakeTextEmbeddingProvider(),
        DeterministicFakeImageEmbeddingProvider(),
        store,
    )

    result = indexer.build(include_images=False)

    assert result.text_points == 1
    state = json.loads(indexer.state_path.read_text(encoding="utf-8"))
    assert state["material_checksums"] == {"file-1": "material-sum-1"}
    assert store.health()["text_vector_count"] == 1
    store.close()


def test_failed_rebuild_preserves_previous_state_and_vectors(tmp_path: Path) -> None:
    class LateFailTextProvider(DeterministicFakeTextEmbeddingProvider):
        def embed_documents(self, texts):  # type: ignore[no-untyped-def]
            raise RuntimeError("simulated embedding failure")

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
    store = store_for(config)
    first = MultimodalRAGIndexer(
        config,
        DeterministicFakeTextEmbeddingProvider(),
        DeterministicFakeImageEmbeddingProvider(),
        store,
    )
    first.build(include_images=False)
    state_before = first.state_path.read_text(encoding="utf-8")
    count_before = store.health()["text_vector_count"]

    failing = MultimodalRAGIndexer(
        config,
        LateFailTextProvider(revision="test-v2"),
        DeterministicFakeImageEmbeddingProvider(),
        store,
    )
    try:
        failing.build(include_images=False)
    except RuntimeError as exc:
        assert "simulated" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("rebuild should fail")
    assert failing.state_path.read_text(encoding="utf-8") == state_before
    assert store.health()["text_vector_count"] == count_before
    store.close()
