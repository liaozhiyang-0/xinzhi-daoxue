import math
import sys
from types import SimpleNamespace

from app.providers.embedding import HashLegacyEmbeddingProvider
from app.services.rag_providers import (
    LocalBGETextEmbeddingProvider,
    LocalSigLIP2ImageEmbeddingProvider,
)


def test_legacy_hash_embedding_is_deterministic_and_normalized() -> None:
    provider = HashLegacyEmbeddingProvider(dimension=64)

    first = provider.embed_query("电容电压连续")
    second = provider.embed_query("电容电压连续")

    assert first == second
    assert len(first) == 64
    assert math.isclose(sum(value * value for value in first), 1.0)
    assert provider.health().reason == "legacy_embedding_fallback=true"


def test_local_text_model_load_does_not_probe_the_network(monkeypatch) -> None:
    tokenizer_kwargs: dict[str, object] = {}
    model_kwargs: dict[str, object] = {}

    class FakeTokenizer:
        model_max_length = 512

        @classmethod
        def from_pretrained(cls, model_name: str, **kwargs: object) -> object:
            tokenizer_kwargs["model_name"] = model_name
            tokenizer_kwargs.update(kwargs)
            return cls()

    class FakeModel:
        config = SimpleNamespace(
            hidden_size=384,
            max_position_embeddings=512,
            _commit_hash="local-revision",
        )

        @classmethod
        def from_pretrained(cls, model_name: str, **kwargs: object) -> object:
            model_kwargs["model_name"] = model_name
            model_kwargs.update(kwargs)
            return cls()

        def to(self, _device: str) -> object:
            return self

        def eval(self) -> None:
            return None

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(AutoModel=FakeModel, AutoTokenizer=FakeTokenizer),
    )
    provider = LocalBGETextEmbeddingProvider(
        model_name="local/text",
        revision="revision",
        device="cpu",
        batch_size=1,
        normalize=True,
        max_length=512,
        cache_dir=None,
        trust_remote_code=False,
        local_files_only=True,
    )

    provider.load()

    assert tokenizer_kwargs["local_files_only"] is True
    assert model_kwargs["local_files_only"] is True


def test_local_image_model_load_does_not_probe_the_network(monkeypatch) -> None:
    processor_kwargs: dict[str, object] = {}
    model_kwargs: dict[str, object] = {}

    class FakeProcessor:
        @classmethod
        def from_pretrained(
            cls, model_name: str, **kwargs: object
        ) -> object:
            processor_kwargs["model_name"] = model_name
            processor_kwargs.update(kwargs)
            return cls()

    class FakeModel:
        config = SimpleNamespace(projection_dim=768, _commit_hash="local-revision")

        @classmethod
        def from_pretrained(cls, model_name: str, **kwargs: object) -> object:
            model_kwargs["model_name"] = model_name
            model_kwargs.update(kwargs)
            return cls()

        def to(self, _device: str) -> object:
            return self

        def eval(self) -> None:
            return None

    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(AutoModel=FakeModel, AutoProcessor=FakeProcessor),
    )
    provider = LocalSigLIP2ImageEmbeddingProvider(
        model_name="local/image",
        revision="revision",
        device="cpu",
        batch_size=1,
        normalize=True,
        cache_dir=None,
        local_files_only=True,
    )

    provider.load()

    assert processor_kwargs["local_files_only"] is True
    assert model_kwargs["local_files_only"] is True
