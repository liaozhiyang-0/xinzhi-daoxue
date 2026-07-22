from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import TYPE_CHECKING, Any

from app.contracts import NodeTrace

if TYPE_CHECKING:
    from app.orchestrator.state import XZDGraphState


class TraceStore:
    """Bounded in-memory trace store; summaries only, never raw secrets/files."""

    def __init__(self, *, max_records: int = 200, ttl_seconds: int = 3600) -> None:
        self.max_records = max_records
        self.ttl = timedelta(seconds=ttl_seconds)
        self._records: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def put(self, state: XZDGraphState) -> None:
        now = datetime.now(UTC)
        payload = {
            "trace_id": state["trace_id"],
            "run_id": state["run_id"],
            "request_id": state["request_id"],
            "course": state["course"],
            "intent": state["intent"],
            "task_family": state["task_family"],
            "selected_agent": state["selected_agent"],
            "route_status": state["route_status"],
            "warnings": list(state["warnings"]),
            "errors": list(state["errors"]),
            "nodes": [item.model_dump(mode="json") for item in state["trace"]],
            "updated_at": now.isoformat(),
        }
        with self._lock:
            self._prune(now)
            self._records[state["trace_id"]] = payload
            while len(self._records) > self.max_records:
                oldest = next(iter(self._records))
                self._records.pop(oldest, None)

    def append(self, trace_id: str, node: NodeTrace) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._prune(now)
            record = self._records.get(trace_id)
            if record is None:
                return
            nodes = record.setdefault("nodes", [])
            if isinstance(nodes, list):
                nodes.append(node.model_dump(mode="json"))
            record["updated_at"] = now.isoformat()

    def get(self, trace_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._prune(datetime.now(UTC))
            record = self._records.get(trace_id)
            return dict(record) if record is not None else None

    def _prune(self, now: datetime) -> None:
        expired: list[str] = []
        for trace_id, record in self._records.items():
            value = record.get("updated_at")
            try:
                updated = datetime.fromisoformat(str(value))
            except ValueError:
                expired.append(trace_id)
                continue
            if now - updated > self.ttl:
                expired.append(trace_id)
        for trace_id in expired:
            self._records.pop(trace_id, None)
