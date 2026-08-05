from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

from app.core.config import Settings
from app.services.knowledge_ocr_review_cache import (
    KnowledgeOCRReviewSnapshotCache,
)


def _settings(tmp_path: Path) -> Settings:
    roots = {
        course: tmp_path / course
        for course in ("CT", "AE", "DE", "SS", "DSP", "COMM")
    }
    for root in roots.values():
        root.mkdir()
    return Settings(
        app_env="test",
        test_database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        redis_url="redis://127.0.0.1:1/0",
        minio_endpoint="127.0.0.1:1",
        local_storage_path=tmp_path / "storage",
        knowledge_ct_path=roots["CT"],
        knowledge_ae_path=roots["AE"],
        knowledge_de_path=roots["DE"],
        knowledge_ss_path=roots["SS"],
        knowledge_dsp_path=roots["DSP"],
        knowledge_comm_path=roots["COMM"],
        knowledge_ocr_decisions_path=tmp_path / "decisions",
        knowledge_ocr_review_cache_path=tmp_path / "snapshots",
        knowledge_ocr_review_cache_ttl_seconds=300,
        _env_file=None,
    )


def _payload() -> dict[str, object]:
    return {
        "schema_version": "ocr_review_queue.v1",
        "generated_at": "2026-08-04T00:00:00+00:00",
        "mode": "read_only_draft",
        "runtime_loaded": False,
        "ocr_execution_performed": False,
        "summary": {"candidate_count": 0},
        "rows": [],
        "decision_reports": {},
    }


def test_cache_hits_memory_then_expires_by_ttl(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    clock = [1000.0]
    cache = KnowledgeOCRReviewSnapshotCache(settings, clock=lambda: clock[0])
    calls = 0

    def build() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return _payload()

    first = cache.get_or_build("CT", build)
    second = cache.get_or_build("CT", build)
    clock[0] += 301
    third = cache.get_or_build("CT", build)

    assert first["cache_status"] == "miss"
    assert second["cache_status"] == "hit"
    assert second["cache_backend"] == "memory"
    assert third["cache_status"] == "stale"
    assert calls == 2


def test_cache_invalidates_when_source_or_decision_metadata_changes(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    source = settings.knowledge_paths["CT"] / "chapter.md"
    source.write_text("before", encoding="utf-8")
    decisions = settings.knowledge_ocr_decisions_path
    decisions.mkdir()
    decision_file = decisions / "CT.yaml"
    decision_file.write_text("version: before", encoding="utf-8")
    cache = KnowledgeOCRReviewSnapshotCache(settings)
    calls = 0

    def build() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return _payload()

    cache.get_or_build("CT", build)
    source.write_text("after", encoding="utf-8")
    source_stat = source.stat()
    os.utime(
        source,
        ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns + 2_000_000_000),
    )
    result = cache.get_or_build("CT", build)
    assert result["cache_status"] == "stale"
    assert calls == 2

    decision_file.write_text("version: after", encoding="utf-8")
    decision_stat = decision_file.stat()
    os.utime(
        decision_file,
        ns=(decision_stat.st_atime_ns, decision_stat.st_mtime_ns + 2_000_000_000),
    )
    result = cache.get_or_build("CT", build)
    assert result["cache_status"] == "stale"
    assert calls == 3


def test_cache_uses_atomic_disk_snapshot_after_new_instance(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    first_cache = KnowledgeOCRReviewSnapshotCache(settings)
    first_cache.get_or_build("CT", _payload)
    second_cache = KnowledgeOCRReviewSnapshotCache(settings)

    result = second_cache.get_or_build(
        "CT", lambda: (_ for _ in ()).throw(AssertionError("disk cache miss"))
    )

    assert result["cache_status"] == "hit"
    assert result["cache_backend"] == "disk"


def test_cache_serializes_concurrent_builds(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    cache = KnowledgeOCRReviewSnapshotCache(settings)
    calls = 0
    calls_lock = Lock()

    def build() -> dict[str, object]:
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.02)
        return _payload()

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(lambda _: cache.get_or_build("CT", build), range(4))
        )

    assert calls == 1
    assert [item["cache_status"] for item in results].count("miss") == 1
    assert [item["cache_status"] for item in results].count("hit") == 3
