from __future__ import annotations

import hashlib
import logging
import math
from collections import OrderedDict, defaultdict
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import BoundedSemaphore, RLock
from time import monotonic, perf_counter
from typing import Any
from uuid import uuid4

from app.contracts import KnowledgeHit, RelatedImage, RetrievalResult
from app.contracts.knowledge import KnowledgeCourseId
from app.core.config import Settings
from app.knowledge_catalog import KNOWLEDGE_COURSE_NAMES
from app.services.knowledge_base import KnowledgeBaseService, tokenize
from app.services.query_rewrite import rewrite_retrieval_query
from app.services.rag_providers import (
    ImageEmbeddingProvider,
    RerankerProvider,
    TextEmbeddingProvider,
)
from app.services.vector_store import VectorSearchHit, VectorStoreAdapter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RetrievalPolicy:
    name: str
    text_top_k: int
    image_top_k: int
    content_types: tuple[str, ...]
    include_images: bool
    allow_generation_injection: bool


def policy_for(
    *,
    agent_id: str,
    intent: str,
    configured_top_k: int,
    content_types: tuple[str, ...],
    policy_name: str | None = None,
    configured_image_top_k: int | None = None,
    allow_generation_injection: bool | None = None,
) -> RetrievalPolicy:
    if policy_name is not None:
        return RetrievalPolicy(
            name=policy_name,
            text_top_k=configured_top_k,
            image_top_k=max(0, configured_image_top_k or 0),
            content_types=tuple(content_types),
            include_images=bool(configured_image_top_k),
            allow_generation_injection=bool(allow_generation_injection),
        )
    if agent_id == "SOLVER_CT_V1":
        return RetrievalPolicy(
            name="solver_method_reference",
            text_top_k=min(2, configured_top_k),
            image_top_k=2,
            content_types=("method", "formula", "concept", "common_error"),
            include_images=True,
            allow_generation_injection=False,
        )
    defaults = {
        "explain_concept": (
            "learn_explain_concept",
            3,
            2,
            ("concept", "formula", "method", "chapter_summary", "mixed", "unknown"),
        ),
        "follow_up_question": (
            "learn_follow_up",
            3,
            1,
            ("concept", "formula", "method", "mixed", "unknown"),
        ),
        "summarize_knowledge": (
            "learn_summarize",
            5,
            2,
            ("chapter_summary", "concept", "method", "mixed", "unknown"),
        ),
        "learning_advice": (
            "learn_advice",
            4,
            0,
            ("chapter_summary", "common_error", "method", "mixed", "unknown"),
        ),
        "check_simple_step": (
            "learn_check_step",
            3,
            1,
            ("formula", "method", "common_error", "mixed", "unknown"),
        ),
    }
    name, intent_top_k, image_top_k, intent_types = defaults.get(
        intent,
        ("learn_general_qa", configured_top_k, 0, ()),
    )
    selected = tuple(content_types) or intent_types
    return RetrievalPolicy(
        name=name,
        text_top_k=min(configured_top_k, intent_top_k),
        image_top_k=image_top_k,
        content_types=selected,
        include_images=True,
        allow_generation_injection=True,
    )


@dataclass(slots=True)
class _Candidate:
    hit: KnowledgeHit
    ranks: dict[str, int]
    fusion_score: float = 0.0
    topic_bonus: float = 0.0
    rerank_score: float | None = None


