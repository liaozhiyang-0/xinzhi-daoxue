from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from threading import RLock
from time import perf_counter
from typing import Any

import yaml

from app.contracts import (
    KnowledgeHit,
    KnowledgeSourceStatus,
    RelatedImage,
    RetrievalResult,
)
from app.contracts.knowledge import KnowledgeCourseId, utc_now
from app.core.config import Settings
from app.services.knowledge_audit import (
    infer_content_type,
    markdown_image_references,
    stable_id,
)

COURSE_NAMES: dict[str, str] = {
    "CT": "电路理论",
    "AE": "模拟电子技术",
    "DE": "数字电子技术",
}
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^\)]+\)")
HTML_RE = re.compile(r"<[^>]+>")
LATIN_RE = re.compile(r"[a-z0-9]+(?:[._+-][a-z0-9]+)*", re.IGNORECASE)
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")


@dataclass(frozen=True, slots=True)
class IndexedChunk:
    chunk_id: str
    document_id: str
    course_id: KnowledgeCourseId
    course_name: str
    chapter: str
    section: str
    document_path: str
    title: str
    content_type: str
    content: str
    source_ref: str
    document_checksum: str
    tokens: Counter[str]
    title_tokens: Counter[str]
    content_tokens: Counter[str]
    filename_tokens: Counter[str]
    token_count: int
    normalized_content: str
    excluded_v2: bool
    related_images: tuple[RelatedImage, ...]


@dataclass(frozen=True, slots=True)
class CourseMetadata:
    patterns: tuple[str, ...]
    excluded_paths: tuple[str, ...]
    chapter_aliases: dict[str, str]
    synonyms: dict[str, tuple[str, ...]]
    retrieval_topic_boosts: tuple[RetrievalTopicBoost, ...]
    approved_corrections: tuple[dict[str, str], ...]


@dataclass(frozen=True, slots=True)
class RetrievalTopicBoost:
    """Course-local, terminology-based boost for a narrowly defined topic."""

    name: str
    query_terms: tuple[str, ...]
    query_context_terms: tuple[str, ...]
    evidence_terms: tuple[str, ...]
    preferred_content_types: tuple[str, ...]
    evidence_term_boost: float
    content_type_boost: float
    max_boost: float


