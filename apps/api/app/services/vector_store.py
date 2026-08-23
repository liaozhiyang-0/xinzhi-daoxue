from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models


@dataclass(frozen=True, slots=True)
class VectorSearchHit:
    item_id: str
    score: float
    payload: dict[str, Any]


class VectorStoreAdapter(Protocol):
    def ensure_collections(
        self, text_dimension: int, image_dimension: int, *, recreate: bool = False
    ) -> None: ...

    def upsert_text(
        self, records: Sequence[dict[str, Any]], vectors: Sequence[Sequence[float]]
    ) -> None: ...

    def upsert_images(
        self,
        records: Sequence[dict[str, Any]],
        visual_vectors: Sequence[Sequence[float]],
        caption_vectors: Sequence[Sequence[float]],
    ) -> None: ...

    def search_text(
        self,
        vector: Sequence[float],
        *,
        course_id: str,
        limit: int,
        content_types: Sequence[str] = (),
    ) -> list[VectorSearchHit]: ...

    def search_images(
        self,
        vector: Sequence[float],
        *,
        vector_name: str,
        course_id: str,
        limit: int,
    ) -> list[VectorSearchHit]: ...

    def retrieve_text(
        self,
        chunk_ids: Sequence[str],
        *,
        content_types: Sequence[str] = (),
    ) -> list[VectorSearchHit]: ...

    def prune(
        self,
        *,
        text_ids: set[str] | None = None,
        image_ids: set[str] | None = None,
    ) -> dict[str, int]: ...

    def ensure_research_collection(self, dimension: int) -> None: ...

    def research_collection_exists(self) -> bool: ...

    def upsert_research(
        self, records: Sequence[dict[str, Any]], vectors: Sequence[Sequence[float]]
    ) -> None: ...

    def search_research(
        self,
        vector: Sequence[float],
        *,
        limit: int,
        topic: str = "",
    ) -> list[VectorSearchHit]: ...

    def delete_research(self, evidence_ids: Sequence[str]) -> int: ...

    def health(
        self,
        *,
        expected_text_dimension: int | None = None,
        expected_image_dimension: int | None = None,
    ) -> dict[str, Any]: ...

    def metrics(self) -> dict[str, dict[str, Any]]: ...

    def close(self) -> None: ...


def qdrant_point_id(item_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"xinzhi-daoxue:{item_id}"))


