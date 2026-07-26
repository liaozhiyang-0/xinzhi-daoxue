from __future__ import annotations

import logging
from collections.abc import Sequence

from app.providers.embedding.hash_legacy import HashLegacyEmbeddingProvider
from app.services.rag_providers import ProviderHealth, TextEmbeddingProvider

logger = logging.getLogger(__name__)


class DevelopmentEmbeddingFallback:
    """Use legacy vectors only in development when the real model cannot load."""

    def __init__(
        self,
        primary: TextEmbeddingProvider,
        legacy: HashLegacyEmbeddingProvider,
    ) -> None:
        self.primary = primary
        self.legacy = legacy
        self.model_name = primary.model_name
        self.model_revision = primary.model_revision
        self._using_legacy = False

    def load(self) -> None:
        try:
            self.primary.load()
        except Exception as exc:
            self._activate(exc)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if self._using_legacy:
            return self.legacy.embed_documents(texts)
        try:
            return self.primary.embed_documents(texts)
        except Exception as exc:
            self._activate(exc)
            return self.legacy.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        if self._using_legacy:
            return self.legacy.embed_query(text)
        try:
            return self.primary.embed_query(text)
        except Exception as exc:
            self._activate(exc)
            return self.legacy.embed_query(text)

    @property
    def dimension(self) -> int:
        if self._using_legacy:
            return self.legacy.dimension
        try:
            return self.primary.dimension
        except Exception as exc:
            self._activate(exc)
            return self.legacy.dimension

    def health(self) -> ProviderHealth:
        return self.legacy.health() if self._using_legacy else self.primary.health()

    def close(self) -> None:
        self.primary.close()
        self.legacy.close()

    def _activate(self, exc: Exception) -> None:
        if not self._using_legacy:
            logger.warning(
                "text_embedding_primary_unavailable error=%s "
                "legacy_embedding_fallback=true",
                type(exc).__name__,
            )
        self._using_legacy = True
        self.model_name = self.legacy.model_name
        self.model_revision = self.legacy.model_revision
