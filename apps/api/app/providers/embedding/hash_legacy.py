from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence

from app.providers.embedding.base import EmbeddingProvider
from app.services.rag_providers import ProviderHealth


class HashLegacyEmbeddingProvider(EmbeddingProvider):
    """Deterministic compatibility vectors; never presented as semantic embeddings."""

    model_name = "legacy-hash-sha256-v1"
    model_revision = "1"
    device = "cpu"

    def __init__(self, *, dimension: int = 384) -> None:
        if dimension < 8:
            raise ValueError("legacy hash dimension must be >= 8")
        self._dimension = dimension

    def load(self) -> None:
        return None

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        values = [text.strip() for text in texts]
        if not values or any(not item for item in values):
            raise ValueError("Embedding 输入不得为空")
        return [self._embed(item) for item in values]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self.embed_texts(texts)

    def embed_query(self, query: str) -> list[float]:
        if not query.strip():
            raise ValueError("Embedding 查询不得为空")
        return self._embed(query.strip())

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        normalized = " ".join(text.lower().split())
        tokens = [normalized[index : index + 2] for index in range(len(normalized) - 1)]
        if not tokens:
            tokens = [normalized]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            position = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[position] += sign
        norm = math.sqrt(sum(item * item for item in vector)) or 1.0
        return [item / norm for item in vector]

    @property
    def dimension(self) -> int:
        return self._dimension

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="legacy_fallback",
            loaded=True,
            model_name=self.model_name,
            model_revision=self.model_revision,
            dimension=self.dimension,
            device=self.device,
            reason="legacy_embedding_fallback=true",
        )

    def close(self) -> None:
        return None
