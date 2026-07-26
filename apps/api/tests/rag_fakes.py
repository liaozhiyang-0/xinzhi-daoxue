from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.services.rag_providers import ProviderHealth


def _normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


class DeterministicFakeTextEmbeddingProvider:
    model_name = "tests/fake-bge"

    def __init__(self, revision: str = "test-v1", *, fail: bool = False) -> None:
        self.model_revision = revision
        self.fail = fail
        self.loaded = False

    def load(self) -> None:
        if self.fail:
            raise RuntimeError("fake text model unavailable")
        self.loaded = True

    def _vector(self, text: str) -> list[float]:
        self.load()
        return _normalize(
            [
                float(sum(text.count(term) for term in ("电容", "戴维南", "电路"))),
                float(sum(text.count(term) for term in ("负反馈", "放大", "模拟"))),
                float(sum(text.count(term) for term in ("触发器", "时序", "数字"))),
                0.1,
            ]
        )

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("empty")
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    @property
    def dimension(self) -> int:
        self.load()
        return 4

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="ready" if self.loaded else "not_loaded",
            loaded=self.loaded,
            model_name=self.model_name,
            model_revision=self.model_revision,
            dimension=4 if self.loaded else None,
            device="test",
            reason=None,
        )

    def close(self) -> None:
        self.loaded = False


class DeterministicFakeImageEmbeddingProvider:
    model_name = "tests/fake-siglip2"

    def __init__(self, revision: str = "test-v1", *, fail: bool = False) -> None:
        self.model_revision = revision
        self.fail = fail
        self.loaded = False

    def load(self) -> None:
        if self.fail:
            raise RuntimeError("fake image model unavailable")
        self.loaded = True

    @property
    def dimension(self) -> int:
        self.load()
        return 4

    def embed_images(self, image_paths: Sequence[Path]) -> list[list[float]]:
        return [self.embed_image(path) for path in image_paths]

    def embed_image(self, image: Path | bytes | Any) -> list[float]:
        self.load()
        raw = image.read_bytes() if isinstance(image, Path) else bytes(image)
        marker = raw[-1] if raw else 0
        return _normalize(
            [float(marker < 85), float(85 <= marker < 170), float(marker >= 170), 0.1]
        )

    def embed_text_queries(self, texts: Sequence[str]) -> list[list[float]]:
        self.load()
        return [
            _normalize(
                [
                    float("电路" in text or "电容" in text),
                    float("放大" in text or "反馈" in text),
                    float("时序" in text or "触发器" in text),
                    0.1,
                ]
            )
            for text in texts
        ]

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="ready" if self.loaded else "not_loaded",
            loaded=self.loaded,
            model_name=self.model_name,
            model_revision=self.model_revision,
            dimension=4 if self.loaded else None,
            device="test",
            reason=None,
        )

    def close(self) -> None:
        self.loaded = False


class DeterministicFakeReranker:
    model_name = "tests/fake-reranker"
    model_revision = "test-v1"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.loaded = False

    def load(self) -> None:
        if self.fail:
            raise RuntimeError("fake reranker unavailable")
        self.loaded = True

    def rerank(self, query: str, passages: Sequence[str]) -> list[float]:
        self.load()
        query_chars = set(query)
        return [float(len(query_chars & set(passage))) for passage in passages]

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="ready" if self.loaded else "not_loaded",
            loaded=self.loaded,
            model_name=self.model_name,
            model_revision=self.model_revision,
            dimension=None,
            device="test",
            reason=None,
        )

    def close(self) -> None:
        self.loaded = False
