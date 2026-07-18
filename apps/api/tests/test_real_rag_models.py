from __future__ import annotations

import math
import os
from pathlib import Path

import pytest
from app.services.rag_providers import (
    LocalBGETextEmbeddingProvider,
    LocalSigLIP2ImageEmbeddingProvider,
)
from app.services.vector_store import QdrantVectorStoreAdapter
from PIL import Image

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.getenv("RUN_REAL_RAG_TESTS") != "1",
        reason="set RUN_REAL_RAG_TESTS=1 to load real models",
    ),
]


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        math.sqrt(sum(value * value for value in left))
        * math.sqrt(sum(value * value for value in right))
    )


def test_real_bge_semantic_similarity(tmp_path: Path) -> None:
    shared_cache = Path(os.environ["HF_HOME"]) if os.getenv("HF_HOME") else None
    provider = LocalBGETextEmbeddingProvider(
        model_name=os.getenv("REAL_TEXT_MODEL", "BAAI/bge-small-zh-v1.5"),
        revision="main",
        device="cpu",
        batch_size=2,
        normalize=True,
        max_length=512,
        cache_dir=shared_cache,
        trust_remote_code=False,
        query_instruction="为这个句子生成表示以用于检索相关文章：",
    )
    vectors = provider.embed_documents(
        ["电容两端电压不能发生突变", "电容电压具有连续性", "数字触发器保存逻辑状态"]
    )
    assert provider.dimension > 0
    assert cosine(vectors[0], vectors[1]) > cosine(vectors[0], vectors[2])
    provider.close()


def test_real_siglip2_visual_embedding_and_qdrant_persistence(
    tmp_path: Path,
) -> None:
    shared_cache = Path(os.environ["HF_HOME"]) if os.getenv("HF_HOME") else None
    model = os.getenv("REAL_IMAGE_MODEL", "google/siglip2-base-patch16-224")
    provider = LocalSigLIP2ImageEmbeddingProvider(
        model_name=model,
        revision="main",
        device="cpu",
        batch_size=2,
        normalize=True,
        cache_dir=shared_cache,
    )
    original = tmp_path / "original.png"
    scaled = tmp_path / "scaled.png"
    unrelated = tmp_path / "unrelated.png"
    Image.new("RGB", (80, 40), "red").save(original)
    Image.open(original).resize((160, 80)).save(scaled)
    Image.new("RGB", (80, 40), "blue").save(unrelated)
    vectors = provider.embed_images([original, scaled, unrelated])
    assert provider.dimension > 0
    assert cosine(vectors[0], vectors[1]) > cosine(vectors[0], vectors[2])

    store = QdrantVectorStoreAdapter(
        mode="local",
        url="",
        api_key="",
        local_path=tmp_path / "qdrant",
        text_collection="real_text",
        image_collection="real_image",
    )
    store.ensure_collections(4, provider.dimension, recreate=True)
    store.upsert_images(
        [
            {
                "image_id": "real-image",
                "course_id": "CT",
                "resource_uri": "kb-image://CT/original.png",
            }
        ],
        [vectors[0]],
        [[1.0, 0.0, 0.0, 0.0]],
    )
    assert store.health()["image_vector_count"] == 1
    store.close()
    reopened = QdrantVectorStoreAdapter(
        mode="local",
        url="",
        api_key="",
        local_path=tmp_path / "qdrant",
        text_collection="real_text",
        image_collection="real_image",
    )
    assert reopened.health()["image_vector_count"] == 1
    reopened.close()
    provider.close()
