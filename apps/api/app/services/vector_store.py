from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
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

    def retrieve_text(self, chunk_ids: Sequence[str]) -> list[VectorSearchHit]: ...

    def prune(self, *, text_ids: set[str], image_ids: set[str]) -> dict[str, int]: ...

    def health(self) -> dict[str, Any]: ...

    def close(self) -> None: ...


def qdrant_point_id(item_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"xinzhi-daoxue:{item_id}"))


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
    ) -> None:
        self.mode = mode
        self.url = url
        self.api_key = api_key
        self.local_path = local_path
        self.text_collection = text_collection
        self.image_collection = image_collection
        self._client: QdrantClient | None = None
        self._error: str | None = None

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            try:
                if self.mode == "local":
                    self.local_path.mkdir(parents=True, exist_ok=True)
                    self._client = QdrantClient(path=str(self.local_path))
                else:
                    self._client = QdrantClient(
                        url=self.url,
                        api_key=self.api_key or None,
                        timeout=30,
                    )
                self._error = None
            except Exception as exc:
                self._error = f"{type(exc).__name__}: {exc}"
                raise
        return self._client

    def _exists(self, collection: str) -> bool:
        return self.client.collection_exists(collection)

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

    def retrieve_text(self, chunk_ids: Sequence[str]) -> list[VectorSearchHit]:
        if not chunk_ids:
            return []
        records = self.client.retrieve(
            collection_name=self.text_collection,
            ids=[qdrant_point_id(item) for item in chunk_ids],
            with_payload=True,
            with_vectors=False,
        )
        output: list[VectorSearchHit] = []
        for item in records:
            payload = dict(item.payload or {})
            output.append(
                VectorSearchHit(
                    item_id=str(payload.get("chunk_id") or item.id),
                    score=0.0,
                    payload=payload,
                )
            )
        return output

    def prune(self, *, text_ids: set[str], image_ids: set[str]) -> dict[str, int]:
        return {
            "text_deleted": self._prune_collection(
                self.text_collection, "chunk_id", text_ids
            ),
            "image_deleted": self._prune_collection(
                self.image_collection, "image_id", image_ids
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

    def health(self) -> dict[str, Any]:
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
            return {
                "status": "ready",
                "connected": True,
                "mode": self.mode,
                "text_collection": self.text_collection,
                "image_collection": self.image_collection,
                "text_vector_count": int(text_count),
                "image_vector_count": int(image_count),
                "reason": None,
            }
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"
            return {
                "status": "failed",
                "connected": False,
                "mode": self.mode,
                "text_collection": self.text_collection,
                "image_collection": self.image_collection,
                "text_vector_count": 0,
                "image_vector_count": 0,
                "reason": self._error,
            }

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