class RAGRetrievalService:
    def __init__(
        self,
        settings: Settings,
        lexical: KnowledgeBaseService,
        text_provider: TextEmbeddingProvider,
        image_provider: ImageEmbeddingProvider,
        reranker: RerankerProvider,
        vector_store: VectorStoreAdapter,
    ) -> None:
        self.settings = settings
        self.lexical = lexical
        self.text_provider = text_provider
        self.image_provider = image_provider
        self.reranker = reranker
        self.vector_store = vector_store
        self._metrics: defaultdict[str, int] = defaultdict(int)
        self._query_cache: OrderedDict[tuple[str, ...], list[float]] = OrderedDict()
        self._result_cache: OrderedDict[
            tuple[str, ...], tuple[float, RetrievalResult]
        ] = OrderedDict()
        self._executor = ThreadPoolExecutor(
            max_workers=settings.rag_retrieval_worker_count,
            thread_name_prefix="xzd-rag-channel",
        )
        self._text_semaphore = BoundedSemaphore(
            settings.text_embedding_concurrency_limit
        )
        self._image_semaphore = BoundedSemaphore(
            settings.image_embedding_concurrency_limit
        )
        self._reranker_semaphore = BoundedSemaphore(settings.reranker_concurrency_limit)
        self._cache_lock = RLock()

    def search(
        self,
        *,
        query_text: str = "",
        query_image: Path | bytes | Any | None = None,
        course_id: str,
        intent: str = "general_qa",
        target_agent_id: str = "LEARN_01_KNOWLEDGE_QA_V1",
        top_k: int | None = None,
        content_types: tuple[str, ...] = (),
        include_images: bool = True,
        session_context: str = "",
        use_reranker: bool | str | None = None,
        policy_name: str | None = None,
        image_top_k: int | None = None,
        allow_generation_injection: bool | None = None,
        local_budget_ms: int | None = None,
    ) -> RetrievalResult:
        started = perf_counter()
        trace_id = f"rag_{uuid4().hex}"
        normalized, rewrite_rules = rewrite_retrieval_query(
            query_text,
            course_id=course_id,
            conversation_summary=session_context,
        )
        modalities = ["text"] if normalized else []
        if query_image is not None:
            modalities.append("image")
        if not modalities:
            raise ValueError("RAG 查询必须包含文字或图片")
        if not self.settings.rag_enabled:
            if not normalized:
                raise RuntimeError("RAG 已禁用，无法执行纯图片检索")
            sparse = self.lexical.search_result(normalized, [course_id], top_k)
            return sparse.model_copy(
                update={
                    "rag_status": "disabled",
                    "embedding_status": "disabled",
                    "vector_store_status": "disabled",
                    "reranker_status": "disabled",
                    "query_modalities": modalities,
                    "retrieval_trace_id": trace_id,
                    "latency_ms": int((perf_counter() - started) * 1000),
                }
            )
        policy = policy_for(
            agent_id=target_agent_id,
            intent=intent,
            configured_top_k=top_k or self.settings.rag_final_text_k,
            content_types=content_types,
            policy_name=policy_name,
            configured_image_top_k=image_top_k,
            allow_generation_injection=allow_generation_injection,
        )
        include_images = include_images and policy.include_images
        reranker_request: bool | str = (
            self.settings.rag_default_use_reranker
            if use_reranker is None
            else use_reranker
        )
        image_cold_skipped = bool(
            include_images
            and query_image is None
            and local_budget_ms is not None
            and local_budget_ms <= self.settings.retrieval_p95_target_ms
            and not self.image_provider.health().loaded
        )
        if image_cold_skipped:
            include_images = False
        cache_key = self._result_cache_key(
            query=normalized,
            query_image=query_image,
            course_id=course_id,
            intent=intent,
            policy=policy,
            include_images=include_images,
            use_reranker=reranker_request,
            index_version=self._index_version(),
        )
        cached = self._result_cache_get(cache_key)
        if cached is not None:
            cached_trace = dict(cached.trace)
            cached_trace.update(
                {"cache_hit": True, "query_rewrite_rules": rewrite_rules}
            )
            self._metrics["rag_result_cache_hit_total"] += 1
            return cached.model_copy(
                update={
                    "query": query_text,
                    "normalized_query": normalized,
                    "retrieval_trace_id": trace_id,
                    "latency_ms": int((perf_counter() - started) * 1000),
                    "trace": cached_trace,
                },
                deep=True,
            )
        warnings: list[str] = []
        if image_cold_skipped:
            warnings.append("optional_image_skipped:cold_model_local_budget")
        candidates: dict[str, _Candidate] = {}
        image_channels: dict[str, dict[str, Any]] = {}
        trace: dict[str, Any] = {
            "target_agent_id": target_agent_id,
            "policy_name": policy.name,
            "cache_hit": False,
            "query_rewrite_rules": rewrite_rules,
            "course_id": course_id,
            "query_modalities": modalities,
            "dense_candidates": 0,
            "sparse_candidates": 0,
            "image_candidates": 0,
            "fusion_candidates": 0,
            "reranked_candidates": 0,
        }
        dense_ok = False
        vector_ok = False
        image_ok = not include_images
        optional_degraded = image_cold_skipped
        index_version = self._index_version()

        sparse_future: Future[list[KnowledgeHit]] | None = None
        if normalized:
            sparse_future = self._executor.submit(
                self._sparse_search,
                normalized,
                course_id,
                policy.content_types,
            )

        dense_hits: list[VectorSearchHit] = []
        try:
            health = self.vector_store.health()
            vector_ok = bool(health.get("connected"))
            if not vector_ok:
                raise RuntimeError(str(health.get("reason") or "Qdrant unavailable"))
            if normalized:
                dense_vector = self._cached_text_query(normalized)
                dense_hits = self.vector_store.search_text(
                    dense_vector,
                    course_id=course_id,
                    limit=self.settings.rag_dense_candidate_k,
                    content_types=policy.content_types,
                )
                dense_ok = True
                trace["dense_candidates"] = len(dense_hits)
                self._add_dense(candidates, dense_hits, "dense")
                trace["dense"] = [
                    self._vector_summary(item, "dense") for item in dense_hits[:10]
                ]
                if include_images:
                    elapsed = int((perf_counter() - started) * 1000)
                    if local_budget_ms is not None and elapsed >= local_budget_ms:
                        include_images = False
                        image_ok = True
                        optional_degraded = True
                        warnings.append("optional_image_skipped:local_budget")
                    else:
                        text_visual = self._cached_image_text_query(normalized)
                        text_image_hits = self.vector_store.search_images(
                            text_visual,
                            vector_name="image_visual",
                            course_id=course_id,
                            limit=self.settings.rag_image_candidate_k,
                        )
                        image_ok = True
                        self._add_images(image_channels, text_image_hits, "text_visual")
            if query_image is not None:
                visual_vector = self._cached_image_query(query_image)
                visual_hits = self.vector_store.search_images(
                    visual_vector,
                    vector_name="image_visual",
                    course_id=course_id,
                    limit=self.settings.rag_image_candidate_k,
                )
                image_ok = True
                self._add_images(image_channels, visual_hits, "image_visual")
                if not normalized and visual_hits:
                    normalized = " ".join(
                        str(item.payload.get("caption", "")) for item in visual_hits[:3]
                    ).strip()[: self.settings.knowledge_chunk_size_chars]
                    if normalized:
                        dense_vector = self._cached_text_query(normalized)
                        dense_hits = self.vector_store.search_text(
                            dense_vector,
                            course_id=course_id,
                            limit=self.settings.rag_dense_candidate_k,
                            content_types=policy.content_types,
                        )
                        dense_ok = True
                        self._add_dense(candidates, dense_hits, "image_caption_dense")
            parent_ids = [
                str(item["payload"].get("parent_chunk_id"))
                for item in image_channels.values()
                if item["payload"].get("parent_chunk_id")
            ]
            self._add_dense(
                candidates,
                self.vector_store.retrieve_text(parent_ids),
                "visual_parent",
            )
        except Exception as exc:
            warnings.append(f"dense_or_visual_degraded:{type(exc).__name__}")
            logger.warning(
                "rag_retrieval_degraded trace_id=%s course_id=%s error=%s",
                trace_id,
                course_id,
                type(exc).__name__,
            )

        sparse_hits: list[KnowledgeHit] = []
        if sparse_future is not None:
            try:
                sparse_hits = sparse_future.result()
            except Exception as exc:
                warnings.append(f"sparse_degraded:{type(exc).__name__}")
            trace["sparse_candidates"] = len(sparse_hits)
            self._add_sparse(candidates, sparse_hits)
            trace["bm25"] = [self._hit_summary(hit) for hit in sparse_hits[:10]]

        self._rrf(candidates, normalized)
        trace["fusion_candidates"] = len(candidates)
        ordered = sorted(candidates.values(), key=lambda item: -item.fusion_score)
        trace["fusion"] = [self._candidate_summary(item) for item in ordered[:10]]
        reranker_status = "disabled"
        should_rerank = reranker_request is True or reranker_request == "on"
        if reranker_request == "conditional":
            should_rerank = self._should_conditionally_rerank(
                ordered,
                intent=intent,
            )
            reranker_status = "conditional_selected" if should_rerank else "skipped"
        elapsed_before_rerank = int((perf_counter() - started) * 1000)
        if (
            should_rerank
            and local_budget_ms is not None
            and elapsed_before_rerank >= local_budget_ms
        ):
            should_rerank = False
            optional_degraded = True
            reranker_status = "skipped"
            warnings.append("optional_reranker_skipped:local_budget")
        trace["reranker_decision"] = {
            "requested": str(reranker_request).lower(),
            "executed": should_rerank,
        }
        if self.settings.reranker_enabled and should_rerank and normalized and ordered:
            try:
                rerank_items = ordered[: self.settings.reranker_top_n]
                with self._reranker_semaphore:
                    scores = self.reranker.rerank(
                        normalized, [item.hit.content for item in rerank_items]
                    )
                for item, score in zip(rerank_items, scores, strict=True):
                    item.rerank_score = float(score)
                ordered.sort(key=self._final_score, reverse=True)
                reranker_status = "ready"
                trace["reranked_candidates"] = len(rerank_items)
                trace["rerank"] = [
                    self._candidate_summary(item) for item in ordered[:10]
                ]
            except Exception as exc:
                reranker_status = "failed"
                warnings.append(f"reranker_degraded:{type(exc).__name__}")
        final_hits = [self._finalize(item) for item in ordered[: policy.text_top_k]]
        final_images = self._final_images(
            image_channels,
            limit=min(policy.image_top_k, self.settings.rag_final_image_k),
        )
        trace["image_candidates"] = len(image_channels)
        trace["final_text_evidence"] = len(final_hits)
        trace["final_images"] = len(final_images)
        trace["images"] = [item.model_dump(mode="json") for item in final_images]
        trace["final"] = [item.model_dump(mode="json") for item in final_hits]
        confidence = self._confidence(final_hits)
        rag_status = "ready" if dense_ok and vector_ok and image_ok else "degraded"
        if optional_degraded:
            rag_status = "degraded"
        if not final_hits and not final_images:
            rag_status = "failed" if not sparse_hits else "degraded"
        self._metrics["rag_request_total"] += 1
        self._metrics[f"rag_{rag_status}_total"] += 1
        if not final_hits:
            self._metrics["empty_retrieval_total"] += 1
        latency = int((perf_counter() - started) * 1000)
        logger.info(
            "rag_retrieval trace_id=%s agent=%s course=%s modalities=%s "
            "dense=%s sparse=%s images=%s fusion=%s reranked=%s final=%s "
            "status=%s latency_ms=%s",
            trace_id,
            target_agent_id,
            course_id,
            ",".join(modalities),
            trace["dense_candidates"],
            trace["sparse_candidates"],
            trace["image_candidates"],
            trace["fusion_candidates"],
            trace["reranked_candidates"],
            len(final_hits),
            rag_status,
            latency,
        )
        result = RetrievalResult(
            query=query_text,
            normalized_query=normalized,
            course_ids=[course_id],
            hits=final_hits,
            confidence=confidence,
            retrieval_mode="multimodal_hybrid_rrf_v2",
            warnings=warnings,
            latency_ms=latency,
            image_hits=final_images,
            rag_status=rag_status,
            embedding_status="ready" if dense_ok else "failed",
            vector_store_status="ready" if vector_ok else "failed",
            reranker_status=reranker_status,
            query_modalities=modalities,
            retrieval_trace_id=trace_id,
            index_version=index_version,
            trace=trace,
        )
        if not optional_degraded:
            self._result_cache_put(cache_key, result)
        return result

    def health(self) -> dict[str, Any]:
        if not self.settings.rag_enabled:
            return {
                "rag_status": "disabled",
                "text_model_loaded": False,
                "text_model_name": self.settings.text_embedding_model,
                "text_model_revision": self.settings.text_embedding_revision,
                "text_dimension": 0,
                "text_model_load_latency_ms": 0,
                "image_model_loaded": False,
                "image_model_name": self.settings.image_embedding_model,
                "image_model_revision": self.settings.image_embedding_revision,
                "image_dimension": 0,
                "image_model_load_latency_ms": 0,
                "reranker_loaded": False,
                "reranker_model": self.settings.reranker_model,
                "reranker_load_latency_ms": 0,
                "vector_store_connected": False,
                "text_vector_count": 0,
                "image_vector_count": 0,
                "index_version": self._index_version(),
                "degraded_reasons": ["rag_disabled"],
                "metrics": dict(self._metrics),
            }
        vector = self.vector_store.health()
        text = self.text_provider.health().to_dict()
        image = self.image_provider.health().to_dict()
        reranker = self.reranker.health().to_dict()
        reasons = [
            str(item.get("reason"))
            for item in (vector, text, image, reranker)
            if item.get("reason")
        ]
        return {
            "rag_status": "ready" if vector.get("connected") else "degraded",
            "text_model_loaded": text["loaded"],
            "text_model_name": text["model_name"],
            "text_model_revision": text["model_revision"],
            "text_dimension": text["dimension"],
            "text_model_load_latency_ms": text["load_latency_ms"],
            "image_model_loaded": image["loaded"],
            "image_model_name": image["model_name"],
            "image_model_revision": image["model_revision"],
            "image_dimension": image["dimension"],
            "image_model_load_latency_ms": image["load_latency_ms"],
            "reranker_loaded": reranker["loaded"],
            "reranker_model": reranker["model_name"],
            "reranker_load_latency_ms": reranker["load_latency_ms"],
            "vector_store_connected": vector.get("connected", False),
            "text_vector_count": vector.get("text_vector_count", 0),
            "image_vector_count": vector.get("image_vector_count", 0),
            "index_version": self._index_version(),
            "degraded_reasons": reasons,
            "metrics": dict(self._metrics),
        }

    def close(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)
        self.text_provider.close()
        self.image_provider.close()
        self.reranker.close()
        self.vector_store.close()

    def _index_version(self) -> str:
        state = self.settings.knowledge_index_path / "rag_index_state.json"
        try:
            payload = __import__("json").loads(state.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ""
        return str(payload.get("index_version", ""))

    def _cache_get(self, key: tuple[str, ...]) -> list[float] | None:
        with self._cache_lock:
            value = self._query_cache.get(key)
            if value is not None:
                self._query_cache.move_to_end(key)
                return list(value)
        return None

    def _cache_put(self, key: tuple[str, ...], value: list[float]) -> list[float]:
        if self.settings.rag_query_cache_size <= 0:
            return value
        with self._cache_lock:
            self._query_cache[key] = list(value)
            self._query_cache.move_to_end(key)
            while len(self._query_cache) > self.settings.rag_query_cache_size:
                self._query_cache.popitem(last=False)
        return value

    def _result_cache_key(
        self,
        *,
        query: str,
        query_image: Path | bytes | Any | None,
        course_id: str,
        intent: str,
        policy: RetrievalPolicy,
        include_images: bool,
        use_reranker: bool | str,
        index_version: str,
    ) -> tuple[str, ...]:
        image_digest = ""
        if isinstance(query_image, Path):
            image_digest = hashlib.sha256(query_image.read_bytes()).hexdigest()
        elif isinstance(query_image, bytes):
            image_digest = hashlib.sha256(query_image).hexdigest()
        elif query_image is not None:
            image_digest = f"object:{id(query_image)}"
        return (
            course_id,
            intent,
            policy.name,
            index_version,
            self.text_provider.model_name,
            self.text_provider.model_revision,
            self.image_provider.model_name if include_images else "no-image",
            self.reranker.model_name if use_reranker else "no-reranker",
            str(include_images),
            str(use_reranker),
            query,
            image_digest,
        )

    def _result_cache_get(self, key: tuple[str, ...]) -> RetrievalResult | None:
        item = self._result_cache.get(key)
        if item is None:
            return None
        created, result = item
        if monotonic() - created > self.settings.rag_result_cache_ttl_seconds:
            self._result_cache.pop(key, None)
            return None
        self._result_cache.move_to_end(key)
        return result.model_copy(deep=True)

    def _result_cache_put(self, key: tuple[str, ...], result: RetrievalResult) -> None:
        if self.settings.rag_result_cache_size <= 0:
            return
        self._result_cache[key] = (monotonic(), result.model_copy(deep=True))
        self._result_cache.move_to_end(key)
        while len(self._result_cache) > self.settings.rag_result_cache_size:
            self._result_cache.popitem(last=False)

    @staticmethod
    def _hit_summary(hit: KnowledgeHit) -> dict[str, Any]:
        return {
            "title": hit.title,
            "chapter": hit.chapter,
            "course_id": hit.course_id.value,
            "content_type": hit.content_type,
            "source_uri": hit.source_ref,
            "score": hit.score,
            "text_preview": hit.content[:240],
        }

    @classmethod
    def _vector_summary(cls, item: VectorSearchHit, channel: str) -> dict[str, Any]:
        hit = cls._payload_hit(item.payload, item.score)
        payload = cls._hit_summary(hit)
        payload.update({"channel": channel, "score": item.score})
        return payload

    @classmethod
    def _candidate_summary(cls, item: _Candidate) -> dict[str, Any]:
        payload = cls._hit_summary(item.hit)
        payload.update(
            {
                "retrieval_channels": sorted(item.ranks),
                "ranks": item.ranks,
                "fusion_score": item.fusion_score,
                "topic_bonus": item.topic_bonus,
                "rerank_score": item.rerank_score,
                "final_score": cls._final_score_static(item),
            }
        )
        return payload

    @staticmethod
    def _final_score_static(candidate: _Candidate) -> float:
        if candidate.rerank_score is None:
            return candidate.fusion_score
        return candidate.rerank_score

    def _cached_text_query(self, text: str) -> list[float]:
        key = (
            "text",
            self.text_provider.model_name,
            self.text_provider.model_revision,
            str(self.settings.text_embedding_normalize),
            text,
        )
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        with self._text_semaphore:
            return self._cache_put(key, self.text_provider.embed_query(text))

    def _cached_image_text_query(self, text: str) -> list[float]:
        key = (
            "image_text",
            self.image_provider.model_name,
            self.image_provider.model_revision,
            str(self.settings.image_embedding_normalize),
            text,
        )
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        with self._image_semaphore:
            return self._cache_put(
                key, self.image_provider.embed_text_queries([text])[0]
            )

    def _cached_image_query(self, image: Path | bytes | Any) -> list[float]:
        if isinstance(image, Path):
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
        elif isinstance(image, bytes):
            digest = hashlib.sha256(image).hexdigest()
        else:
            digest = f"object:{id(image)}"
        key = (
            "image",
            self.image_provider.model_name,
            self.image_provider.model_revision,
            str(self.settings.image_embedding_normalize),
            digest,
        )
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        with self._image_semaphore:
            return self._cache_put(key, self.image_provider.embed_image(image))

    def _sparse_search(
        self, query: str, course_id: str, content_types: tuple[str, ...]
    ) -> list[KnowledgeHit]:
        sparse = self.lexical.search_result(
            query,
            [course_id],
            self.settings.rag_sparse_candidate_k,
        )
        return [
            hit
            for hit in sparse.hits
            if not content_types or hit.content_type in content_types
        ]

    @staticmethod
    def _add_sparse(
        candidates: dict[str, _Candidate], hits: list[KnowledgeHit]
    ) -> None:
        for rank, hit in enumerate(hits, start=1):
            candidate = candidates.setdefault(hit.chunk_id, _Candidate(hit, {}))
            candidate.ranks["sparse"] = rank

    def _should_conditionally_rerank(
        self, ordered: list[_Candidate], *, intent: str
    ) -> bool:
        if intent == "summarize_knowledge":
            return True
        if len(ordered) < 2:
            return False
        score_gap = ordered[0].fusion_score - ordered[1].fusion_score
        conflicting_channels = not (set(ordered[0].ranks) & set(ordered[1].ranks))
        return (
            score_gap <= self.settings.reranker_conditional_score_gap
            or conflicting_channels
        )

    @classmethod
    def _add_dense(
        cls,
        candidates: dict[str, _Candidate],
        hits: list[VectorSearchHit],
        channel: str,
    ) -> None:
        for rank, item in enumerate(hits, start=1):
            if not item.payload:
                continue
            hit = cls._payload_hit(item.payload, item.score)
            candidate = candidates.setdefault(hit.chunk_id, _Candidate(hit, {}))
            candidate.ranks[channel] = rank

    @staticmethod
    def _add_images(
        output: dict[str, dict[str, Any]],
        hits: list[VectorSearchHit],
        channel: str,
    ) -> None:
        for rank, hit in enumerate(hits, start=1):
            record = output.setdefault(
                hit.item_id,
                {"payload": hit.payload, "ranks": {}, "scores": {}},
            )
            record["ranks"][channel] = rank
            record["scores"][channel] = hit.score

    def _rrf(self, candidates: dict[str, _Candidate], query: str) -> None:
        query_tokens = set(tokenize(query))
        for candidate in candidates.values():
            candidate.fusion_score = sum(
                1.0 / (self.settings.rag_rrf_k + rank)
                for rank in candidate.ranks.values()
            )
            if query_tokens:
                title_tokens = set(tokenize(candidate.hit.title))
                content_tokens = set(tokenize(candidate.hit.content))
                title_overlap = len(query_tokens & title_tokens) / len(query_tokens)
                content_overlap = len(query_tokens & content_tokens) / len(query_tokens)
                candidate.fusion_score += 0.012 * title_overlap
                candidate.fusion_score += 0.004 * content_overlap
            candidate.topic_bonus = self.lexical.retrieval_topic_bonus(
                query, candidate.hit
            )
            candidate.fusion_score += candidate.topic_bonus

    @staticmethod
    def _payload_hit(payload: dict[str, Any], score: float) -> KnowledgeHit:
        return KnowledgeHit(
            chunk_id=str(payload["chunk_id"]),
            document_id=str(payload.get("document_id", "")),
            course_id=KnowledgeCourseId(str(payload["course_id"])),
            course_name=KNOWLEDGE_COURSE_NAMES[str(payload["course_id"])],
            chapter=str(payload.get("chapter", "UNKNOWN")),
            section=str(payload.get("parent_section", "")),
            document_path=str(payload.get("relative_path", "")),
            title=str(payload.get("title", "UNKNOWN")),
            content_type=str(payload.get("content_type", "unknown")),
            content=str(payload.get("text", "")),
            score=max(0.0, float(score)),
            source_ref=str(payload.get("source_uri", "")),
            document_checksum=str(payload.get("checksum", "")),
        )

    def _final_score(self, candidate: _Candidate) -> float:
        if candidate.rerank_score is None:
            # Raw RRF values are intentionally small (roughly 1/(k+rank)).
            # Normalize around two agreeing retrieval routes so API confidence
            # remains a meaningful 0..1 value even when reranking is disabled.
            return min(
                1.0,
                candidate.fusion_score * (self.settings.rag_rrf_k + 1) / 2,
            )
        rerank_normalized = 1.0 / (1.0 + math.exp(-candidate.rerank_score))
        return 0.7 * rerank_normalized + 0.3 * min(1.0, candidate.fusion_score * 30)

    def _finalize(self, candidate: _Candidate) -> KnowledgeHit:
        final_score = self._final_score(candidate)
        return candidate.hit.model_copy(
            update={
                "score": max(0.0, final_score),
                "score_components": {
                    **{
                        f"{key}_rank": float(value)
                        for key, value in candidate.ranks.items()
                    },
                    "fusion_score": candidate.fusion_score,
                    "topic_bonus": candidate.topic_bonus,
                    "rerank_score": candidate.rerank_score or 0.0,
                    "final_score": final_score,
                },
            }
        )

    def _final_images(
        self, records: dict[str, dict[str, Any]], *, limit: int
    ) -> list[RelatedImage]:
        ranked = []
        for record in records.values():
            rrf = sum(
                1.0 / (self.settings.rag_rrf_k + rank)
                for rank in record["ranks"].values()
            )
            ranked.append((rrf, record))
        ranked.sort(key=lambda item: -item[0])
        output: list[RelatedImage] = []
        for score, record in ranked[:limit]:
            payload = record["payload"]
            output.append(
                RelatedImage(
                    image_id=str(payload["image_id"]),
                    resource_uri=str(payload["resource_uri"]),
                    caption=str(payload.get("caption", "")),
                    description_source=str(
                        payload.get("description_source", "source_text")
                    ),
                    course_id=str(payload.get("course_id", "")),
                    parent_document_id=payload.get("parent_document_id"),
                    parent_chunk_id=payload.get("parent_chunk_id"),
                    image_type=str(payload.get("image_type", "unknown")),
                    score=max(0.0, score),
                    retrieval_channels=list(record["ranks"]),
                )
            )
        return output

    @staticmethod
    def _confidence(hits: list[KnowledgeHit]) -> float | None:
        if not hits:
            return None
        top = hits[:3]
        return round(sum(hit.score for hit in top) / len(top), 6)
