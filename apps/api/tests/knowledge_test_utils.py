from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.services.knowledge_base import KnowledgeBaseService


def make_service(
    tmp_path: Path,
    documents: dict[str, dict[str, str]],
    **overrides: object,
) -> KnowledgeBaseService:
    roots = {course: tmp_path / course for course in ("CT", "AE", "DE")}
    for course, root in roots.items():
        root.mkdir()
        for relative, content in documents.get(course, {}).items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    values: dict[str, object] = {
        "app_env": "test",
        "knowledge_ct_path": roots["CT"],
        "knowledge_ae_path": roots["AE"],
        "knowledge_de_path": roots["DE"],
        "knowledge_chunk_size_chars": 300,
        "knowledge_chunk_overlap_chars": 100,
    }
    values.update(overrides)
    return KnowledgeBaseService(Settings(**values))  # type: ignore[arg-type]