def _observe(operation: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(function)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            started = perf_counter()
            error: str | None = None
            try:
                return function(self, *args, **kwargs)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                self._record_operation(operation, perf_counter() - started, error)

        return wrapper

    return decorator


class QdrantVectorStoreAdapter:
    def __init__(
        self,
        *,
        mode: str,
        url: str,
        api_key: str,
        local_path: Path,
        text_collection: str,
        image_collection: str,
        research_collection: str = "xinzhi_research_evidence_v1",
        trust_env: bool = False,
    ) -> None:
        self.mode = mode
        self.url = url
        self.api_key = api_key
        self.local_path = local_path
        self.text_collection = text_collection
        self.image_collection = image_collection
        self.research_collection = research_collection
        self.trust_env = trust_env
        self._client: QdrantClient | None = None
        self._error: str | None = None
        self._operation_metrics: dict[str, dict[str, Any]] = {}

    def __enter__(self) -> QdrantVectorStoreAdapter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            try:
                if self.mode == "local":
                    self.local_path.mkdir(parents=True, exist_ok=True)
                    # qdrant-client performs a SQLite thread-safety probe with
                    # a connection that is not closed on Python 3.13. Local
                    # RAG access already crosses the service's thread boundary,
                    # so use the library's explicit opt-out and avoid that leak.
                    self._client = QdrantClient(
                        path=str(self.local_path),
                        force_disable_check_same_thread=True,
                    )
                else:
                    self._client = QdrantClient(
                        url=self.url,
                        api_key=self.api_key or None,
                        timeout=30,
                        trust_env=self.trust_env,
                    )
                self._error = None
            except Exception as exc:
                self._error = f"{type(exc).__name__}: {exc}"
                raise
        return self._client

    def _exists(self, collection: str) -> bool:
        return self.client.collection_exists(collection)

    @_observe("ensure_collections")
    def ensure_collections(
        self, text_dimension: int, image_dimension: int, *, recreate: bool = False
    ) -> None:
        if recreate:
            for collection in (self.text_collection, self.image_collection):
                if self._exists(collection):
                    self.client.delete_collection(collection)
        if not self._exists(self.text_collection):
            self.client.create_collection(
                collection_name=self.text_collection,
                vectors_config={
                    "text_dense": models.VectorParams(
                        size=text_dimension, distance=models.Distance.COSINE
                    )
                },
            )
        if not self._exists(self.image_collection):
            self.client.create_collection(
                collection_name=self.image_collection,
                vectors_config={
                    "image_visual": models.VectorParams(
                        size=image_dimension, distance=models.Distance.COSINE
                    ),
                    "image_caption_dense": models.VectorParams(
                        size=text_dimension, distance=models.Distance.COSINE
                    ),
                },
            )
        # Embedded Qdrant already evaluates payload filters locally. Creating
        # payload indexes there is a no-op and emits a warning on every index
        # build, while server Qdrant still benefits from explicit indexes.
        if self.mode == "local":
            return
        for collection in (self.text_collection, self.image_collection):
            try:
                self.client.create_payload_index(
                    collection_name=collection,
                    field_name="course_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                    wait=True,
                )
            except (ValueError, NotImplementedError):
                # Embedded Qdrant can filter without an explicit payload index.
                continue

    @_observe("ensure_research_collection")
    def ensure_research_collection(self, dimension: int) -> None:
        """Create the isolated research evidence collection on first ingest."""

        if not self._exists(self.research_collection):
            self.client.create_collection(
                collection_name=self.research_collection,
                vectors_config={
                    "text_dense": models.VectorParams(
                        size=dimension, distance=models.Distance.COSINE
                    )
                },
            )
        if self.mode != "local":
            for field in ("evidence_id", "topic", "status", "source_type"):
                try:
                    self.client.create_payload_index(
                        collection_name=self.research_collection,
                        field_name=field,
                        field_schema=models.PayloadSchemaType.KEYWORD,
                        wait=True,
                    )
                except (ValueError, NotImplementedError):
                    continue

    @_observe("research_collection_exists")
    def research_collection_exists(self) -> bool:
        return self._exists(self.research_collection)

    @_observe("upsert_research")
    def upsert_research(
        self,
        records: Sequence[dict[str, Any]],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        if len(records) != len(vectors):
            raise ValueError("科研证据记录与向量数量不一致")
        points = [
            models.PointStruct(
                id=qdrant_point_id(str(record["evidence_id"])),
                vector={"text_dense": list(vector)},
                payload=dict(record),
            )
            for record, vector in zip(records, vectors, strict=True)
        ]
        if points:
            self.client.upsert(
                collection_name=self.research_collection, points=points, wait=True
            )

    @_observe("search_research")
    def search_research(
        self,
        vector: Sequence[float],
        *,
        limit: int,
        topic: str = "",
    ) -> list[VectorSearchHit]:
        must: list[models.Condition] = [
            models.FieldCondition(
                key="status", match=models.MatchValue(value="active")
            )
        ]
        if topic:
            must.append(
                models.FieldCondition(key="topic", match=models.MatchValue(value=topic))
            )
        response = self.client.query_points(
            collection_name=self.research_collection,
            query=list(vector),
            using="text_dense",
            query_filter=models.Filter(must=must),
            limit=limit,
            with_payload=True,
        )
        return [self._hit(item) for item in response.points]

    @_observe("delete_research")
    def delete_research(self, evidence_ids: Sequence[str]) -> int:
        if not evidence_ids or not self._exists(self.research_collection):
            return 0
        self.client.delete(
            collection_name=self.research_collection,
            points_selector=models.PointIdsList(
                points=[qdrant_point_id(item) for item in evidence_ids]
            ),
            wait=True,
        )
        return len(evidence_ids)

    @_observe("upsert_text")
    def upsert_text(
        self, records: Sequence[dict[str, Any]], vectors: Sequence[Sequence[float]]
    ) -> None:
        if len(records) != len(vectors):
            raise ValueError("文本记录与向量数量不一致")
        points = [
            models.PointStruct(
                id=qdrant_point_id(str(record["chunk_id"])),
                vector={"text_dense": list(vector)},
                payload=dict(record),
            )
            for record, vector in zip(records, vectors, strict=True)
        ]
        if points:
            self.client.upsert(
                collection_name=self.text_collection, points=points, wait=True
            )

    @_observe("upsert_images")
    def upsert_images(
        self,
        records: Sequence[dict[str, Any]],
        visual_vectors: Sequence[Sequence[float]],
        caption_vectors: Sequence[Sequence[float]],
    ) -> None:
        if not (len(records) == len(visual_vectors) == len(caption_vectors)):
            raise ValueError("图片记录与向量数量不一致")
        points = [
            models.PointStruct(
                id=qdrant_point_id(str(record["image_id"])),
                vector={
                    "image_visual": list(visual),
                    "image_caption_dense": list(caption),
                },
                payload=dict(record),
            )
            for record, visual, caption in zip(
                records, visual_vectors, caption_vectors, strict=True
            )
        ]
        if points:
            self.client.upsert(
                collection_name=self.image_collection, points=points, wait=True
            )

    @staticmethod
    def _filter(course_id: str, content_types: Sequence[str] = ()) -> models.Filter:
        conditions: list[models.Condition] = [
            models.FieldCondition(
                key="course_id", match=models.MatchValue(value=course_id)
            )
        ]
        if content_types:
            conditions.append(
                models.FieldCondition(
                    key="content_type",
                    match=models.MatchAny(any=list(content_types)),
                )
            )
        return models.Filter(must=conditions)

    @_observe("search_text")
    def search_text(
        self,
        vector: Sequence[float],
        *,
        course_id: str,
        limit: int,
        content_types: Sequence[str] = (),
    ) -> list[VectorSearchHit]:
        response = self.client.query_points(
            collection_name=self.text_collection,
            query=list(vector),
            using="text_dense",
            query_filter=self._filter(course_id, content_types),
            limit=limit,
            with_payload=True,
        )
        return [self._hit(item) for item in response.points]

    @_observe("search_images")
    def search_images(
        self,
        vector: Sequence[float],
        *,
        vector_name: str,
        course_id: str,
        limit: int,
    ) -> list[VectorSearchHit]:
        if vector_name not in {"image_visual", "image_caption_dense"}:
            raise ValueError("未知图片向量字段")
        response = self.client.query_points(
            collection_name=self.image_collection,
            query=list(vector),
            using=vector_name,
            query_filter=self._filter(course_id),
            limit=limit,
            with_payload=True,
        )
        return [self._hit(item) for item in response.points]

    @_observe("retrieve_text")
    def retrieve_text(
        self,
        chunk_ids: Sequence[str],
        *,
        content_types: Sequence[str] = (),
    ) -> list[VectorSearchHit]:
        if not chunk_ids:
            return []
        records = self.client.retrieve(
            collection_name=self.text_collection,
            ids=[qdrant_point_id(item) for item in chunk_ids],
            with_payload=True,
            with_vectors=False,
        )
        output: list[VectorSearchHit] = []
        allowed = set(content_types)
        for item in records:
            payload = dict(item.payload or {})
            if allowed and str(payload.get("content_type", "")) not in allowed:
                continue
            output.append(
                VectorSearchHit(
                    item_id=str(payload.get("chunk_id") or item.id),
                    score=0.0,
                    payload=payload,
                )
            )
        return output

    @_observe("prune")
    def prune(
        self,
        *,
        text_ids: set[str] | None = None,
        image_ids: set[str] | None = None,
    ) -> dict[str, int]:
        return {
            "text_deleted": (
                self._prune_collection(self.text_collection, "chunk_id", text_ids)
                if text_ids is not None
                else 0
            ),
            "image_deleted": (
                self._prune_collection(self.image_collection, "image_id", image_ids)
                if image_ids is not None
                else 0
            ),
        }

    def _prune_collection(
        self, collection: str, payload_key: str, active_ids: set[str]
    ) -> int:
        if not self._exists(collection):
            return 0
        offset: Any = None
        stale: list[Any] = []
        while True:
            records, offset = self.client.scroll(
                collection_name=collection,
                limit=256,
                offset=offset,
                with_payload=[payload_key],
                with_vectors=False,
            )
            stale.extend(
                item.id
                for item in records
                if str((item.payload or {}).get(payload_key, "")) not in active_ids
            )
            if offset is None:
                break
        if stale:
            self.client.delete(
                collection_name=collection,
                points_selector=models.PointIdsList(points=stale),
                wait=True,
            )
        return len(stale)

    @staticmethod
    def _hit(item: Any) -> VectorSearchHit:
        payload = dict(item.payload or {})
        item_id = str(payload.get("chunk_id") or payload.get("image_id") or item.id)
        return VectorSearchHit(
            item_id=item_id, score=float(item.score), payload=payload
        )

    def _record_operation(
        self, operation: str, elapsed_seconds: float, error: str | None
    ) -> None:
        metrics = self._operation_metrics.setdefault(
            operation,
            {
                "count": 0,
                "error_count": 0,
                "total_latency_ms": 0.0,
                "last_latency_ms": 0.0,
                "last_error": None,
            },
        )
        metrics["count"] += 1
        metrics["error_count"] += int(error is not None)
        metrics["total_latency_ms"] += elapsed_seconds * 1000
        metrics["last_latency_ms"] = round(elapsed_seconds * 1000, 3)
        metrics["last_error"] = error

    def metrics(self) -> dict[str, dict[str, Any]]:
        return {
            operation: dict(values)
            for operation, values in self._operation_metrics.items()
        }

    def _collection_dimensions(self, collection: str) -> dict[str, int]:
        """Read named-vector dimensions without mutating an existing collection."""

        if not self._exists(collection):
            return {}
        info = self.client.get_collection(collection)
        vectors = getattr(getattr(info, "config", None), "params", None)
        vectors = getattr(vectors, "vectors", None)
        if isinstance(vectors, dict):
            return {
                str(name): int(params.size)
                for name, params in vectors.items()
                if params.size is not None
            }
        size = getattr(vectors, "size", None)
        return {"default": int(size)} if size is not None else {}

    @_observe("health")
    def health(
        self,
        *,
        expected_text_dimension: int | None = None,
        expected_image_dimension: int | None = None,
    ) -> dict[str, Any]:
        try:
            text_count = (
                self.client.count(self.text_collection, exact=True).count
                if self._exists(self.text_collection)
                else 0
            )
            image_count = (
                self.client.count(self.image_collection, exact=True).count
                if self._exists(self.image_collection)
                else 0
            )
            collection_dimensions = {
                self.text_collection: self._collection_dimensions(
                    self.text_collection
                ),
                self.image_collection: self._collection_dimensions(
                    self.image_collection
                ),
            }
            dimension_mismatches: list[dict[str, Any]] = []
            expected_vectors = {
                f"{self.text_collection}:text_dense": expected_text_dimension,
                f"{self.image_collection}:image_visual": expected_image_dimension,
                f"{self.image_collection}:image_caption_dense": expected_text_dimension,
            }
            for key, expected in expected_vectors.items():
                if expected is None:
                    continue
                collection, vector_name = key.split(":", 1)
                actual = collection_dimensions[collection].get(vector_name)
                if actual is not None and actual != expected:
                    dimension_mismatches.append(
                        {
                            "collection": collection,
                            "vector_name": vector_name,
                            "expected": expected,
                            "actual": actual,
                        }
                    )
            reason = None
            if dimension_mismatches:
                reason = "vector_dimension_mismatch"
            return {
                "status": "ready" if not dimension_mismatches else "degraded",
                "connected": True,
                "compatible": not dimension_mismatches,
                "mode": self.mode,
                "text_collection": self.text_collection,
                "image_collection": self.image_collection,
                "research_collection": self.research_collection,
                "text_vector_count": int(text_count),
                "image_vector_count": int(image_count),
                "collection_dimensions": collection_dimensions,
                "dimension_mismatches": dimension_mismatches,
                "reason": reason,
                "backend": "embedded_sqlite" if self.mode == "local" else "remote_http",
                "metrics": self.metrics(),
            }
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"
            return {
                "status": "failed",
                "connected": False,
                "compatible": False,
                "mode": self.mode,
                "text_collection": self.text_collection,
                "image_collection": self.image_collection,
                "research_collection": self.research_collection,
                "text_vector_count": 0,
                "image_vector_count": 0,
                "collection_dimensions": {},
                "dimension_mismatches": [],
                "reason": self._error,
                "backend": "embedded_sqlite" if self.mode == "local" else "remote_http",
                "metrics": self.metrics(),
            }

    def close(self) -> None:
        if self._client is not None:
            client, self._client = self._client, None
            client.close()
