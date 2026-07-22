from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from threading import RLock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelCallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    request_id: str | None = None
    provider: str
    model: str
    task_type: str
    start_time: datetime
    elapsed_ms: int = Field(ge=0)
    status: Literal["completed", "failed"]
    retry_count: int = Field(ge=0)
    fallback_used: bool
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    image_count: int = Field(default=0, ge=0)
    high_resolution: bool = False
    provider_request_id: str | None = None
    error_type: str | None = None
    input_hash: str | None = None


class ModelTracer:
    """Bounded in-memory metadata trace; never stores prompts, images or reasoning."""

    def __init__(self, max_records: int = 500) -> None:
        self._records: deque[ModelCallRecord] = deque(maxlen=max_records)
        self._lock = RLock()

    def record(self, record: ModelCallRecord) -> None:
        with self._lock:
            self._records.append(record)

    def list(self) -> list[ModelCallRecord]:
        with self._lock:
            return list(self._records)

    @staticmethod
    def now() -> datetime:
        return datetime.now(UTC)
