from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import RLock
from time import time
from typing import Any
from uuid import uuid4

from app.core.config import Settings

OCR_REVIEW_SNAPSHOT_SCHEMA = "ocr_review_queue_snapshot.v1"


@dataclass(frozen=True, slots=True)
class _MemorySnapshot:
    fingerprint: str
    cached_at: float
    payload: dict[str, Any]


def _file_metadata(path: Path, relative_path: str) -> tuple[Any, ...]:
    try:
        stat = path.stat()
    except OSError:
        return (relative_path, "unreadable")
    return (relative_path, stat.st_size, stat.st_mtime_ns)


def build_ocr_review_fingerprint(
    roots: dict[str, Path],
    course_ids: tuple[str, ...],
    decisions_path: Path,
    *,
    max_parse_bytes: int,
) -> str:
    """Build a cheap metadata fingerprint without reading document contents."""

    records: list[tuple[Any, ...]] = [
        ("config", "max_parse_bytes", max_parse_bytes),
    ]
    for course_id in course_ids:
        root = roots[course_id]
        if root.is_dir():
            for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
                if not path.is_file() or path.is_symlink():
                    continue
                relative_path = path.relative_to(root).as_posix()
                records.append(
                    (course_id, *_file_metadata(path, relative_path))
                )
        else:
            records.append((course_id, "<root>", "missing"))
        decision_file = decisions_path / f"{course_id}.yaml"
        if decision_file.is_file() and not decision_file.is_symlink():
            records.append(
                (
                    course_id,
                    "<decision>",
                    *_file_metadata(decision_file, decision_file.name),
                )
            )
        else:
            records.append((course_id, "<decision>", "missing"))
    serialized = json.dumps(
        records,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(serialized).hexdigest()


class KnowledgeOCRReviewSnapshotCache:
    """Cache read-only OCR review queues by source metadata and TTL."""

    def __init__(
        self,
        settings: Settings,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.settings = settings
        self._clock = clock or time
        self._lock = RLock()
        self._memory: dict[str, _MemorySnapshot] = {}

    def get_or_build(
        self,
        course_id: str | None,
        builder: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        selected = tuple(
            course_id.upper() if course_id else item
            for item in (course_id,) if item
        ) or tuple(self.settings.knowledge_paths)
        cache_key = course_id.lower() if course_id else "all"
        now = self._clock()
        if not self.settings.knowledge_ocr_review_cache_enabled:
            return self._decorate(
                builder(),
                cache_status="disabled",
                cache_backend="none",
                source_fingerprint="",
                snapshot_age_seconds=0.0,
            )

        fingerprint = build_ocr_review_fingerprint(
            self.settings.knowledge_paths,
            selected,
            self.settings.knowledge_ocr_decisions_path,
            max_parse_bytes=self.settings.knowledge_max_file_size_mb * 1024 * 1024,
        )
        with self._lock:
            memory = self._memory.get(cache_key)
            if memory and self._is_fresh(
                memory.fingerprint, memory.cached_at, fingerprint, now
            ):
                return self._decorate(
                    memory.payload,
                    cache_status="hit",
                    cache_backend="memory",
                    source_fingerprint=fingerprint,
                    snapshot_age_seconds=now - memory.cached_at,
                )

            disk = self._load_disk(cache_key)
            if disk is not None:
                disk_fingerprint, cached_at, payload = disk
                if self._is_fresh(disk_fingerprint, cached_at, fingerprint, now):
                    self._memory[cache_key] = _MemorySnapshot(
                        fingerprint=fingerprint,
                        cached_at=cached_at,
                        payload=payload,
                    )
                    return self._decorate(
                        payload,
                        cache_status="hit",
                        cache_backend="disk",
                        source_fingerprint=fingerprint,
                        snapshot_age_seconds=now - cached_at,
                    )

            stale = memory is not None or disk is not None
            payload = builder()
            cached_at = self._clock()
            self._memory[cache_key] = _MemorySnapshot(
                fingerprint=fingerprint,
                cached_at=cached_at,
                payload=deepcopy(payload),
            )
            self._write_disk(cache_key, fingerprint, cached_at, payload)
            return self._decorate(
                payload,
                cache_status="stale" if stale else "miss",
                cache_backend="memory",
                source_fingerprint=fingerprint,
                snapshot_age_seconds=0.0,
            )

    def invalidate(self, course_id: str | None) -> None:
        """Drop the in-memory snapshot after a teacher decision write."""

        cache_key = course_id.lower() if course_id else "all"
        with self._lock:
            self._memory.pop(cache_key, None)

    def _is_fresh(
        self,
        cached_fingerprint: str,
        cached_at: float,
        current_fingerprint: str,
        now: float,
    ) -> bool:
        return (
            cached_fingerprint == current_fingerprint
            and now - cached_at <= self.settings.knowledge_ocr_review_cache_ttl_seconds
        )

    def _cache_path(self, cache_key: str) -> Path:
        return self.settings.knowledge_ocr_review_cache_path / f"{cache_key}.json"

    def _load_disk(
        self, cache_key: str
    ) -> tuple[str, float, dict[str, Any]] | None:
        path = self._cache_path(cache_key)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                return None
            if document.get("schema_version") != OCR_REVIEW_SNAPSHOT_SCHEMA:
                return None
            fingerprint = document.get("source_fingerprint")
            cached_at = document.get("cached_at")
            payload = document.get("payload")
            if (
                not isinstance(fingerprint, str)
                or not isinstance(cached_at, (int, float))
                or not isinstance(payload, dict)
            ):
                return None
            return fingerprint, float(cached_at), payload
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            return None

    def _write_disk(
        self,
        cache_key: str,
        fingerprint: str,
        cached_at: float,
        payload: dict[str, Any],
    ) -> None:
        path = self._cache_path(cache_key)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        document = {
            "schema_version": OCR_REVIEW_SNAPSHOT_SCHEMA,
            "cache_key": cache_key,
            "source_fingerprint": fingerprint,
            "cached_at": cached_at,
            "payload": payload,
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(document, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
                newline="\n",
            )
            temporary.replace(path)
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _decorate(
        payload: dict[str, Any],
        *,
        cache_status: str,
        cache_backend: str,
        source_fingerprint: str,
        snapshot_age_seconds: float,
    ) -> dict[str, Any]:
        result = deepcopy(payload)
        result.update(
            {
                "cache_status": cache_status,
                "cache_backend": cache_backend,
                "source_fingerprint": source_fingerprint,
                "snapshot_age_seconds": max(0.0, round(snapshot_age_seconds, 3)),
            }
        )
        return result
