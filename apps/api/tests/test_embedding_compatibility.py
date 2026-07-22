import math

from app.providers.embedding import HashLegacyEmbeddingProvider


def test_legacy_hash_embedding_is_deterministic_and_normalized() -> None:
    provider = HashLegacyEmbeddingProvider(dimension=64)

    first = provider.embed_query("电容电压连续")
    second = provider.embed_query("电容电压连续")

    assert first == second
    assert len(first) == 64
    assert math.isclose(sum(value * value for value in first), 1.0)
    assert provider.health().reason == "legacy_embedding_fallback=true"
