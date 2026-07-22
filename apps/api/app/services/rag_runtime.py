from __future__ import annotations

from app.core.config import Settings
from app.providers.embedding.fallback import DevelopmentEmbeddingFallback
from app.providers.embedding.hash_legacy import HashLegacyEmbeddingProvider
from app.providers.embedding.local_sentence_transformer import (
    LocalSentenceTransformerEmbeddingProvider,
)
from app.services.rag_providers import (
    BGERerankerProvider,
    LocalSigLIP2ImageEmbeddingProvider,
    TextEmbeddingProvider,
)
from app.services.vector_store import QdrantVectorStoreAdapter


def create_text_embedding_provider(
    settings: Settings,
) -> TextEmbeddingProvider:
    legacy = HashLegacyEmbeddingProvider(
        dimension=settings.legacy_hash_embedding_dimension
    )
    if settings.text_embedding_provider == "hash_legacy":
        return legacy
    primary = LocalSentenceTransformerEmbeddingProvider(
        model_name=settings.text_embedding_model,
        revision=settings.text_embedding_revision,
        device=settings.text_embedding_device,
        batch_size=settings.text_embedding_batch_size,
        normalize=settings.text_embedding_normalize,
        max_length=settings.text_embedding_max_length,
        cache_dir=settings.text_embedding_cache_dir,
        trust_remote_code=settings.text_embedding_trust_remote_code,
        query_instruction=settings.text_embedding_query_instruction,
    )
    if settings.app_env == "development" and settings.legacy_hash_embedding_enabled:
        return DevelopmentEmbeddingFallback(primary, legacy)
    return primary


def create_image_embedding_provider(
    settings: Settings,
) -> LocalSigLIP2ImageEmbeddingProvider:
    return LocalSigLIP2ImageEmbeddingProvider(
        model_name=settings.image_embedding_model,
        revision=settings.image_embedding_revision,
        device=settings.image_embedding_device,
        batch_size=settings.image_embedding_batch_size,
        normalize=settings.image_embedding_normalize,
        cache_dir=settings.image_embedding_cache_dir,
    )


def create_reranker_provider(settings: Settings) -> BGERerankerProvider:
    return BGERerankerProvider(
        model_name=settings.reranker_model,
        revision=settings.reranker_revision,
        device=settings.reranker_device,
        cache_dir=settings.text_embedding_cache_dir,
    )


def create_vector_store(settings: Settings) -> QdrantVectorStoreAdapter:
    return QdrantVectorStoreAdapter(
        mode=settings.qdrant_mode,
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value(),
        local_path=settings.qdrant_local_path,
        text_collection=settings.qdrant_text_collection,
        image_collection=settings.qdrant_image_collection,
    )