def normalize_query(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def tokenize(text: str) -> list[str]:
    """Frozen stage 1.5 tokenizer used by the baseline and v2 scorer."""
    normalized = normalize_query(text).replace("节点", "结点")
    tokens = LATIN_RE.findall(normalized)
    for sequence in CJK_RE.findall(normalized):
        tokens.extend(sequence)
        tokens.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
    return tokens


def clean_markdown(text: str) -> str:
    text = IMAGE_RE.sub(lambda match: f" 图示：{match.group(1)} ", text)
    text = HTML_RE.sub(" ", text)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"[`*_>|]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_markdown(text: str, chunk_size: int, overlap: int) -> list[tuple[str, str]]:
    """Frozen stage 1.5 chunking behavior."""
    matches = list(HEADING_RE.finditer(text))
    sections: list[tuple[str, str]] = []
    if not matches:
        sections.append(("未命名章节", text))
    else:
        if matches[0].start() > 0:
            sections.append(("文档前言", text[: matches[0].start()]))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            sections.append((match.group(2).strip(), text[match.end() : end]))

    chunks: list[tuple[str, str]] = []
    step = max(1, chunk_size - overlap)
    for title, body in sections:
        cleaned = clean_markdown(body)
        if not cleaned:
            continue
        for start in range(0, len(cleaned), step):
            content = cleaned[start : start + chunk_size].strip()
            if content:
                chunks.append((title, content))
            if start + chunk_size >= len(cleaned):
                break
    return chunks


class KnowledgeBaseService:
    """Read-only lexical index for the three local Markdown course libraries."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = RLock()
        self._loaded = False
        self._chunks: list[IndexedChunk] = []
        self._document_frequency: Counter[str] = Counter()
        self._average_length = 1.0
        self._statuses: list[KnowledgeSourceStatus] = []
        self._metadata = {
            course_id: self._load_metadata(course_id) for course_id in COURSE_NAMES
        }

    def refresh(self) -> list[KnowledgeSourceStatus]:
        with self._lock:
            chunks: list[IndexedChunk] = []
            statuses: list[KnowledgeSourceStatus] = []
            indexed_at = utc_now()
            for course_id, root in self.settings.knowledge_paths.items():
                course = KnowledgeCourseId(course_id)
                course_name = COURSE_NAMES[course_id]
                course_chunks, document_count, message = self._index_course(
                    course, course_name, root
                )
                chunks.extend(course_chunks)
                statuses.append(
                    KnowledgeSourceStatus(
                        course_id=course,
                        course_name=course_name,
                        available=root.is_dir(),
                        document_count=document_count,
                        chunk_count=len(course_chunks),
                        indexed_at=indexed_at if root.is_dir() else None,
                        message=message,
                    )
                )

            frequencies: Counter[str] = Counter()
            for chunk in chunks:
                frequencies.update(chunk.tokens.keys())
            self._chunks = chunks
            self._document_frequency = frequencies
            self._average_length = (
                sum(chunk.token_count for chunk in chunks) / len(chunks)
                if chunks
                else 1.0
            )
            self._statuses = statuses
            self._loaded = True
            return [status.model_copy() for status in statuses]

    def source_statuses(self) -> list[KnowledgeSourceStatus]:
        self._ensure_loaded()
        with self._lock:
            return [status.model_copy() for status in self._statuses]

    def search(
        self,
        query: str,
        course_ids: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[KnowledgeHit]:
        return self.search_result(query, course_ids, top_k).hits

    def search_baseline(
        self,
        query: str,
        course_ids: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[KnowledgeHit]:
        """Frozen stage 1.5 ranking for reproducible baseline comparisons."""
        self._ensure_loaded()
        query_tokens = Counter(tokenize(query))
        if not query_tokens:
            return []
        selected = set(course_ids or COURSE_NAMES)
        limit = top_k or self.settings.knowledge_default_top_k
        with self._lock:
            total = max(1, len(self._chunks))
            scored = [
                (self._score_baseline(chunk, query_tokens, total), chunk)
                for chunk in self._chunks
                if chunk.course_id in selected
            ]
            scored = [(score, chunk) for score, chunk in scored if score > 0]
            scored.sort(key=lambda item: (-item[0], item[1].source_ref))
            return [
                self._hit(chunk, score, {"bm25_baseline": score})
                for score, chunk in scored[:limit]
            ]

    def search_result(
        self,
        query: str,
        course_ids: list[str] | None = None,
        top_k: int | None = None,
    ) -> RetrievalResult:
        started = perf_counter()
        self._ensure_loaded()
        selected = [item.upper() for item in (course_ids or list(COURSE_NAMES))]
        normalized = normalize_query(query)
        expanded = self.expand_query(normalized, selected)
        query_tokens = Counter(tokenize(expanded))
        limit = top_k or self.settings.knowledge_default_top_k
        warnings: list[str] = []
        if not query_tokens:
            warnings.append("查询标准化后没有可检索词项")
            return RetrievalResult(
                query=query,
                normalized_query=expanded,
                course_ids=selected,
                hits=[],
                confidence=None,
                warnings=warnings,
                latency_ms=max(0, round((perf_counter() - started) * 1000)),
            )

        with self._lock:
            total = max(1, len(self._chunks))
            scored: list[tuple[float, IndexedChunk, dict[str, float]]] = []
            for chunk in self._chunks:
                if chunk.course_id not in selected or chunk.excluded_v2:
                    continue
                components = self._score_v2(
                    chunk,
                    query_tokens,
                    normalized,
                    total,
                )
                score = sum(components.values())
                if score >= self.settings.knowledge_min_score_v2:
                    scored.append((score, chunk, components))
            scored.sort(key=lambda item: (-item[0], item[1].source_ref))
            chosen = self._deduplicate_and_diversify(scored, limit)
            hits = [
                self._hit(chunk, score, components)
                for score, chunk, components in chosen
            ]

        confidence = None
        if hits:
            confidence = round(min(1.0, hits[0].score / (hits[0].score + 5.0)), 6)
            if confidence < self.settings.knowledge_low_confidence_threshold:
                warnings.append("检索置信度较低，请核对章节与原始资料")
        else:
            warnings.append("本地词项检索未命中满足最低分阈值的片段")
        return RetrievalResult(
            query=query,
            normalized_query=expanded,
            course_ids=selected,
            hits=hits,
            confidence=confidence,
            retrieval_mode="sparse_bm25_v1",
            rag_status="degraded",
            embedding_status="unavailable",
            vector_store_status="not_used",
            reranker_status="not_used",
            warnings=warnings,
            latency_ms=max(0, round((perf_counter() - started) * 1000)),
        )

    def expand_query(self, normalized_query: str, course_ids: list[str]) -> str:
        expansions: list[str] = [normalized_query]
        seen = {normalized_query}
        for course_id in course_ids:
            metadata = self._metadata.get(course_id)
            if metadata is None:
                continue
            for canonical, variants in metadata.synonyms.items():
                group = (canonical, *variants)
                if any(normalize_query(term) in normalized_query for term in group):
                    for term in group:
                        normalized_term = normalize_query(term)
                        if normalized_term and normalized_term not in seen:
                            expansions.append(normalized_term)
                            seen.add(normalized_term)
            for alias, canonical in metadata.chapter_aliases.items():
                if normalize_query(alias) in normalized_query:
                    normalized_term = normalize_query(canonical)
                    if normalized_term not in seen:
                        expansions.append(normalized_term)
                        seen.add(normalized_term)
        return " ".join(expansions)

    def retrieval_topic_bonus(self, query: str, hit: KnowledgeHit) -> float:
        """Return an opt-in course/topic bonus without changing global RRF weights."""
        self._ensure_loaded()
        metadata = self._metadata.get(hit.course_id.value)
        if metadata is None:
            return 0.0
        normalized_query = normalize_query(query)
        searchable = normalize_query(
            " ".join((hit.title, hit.chapter, hit.section, hit.content))
        )
        best_bonus = 0.0
        for rule in metadata.retrieval_topic_boosts:
            if rule.query_terms and not any(
                normalize_query(term) in normalized_query for term in rule.query_terms
            ):
                continue
            if rule.query_context_terms and not any(
                normalize_query(term) in normalized_query
                for term in rule.query_context_terms
            ):
                continue
            evidence_matches = sum(
                1 for term in rule.evidence_terms if normalize_query(term) in searchable
            )
            if evidence_matches == 0:
                continue
            bonus = evidence_matches * rule.evidence_term_boost
            if hit.content_type in rule.preferred_content_types:
                bonus += rule.content_type_boost
            best_bonus = max(best_bonus, min(rule.max_boost, bonus))
        return best_bonus

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.refresh()

    def _load_metadata(self, course_id: str) -> CourseMetadata:
        root = self.settings.knowledge_config_path
        course_payload = self._read_yaml(root / "courses" / f"{course_id}.yaml")
        synonym_payload = self._read_yaml(root / "synonyms" / f"{course_id}.yaml")
        correction_payload = self._read_yaml(root / "corrections" / f"{course_id}.yaml")
        synonyms = {
            str(key): tuple(str(item) for item in value)
            for key, value in synonym_payload.items()
            if isinstance(value, list)
        }
        rules = correction_payload.get("rules", [])
        approved = (
            tuple(
                {str(key): str(value) for key, value in rule.items()}
                for rule in rules
                if isinstance(rule, dict) and rule.get("review_status") == "approved"
            )
            if isinstance(rules, list)
            else ()
        )
        aliases = course_payload.get("chapter_aliases", {})
        topic_boost_payload = course_payload.get("retrieval_topic_boosts", [])
        topic_boosts = tuple(
            RetrievalTopicBoost(
                name=str(item.get("name", "unnamed")),
                query_terms=tuple(str(term) for term in item.get("query_terms", [])),
                query_context_terms=tuple(
                    str(term) for term in item.get("query_context_terms", [])
                ),
                evidence_terms=tuple(
                    str(term) for term in item.get("evidence_terms", [])
                ),
                preferred_content_types=tuple(
                    str(term) for term in item.get("preferred_content_types", [])
                ),
                evidence_term_boost=float(item.get("evidence_term_boost", 0.0)),
                content_type_boost=float(item.get("content_type_boost", 0.0)),
                max_boost=float(item.get("max_boost", 0.0)),
            )
            for item in topic_boost_payload
            if isinstance(item, dict)
        )
        return CourseMetadata(
            patterns=tuple(
                str(item)
                for item in course_payload.get("document_patterns", ["**/*.md"])
            ),
            excluded_paths=tuple(
                str(item) for item in course_payload.get("excluded_paths", [])
            ),
            chapter_aliases={str(k): str(v) for k, v in aliases.items()}
            if isinstance(aliases, dict)
            else {},
            synonyms=synonyms,
            retrieval_topic_boosts=topic_boosts,
            approved_corrections=approved,
        )

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _index_course(
        self,
        course_id: KnowledgeCourseId,
        course_name: str,
        root: Path,
    ) -> tuple[list[IndexedChunk], int, str | None]:
        if not self.settings.knowledge_enabled:
            return [], 0, "本地知识库已禁用"
        if not root.is_dir():
            return [], 0, "目录不存在；请配置只读知识库路径"

        root_resolved = root.resolve()
        max_bytes = self.settings.knowledge_max_file_size_mb * 1024 * 1024
        files = sorted(root.rglob("*.md"), key=lambda path: path.as_posix())
        files = files[: self.settings.knowledge_max_files_per_course]
        chunks: list[IndexedChunk] = []
        document_count = 0
        skipped = 0
        metadata = self._metadata[course_id.value]
        for file_path in files:
            try:
                resolved = file_path.resolve()
                resolved.relative_to(root_resolved)
                if file_path.is_symlink() or file_path.stat().st_size > max_bytes:
                    skipped += 1
                    continue
                raw_text = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError, ValueError):
                skipped += 1
                continue
            document_count += 1
            relative = file_path.relative_to(root).as_posix()
            text = self._apply_approved_corrections(raw_text, relative, metadata)
            checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            document_id = stable_id("DOC", course_id.value, relative.casefold())
            image_references = markdown_image_references(
                course_id=course_id.value,
                document_path=file_path,
                root=root,
                document_id=document_id,
                text=raw_text,
            )
            excluded = any(
                PurePosixPath(relative).match(pattern)
                for pattern in metadata.excluded_paths
            )
            for index, (title, content) in enumerate(
                split_markdown(
                    text,
                    self.settings.knowledge_chunk_size_chars,
                    self.settings.knowledge_chunk_overlap_chars,
                ),
                start=1,
            ):
                baseline_tokens = Counter(tokenize(f"{title} {content}"))
                if not baseline_tokens:
                    continue
                chunk_id = hashlib.sha256(
                    f"{course_id.value}:{relative}:{index}".encode()
                ).hexdigest()[:24]
                source_ref = f"kb://{course_id}/{relative}#chunk-{index}"
                chunks.append(
                    IndexedChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        course_id=course_id,
                        course_name=course_name,
                        chapter=title,
                        section=title,
                        document_path=relative,
                        title=title,
                        content_type=infer_content_type(file_path, title, content),
                        content=content,
                        source_ref=source_ref,
                        document_checksum=checksum,
                        tokens=baseline_tokens,
                        title_tokens=Counter(tokenize(title)),
                        content_tokens=Counter(tokenize(content)),
                        filename_tokens=Counter(tokenize(file_path.stem)),
                        token_count=sum(baseline_tokens.values()),
                        normalized_content=normalize_query(content),
                        excluded_v2=excluded,
                        related_images=tuple(
                            RelatedImage(
                                image_id=stable_id(
                                    "IMG",
                                    course_id.value,
                                    reference.image_relative_path.casefold(),
                                ),
                                resource_uri=(
                                    f"kb-image://{course_id.value}/"
                                    f"{reference.image_relative_path}"
                                ),
                                caption=(reference.alt_text or reference.nearby_text),
                                description_source="source_text",
                            )
                            for reference in image_references
                            if reference.exists and reference.section == title
                        ),
                    )
                )
        message = f"跳过 {skipped} 个不可读或超限文件" if skipped else None
        return chunks, document_count, message

    @staticmethod
    def _apply_approved_corrections(
        text: str, relative: str, metadata: CourseMetadata
    ) -> str:
        updated = text
        for rule in metadata.approved_corrections:
            if rule.get("document_path") == relative:
                updated = updated.replace(
                    rule.get("original", ""), rule.get("replacement", "")
                )
        return updated

    def _score_baseline(
        self, chunk: IndexedChunk, query_tokens: Counter[str], total: int
    ) -> float:
        score = 0.0
        k1 = 1.5
        b = 0.75
        length_ratio = chunk.token_count / self._average_length
        title_tokens = set(tokenize(chunk.title))
        for token, query_frequency in query_tokens.items():
            term_frequency = chunk.tokens.get(token, 0)
            if not term_frequency:
                continue
            document_frequency = self._document_frequency.get(token, 0)
            inverse_frequency = math.log(
                1 + (total - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            saturation = (term_frequency * (k1 + 1)) / (
                term_frequency + k1 * (1 - b + b * length_ratio)
            )
            title_boost = 1.35 if token in title_tokens else 1.0
            token_weight = 0.25 if len(token) == 1 and CJK_RE.fullmatch(token) else 1.0
            score += (
                inverse_frequency
                * saturation
                * query_frequency
                * title_boost
                * token_weight
            )
        return score

    def _score_v2(
        self,
        chunk: IndexedChunk,
        query_tokens: Counter[str],
        normalized_query_text: str,
        total: int,
    ) -> dict[str, float]:
        bm25 = (
            self._score_baseline(chunk, query_tokens, total)
            * self.settings.knowledge_keyword_weight
        )
        title_overlap = sum(
            query_tokens[token] for token in chunk.title_tokens if token in query_tokens
        )
        filename_overlap = sum(
            query_tokens[token]
            for token in chunk.filename_tokens
            if token in query_tokens
        )
        image_context_tokens = Counter(
            tokenize(" ".join(image.caption for image in chunk.related_images))
        )
        image_context_overlap = sum(
            query_tokens[token]
            for token in image_context_tokens
            if token in query_tokens
        )
        exact_phrase = 0.0
        if len(normalized_query_text) >= 2:
            if normalized_query_text in normalize_query(chunk.title):
                exact_phrase = 3.0
            elif normalized_query_text in chunk.normalized_content:
                exact_phrase = 1.8
        short_penalty = -0.8 if len(chunk.content) < 80 else 0.0
        return {
            "bm25": bm25,
            "exact_phrase_boost": exact_phrase,
            "title_boost": min(3.0, title_overlap * 0.18),
            "chapter_boost": min(1.5, title_overlap * 0.08),
            "filename_boost": min(1.0, filename_overlap * 0.12),
            "image_context_boost": min(
                self.settings.knowledge_image_context_weight,
                image_context_overlap
                * 0.08
                * self.settings.knowledge_image_context_weight,
            ),
            "short_fragment_penalty": short_penalty,
        }

    def _deduplicate_and_diversify(
        self,
        scored: list[tuple[float, IndexedChunk, dict[str, float]]],
        limit: int,
    ) -> list[tuple[float, IndexedChunk, dict[str, float]]]:
        chosen: list[tuple[float, IndexedChunk, dict[str, float]]] = []
        per_document: defaultdict[str, int] = defaultdict(int)
        signatures: defaultdict[str, list[set[str]]] = defaultdict(list)
        for item in scored:
            _, chunk, _ = item
            if (
                per_document[chunk.document_path]
                >= self.settings.knowledge_max_hits_per_document
            ):
                continue
            signature = set(tokenize(chunk.content))
            if any(
                signature and len(signature & prior) / len(signature | prior) >= 0.88
                for prior in signatures[chunk.document_path]
            ):
                continue
            chosen.append(item)
            per_document[chunk.document_path] += 1
            signatures[chunk.document_path].append(signature)
            if len(chosen) >= limit:
                break
        return chosen

    @staticmethod
    def _hit(
        chunk: IndexedChunk, score: float, components: dict[str, float]
    ) -> KnowledgeHit:
        return KnowledgeHit(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            course_id=chunk.course_id,
            course_name=chunk.course_name,
            chapter=chunk.chapter,
            section=chunk.section,
            document_path=chunk.document_path,
            title=chunk.title,
            content_type=chunk.content_type,
            content=chunk.content,
            score=round(max(0.0, score), 6),
            score_components={
                key: round(value, 6) for key, value in components.items()
            },
            source_ref=chunk.source_ref,
            document_checksum=chunk.document_checksum,
            related_images=list(chunk.related_images),
        )
