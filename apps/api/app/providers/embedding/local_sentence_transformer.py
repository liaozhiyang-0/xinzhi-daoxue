from __future__ import annotations

from collections.abc import Sequence

from app.services.rag_providers import LocalBGETextEmbeddingProvider


class LocalSentenceTransformerEmbeddingProvider(LocalBGETextEmbeddingProvider):
    """Named adapter for the existing CPU-capable SentenceTransformer provider."""

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return self.embed_documents(texts)
