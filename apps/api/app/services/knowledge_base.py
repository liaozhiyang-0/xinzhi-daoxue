from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class KnowledgeSnippet:
    content: str
    source_ref: str
    score: float


def tokenize(value: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(value)]


class KnowledgeBaseService:
    """Small read-only BM25-style adapter over the existing course Markdown tree."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def search(
        self, query: str, course_id: str, top_k: int
    ) -> list[KnowledgeSnippet]:
        root = self.settings.knowledge_paths.get(course_id)
        if root is None or not root.is_dir():
            raise OSError(f"课程知识库目录不可用: {course_id}")
        query_terms = Counter(tokenize(query))
        if not query_terms:
            return []
        max_bytes = self.settings.knowledge_max_file_size_mb * 1024 * 1024
        documents: list[tuple[str, str, Counter[str]]] = []
        for path in sorted(root.rglob("*.md"))[
            : self.settings.knowledge_max_files_per_course
        ]:
            try:
                if path.is_symlink() or path.stat().st_size > max_bytes:
                    continue
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            relative = path.relative_to(root).as_posix()
            for index, chunk in enumerate(self._chunks(text), start=1):
                terms = Counter(tokenize(chunk))
                if terms:
                    documents.append((f"kb://{course_id}/{relative}#chunk-{index}", chunk, terms))
        if not documents:
            return []
        document_frequency = Counter(
            term for _, _, terms in documents for term in terms
        )
        average_length = sum(sum(terms.values()) for _, _, terms in documents) / len(documents)
        scored: list[KnowledgeSnippet] = []
        for source_ref, content, terms in documents:
            length_ratio = sum(terms.values()) / max(1.0, average_length)
            score = 0.0
            for term, query_frequency in query_terms.items():
                frequency = terms.get(term, 0)
                if not frequency:
                    continue
                inverse = math.log(
                    1
                    + (len(documents) - document_frequency[term] + 0.5)
                    / (document_frequency[term] + 0.5)
                )
                saturation = frequency * 2.5 / (
                    frequency + 1.5 * (0.25 + 0.75 * length_ratio)
                )
                score += inverse * saturation * query_frequency
            if score > 0:
                scored.append(KnowledgeSnippet(content, source_ref, score))
        scored.sort(key=lambda item: (-item.score, item.source_ref))
        return scored[:top_k]

    @staticmethod
    def _chunks(text: str, max_chars: int = 1200) -> list[str]:
        headings = list(HEADING_RE.finditer(text))
        sections: list[str] = []
        if not headings:
            sections = [text]
        else:
            for index, heading in enumerate(headings):
                end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
                sections.append(text[heading.start() : end])
        chunks: list[str] = []
        for section in sections:
            normalized = section.strip()
            for start in range(0, len(normalized), max_chars):
                chunk = normalized[start : start + max_chars].strip()
                if chunk:
                    chunks.append(chunk)
        return chunks
