from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from app.contracts import KnowledgeHit, KnowledgeSourceStatus
from app.contracts.knowledge import KnowledgeCourseId, utc_now
from app.core.config import Settings

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
    course_id: KnowledgeCourseId
    course_name: str
    document_path: str
    title: str
    content: str
    source_ref: str
    tokens: Counter[str]
    token_count: int


def tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = normalized.replace("节点", "结点")
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
    """Read-only Markdown index for the three local course libraries."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = RLock()
        self._loaded = False
        self._chunks: list[IndexedChunk] = []
        self._document_frequency: Counter[str] = Counter()
        self._average_length = 1.0
        self._statuses: list[KnowledgeSourceStatus] = []

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
        self._ensure_loaded()
        query_tokens = Counter(tokenize(query))
        if not query_tokens:
            return []
        selected = set(course_ids or COURSE_NAMES)
        limit = top_k or self.settings.knowledge_default_top_k
        with self._lock:
            total = max(1, len(self._chunks))
            scored: list[tuple[float, IndexedChunk]] = []
            for chunk in self._chunks:
                if chunk.course_id not in selected:
                    continue
                score = self._score(chunk, query_tokens, total)
                if score > 0:
                    scored.append((score, chunk))
            scored.sort(key=lambda item: (-item[0], item[1].source_ref))
            return [
                KnowledgeHit(
                    course_id=chunk.course_id,
                    course_name=chunk.course_name,
                    document_path=chunk.document_path,
                    title=chunk.title,
                    content=chunk.content,
                    score=round(score, 6),
                    source_ref=chunk.source_ref,
                )
                for score, chunk in scored[:limit]
            ]

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self.refresh()

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
        for file_path in files:
            try:
                resolved = file_path.resolve()
                resolved.relative_to(root_resolved)
                if file_path.is_symlink() or file_path.stat().st_size > max_bytes:
                    skipped += 1
                    continue
                text = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError, ValueError):
                skipped += 1
                continue
            document_count += 1
            relative = file_path.relative_to(root).as_posix()
            for index, (title, content) in enumerate(
                split_markdown(
                    text,
                    self.settings.knowledge_chunk_size_chars,
                    self.settings.knowledge_chunk_overlap_chars,
                ),
                start=1,
            ):
                token_counts = Counter(tokenize(f"{title} {content}"))
                if not token_counts:
                    continue
                source_ref = f"kb://{course_id}/{relative}#chunk-{index}"
                chunks.append(
                    IndexedChunk(
                        course_id=course_id,
                        course_name=course_name,
                        document_path=relative,
                        title=title,
                        content=content,
                        source_ref=source_ref,
                        tokens=token_counts,
                        token_count=sum(token_counts.values()),
                    )
                )
        message = f"跳过 {skipped} 个不可读或超限文件" if skipped else None
        return chunks, document_count, message

    def _score(
        self,
        chunk: IndexedChunk,
        query_tokens: Counter[str],
        total: int,
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
            token_weight = (
                0.25 if len(token) == 1 and CJK_RE.fullmatch(token) else 1.0
            )
            score += (
                inverse_frequency
                * saturation
                * query_frequency
                * title_boost
                * token_weight
            )
        return score
