from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any, Protocol

import numpy as np


@dataclass(slots=True)
class ProviderHealth:
    status: str
    loaded: bool
    model_name: str
    model_revision: str
    dimension: int | None
    device: str
    reason: str | None = None
    load_latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TextEmbeddingProvider(Protocol):
    model_name: str
    model_revision: str

    def load(self) -> None: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...

    @property
    def dimension(self) -> int: ...

    def health(self) -> ProviderHealth: ...

    def close(self) -> None: ...


class ImageEmbeddingProvider(Protocol):
    model_name: str
    model_revision: str

    def load(self) -> None: ...

    def embed_images(self, image_paths: Sequence[Path]) -> list[list[float]]: ...

    def embed_image(self, image: Path | bytes | Any) -> list[float]: ...

    def embed_text_queries(self, texts: Sequence[str]) -> list[list[float]]: ...

    @property
    def dimension(self) -> int: ...

    def health(self) -> ProviderHealth: ...

    def close(self) -> None: ...


class RerankerProvider(Protocol):
    model_name: str
    model_revision: str

    def load(self) -> None: ...

    def rerank(self, query: str, passages: Sequence[str]) -> list[float]: ...

    def health(self) -> ProviderHealth: ...

    def close(self) -> None: ...


def resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    import torch

    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def _l2_rows(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("模型返回了零向量")
    return values / norms


class LocalBGETextEmbeddingProvider:
    def __init__(
        self,
        *,
        model_name: str,
        revision: str,
        device: str,
        batch_size: int,
        normalize: bool,
        max_length: int,
        cache_dir: Path | None,
        trust_remote_code: bool,
        query_instruction: str = "",
    ) -> None:
        self.model_name = model_name
        self.model_revision = revision
        self.requested_device = device
        self.device = "unresolved"
        self.batch_size = batch_size
        self.normalize = normalize
        self.max_length = max_length
        self.cache_dir = cache_dir
        self.trust_remote_code = trust_remote_code
        self.query_instruction = query_instruction
        self._model: Any = None
        self._dimension: int | None = None
        self._effective_max_length: int | None = None
        self._error: str | None = None
        self._load_latency_ms = 0
        self._load_lock = RLock()

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            started = perf_counter()
            self.load()
            self._load_latency_ms = int((perf_counter() - started) * 1000)

    def load(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            self.device = resolve_device(self.requested_device)
            self._model = SentenceTransformer(
                self.model_name,
                revision=self.model_revision,
                device=self.device,
                cache_folder=str(self.cache_dir) if self.cache_dir else None,
                trust_remote_code=self.trust_remote_code,
            )
            tokenizer_limit = int(
                getattr(self._model.tokenizer, "model_max_length", self.max_length)
            )
            first_module = self._model._first_module()
            config = getattr(getattr(first_module, "auto_model", None), "config", None)
            position_limit = int(
                getattr(config, "max_position_embeddings", self.max_length)
            )
            self._effective_max_length = min(
                self.max_length, tokenizer_limit, position_limit
            )
            self._model.max_seq_length = self._effective_max_length
            dimension_getter = getattr(
                self._model,
                "get_embedding_dimension",
                self._model.get_sentence_embedding_dimension,
            )
            self._dimension = int(dimension_getter())
            commit = getattr(config, "_commit_hash", None)
            if commit:
                self.model_revision = str(commit)
            self._error = None
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"
            self._model = None
            raise

    @staticmethod
    def _validate(texts: Sequence[str]) -> list[str]:
        values = [text.strip() for text in texts]
        if not values or any(not text for text in values):
            raise ValueError("Embedding 输入不得为空")
        return values

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        values = self._validate(texts)
        self._ensure_loaded()
        self._validate_model_lengths(values)
        encode = getattr(self._model, "encode_document", self._model.encode)
        vectors = encode(
            values,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize,
            show_progress_bar=False,
        )
        array = np.asarray(vectors, dtype=np.float32)
        if array.ndim == 1:
            array = array.reshape(1, -1)
        if self.normalize:
            array = _l2_rows(array)
        return array.astype(np.float32, copy=False).tolist()

    def embed_query(self, text: str) -> list[float]:
        values = self._validate([f"{self.query_instruction}{text}"])
        self._ensure_loaded()
        self._validate_model_lengths(values)
        encode = getattr(self._model, "encode_query", self._model.encode)
        vectors = encode(
            values,
            batch_size=1,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize,
            show_progress_bar=False,
        )
        array = np.asarray(vectors, dtype=np.float32).reshape(1, -1)
        if self.normalize:
            array = _l2_rows(array)
        return array[0].tolist()

    def _validate_model_lengths(self, texts: Sequence[str]) -> None:
        if self._effective_max_length is None:
            raise RuntimeError("文本模型最大长度不可用")
        encoded = self._model.tokenizer(
            list(texts),
            add_special_tokens=True,
            truncation=False,
            padding=False,
        )
        lengths = [len(item) for item in encoded["input_ids"]]
        longest = max(lengths, default=0)
        if longest > self._effective_max_length:
            raise ValueError(
                "文本分块超过模型 token 上限："
                f"{longest}>{self._effective_max_length}；请在切块阶段缩短"
            )

    @property
    def dimension(self) -> int:
        self._ensure_loaded()
        if self._dimension is None:
            raise RuntimeError("文本 Embedding 维度不可用")
        return self._dimension

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="ready" if self._model is not None else "not_loaded",
            loaded=self._model is not None,
            model_name=self.model_name,
            model_revision=self.model_revision,
            dimension=self._dimension,
            device=self.device,
            reason=self._error,
            load_latency_ms=self._load_latency_ms,
        )

    def close(self) -> None:
        self._model = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            return


class LocalSigLIP2ImageEmbeddingProvider:
    def __init__(
        self,
        *,
        model_name: str,
        revision: str,
        device: str,
        batch_size: int,
        normalize: bool,
        cache_dir: Path | None,
    ) -> None:
        self.model_name = model_name
        self.model_revision = revision
        self.requested_device = device
        self.device = "unresolved"
        self.batch_size = batch_size
        self.normalize = normalize
        self.cache_dir = cache_dir
        self._model: Any = None
        self._processor: Any = None
        self._dimension: int | None = None
        self._error: str | None = None
        self._load_latency_ms = 0
        self._load_lock = RLock()

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            started = perf_counter()
            self.load()
            self._load_latency_ms = int((perf_counter() - started) * 1000)

    def load(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import AutoModel, AutoProcessor

            self.device = resolve_device(self.requested_device)
            cache = str(self.cache_dir) if self.cache_dir else None
            self._processor = AutoProcessor.from_pretrained(
                self.model_name,
                revision=self.model_revision,
                cache_dir=cache,
            )
            self._model = AutoModel.from_pretrained(
                self.model_name,
                revision=self.model_revision,
                cache_dir=cache,
            ).to(self.device)
            self._model.eval()
            projection = getattr(self._model.config, "projection_dim", None)
            if projection is None:
                vision = getattr(self._model.config, "vision_config", None)
                projection = getattr(vision, "hidden_size", None)
            self._dimension = int(projection) if projection else None
            commit = getattr(self._model.config, "_commit_hash", None)
            if commit:
                self.model_revision = str(commit)
            if self._dimension is None:
                self._dimension = len(self.embed_text_queries(["dimension probe"])[0])
            self._error = None
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"
            self._model = None
            self._processor = None
            raise

    @staticmethod
    def _open_image(value: Path | bytes | Any) -> Any:
        from PIL import Image

        image: Any
        if isinstance(value, Path):
            image = Image.open(value)
        elif isinstance(value, bytes):
            image = Image.open(io.BytesIO(value))
        elif isinstance(value, Image.Image):
            image = value
        else:
            raise TypeError("不支持的图片输入类型")
        image.load()
        return image.convert("RGB")

    def _features(self, inputs: dict[str, Any], method: str) -> list[list[float]]:
        import torch

        moved = {
            key: value.to(self.device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }
        with torch.inference_mode():
            output = getattr(self._model, method)(**moved)
        array = output.detach().cpu().float().numpy().astype(np.float32)
        if array.ndim == 1:
            array = array.reshape(1, -1)
        if self.normalize:
            array = _l2_rows(array)
        return array.tolist()

    def embed_images(self, image_paths: Sequence[Path]) -> list[list[float]]:
        if not image_paths:
            raise ValueError("图片 Embedding 输入不得为空")
        self._ensure_loaded()
        output: list[list[float]] = []
        for start in range(0, len(image_paths), self.batch_size):
            images = [
                self._open_image(path)
                for path in image_paths[start : start + self.batch_size]
            ]
            inputs = self._processor(images=images, return_tensors="pt")
            output.extend(self._features(dict(inputs), "get_image_features"))
        return output

    def embed_image(self, image: Path | bytes | Any) -> list[float]:
        self._ensure_loaded()
        opened = self._open_image(image)
        inputs = self._processor(images=[opened], return_tensors="pt")
        return self._features(dict(inputs), "get_image_features")[0]

    def embed_text_queries(self, texts: Sequence[str]) -> list[list[float]]:
        values = [text.strip() for text in texts]
        if not values or any(not text for text in values):
            raise ValueError("图片文本查询不得为空")
        self._ensure_loaded()
        inputs = self._processor(
            text=values,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return self._features(dict(inputs), "get_text_features")

    @property
    def dimension(self) -> int:
        self._ensure_loaded()
        if self._dimension is None:
            raise RuntimeError("图片 Embedding 维度不可用")
        return self._dimension

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="ready" if self._model is not None else "not_loaded",
            loaded=self._model is not None,
            model_name=self.model_name,
            model_revision=self.model_revision,
            dimension=self._dimension,
            device=self.device,
            reason=self._error,
            load_latency_ms=self._load_latency_ms,
        )

    def close(self) -> None:
        self._model = None
        self._processor = None


class BGERerankerProvider:
    def __init__(
        self,
        *,
        model_name: str,
        revision: str,
        device: str,
        cache_dir: Path | None,
    ) -> None:
        self.model_name = model_name
        self.model_revision = revision
        self.requested_device = device
        self.device = "unresolved"
        self.cache_dir = cache_dir
        self._model: Any = None
        self._error: str | None = None
        self._load_latency_ms = 0
        self._load_lock = RLock()

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            started = perf_counter()
            self.load()
            self._load_latency_ms = int((perf_counter() - started) * 1000)

    def load(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder

            self.device = resolve_device(self.requested_device)
            self._model = CrossEncoder(
                self.model_name,
                revision=self.model_revision,
                device=self.device,
                cache_folder=str(self.cache_dir) if self.cache_dir else None,
            )
            config = getattr(self._model.model, "config", None)
            commit = getattr(config, "_commit_hash", None)
            if commit:
                self.model_revision = str(commit)
            self._error = None
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"
            self._model = None
            raise

    def rerank(self, query: str, passages: Sequence[str]) -> list[float]:
        query = query.strip()
        if not query or not passages:
            raise ValueError("重排查询和候选不得为空")
        self._ensure_loaded()
        scores = self._model.predict(
            [(query, passage) for passage in passages],
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(scores, dtype=np.float32).reshape(-1).tolist()

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="ready" if self._model is not None else "not_loaded",
            loaded=self._model is not None,
            model_name=self.model_name,
            model_revision=self.model_revision,
            dimension=None,
            device=self.device,
            reason=self._error,
            load_latency_ms=self._load_latency_ms,
        )

    def close(self) -> None:
        self._model = None
