from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from app.core.config import Settings
from app.services.knowledge_base import KnowledgeBaseService
from app.services.rag_retrieval import RAGRetrievalService


def test_index_version_cache_refreshes_when_state_file_changes(tmp_path: Path) -> None:
    index_root = tmp_path / "indexes"
    index_root.mkdir()
    state = index_root / "rag_index_state.json"
    state.write_text(json.dumps({"index_version": "v1"}), encoding="utf-8")
    settings = Settings(
        app_env="test",
        knowledge_index_path=index_root,
        _env_file=None,
    )
    service = RAGRetrievalService(
        settings,
        KnowledgeBaseService(settings),
        cast(Any, None),
        cast(Any, None),
        cast(Any, None),
        cast(Any, None),
    )

    assert service._index_version() == "v1"
    assert service._index_version() == "v1"
    assert service._metrics["rag_index_version_read_total"] == 1
    assert service._metrics["rag_index_version_cache_hit_total"] == 1
    state.write_text(json.dumps({"index_version": "version-2"}), encoding="utf-8")

    assert service._index_version() == "version-2"
    assert service._metrics["rag_index_version_read_total"] == 2
