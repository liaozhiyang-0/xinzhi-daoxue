from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.observability.model_tracer import ModelCallRecord, ModelTracer
from app.observability.tracer import TraceStore

SpanType = Literal[
    "ingress",
    "planning",
    "retrieval",
    "model",
    "tool",
    "verification",
    "presentation",
]
SpanStatus = Literal["completed", "failed", "running", "unknown"]

_SENSITIVE_KEYS = (
    "answer",
    "api_key",
    "base64",
    "content",
    "message",
    "password",
    "prompt",
    "question",
    "raw",
    "secret",
    "token",
)
_TOKEN_PATTERN = re.compile(r"(?i)(?:sk-|bearer\s+|api[_-]?key\s*[:=])\S+")


class TraceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    span_type: SpanType
    name: str
    status: SpanStatus
    start_time: datetime
    end_time: datetime
    duration_ms: int = Field(ge=0)
    provider: str = ""
    tool_id: str = ""
    error_code: str = ""
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)


class TraceProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    trace_id: str
    spans: list[TraceSpan] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TraceProjectionService:
    """Read-only projection of existing trace and model metadata."""

    def __init__(self, trace_store: TraceStore, model_tracer: ModelTracer) -> None:
        self.trace_store = trace_store
        self.model_tracer = model_tracer

    def project(self, trace_id: str) -> dict[str, Any] | None:
        record = self.trace_store.get(trace_id)
        if record is None:
            return None

        spans: list[TraceSpan] = []
        for node in record.get("nodes", []):
            if not isinstance(node, dict):
                continue
            span = self._node_span(trace_id, len(spans), node)
            if span is not None:
                spans.append(span)

        for model in self.model_tracer.list():
            if model.trace_id != trace_id:
                continue
            spans.append(self._model_span(trace_id, len(spans), model))

        projection = TraceProjection(
            trace_id=trace_id,
            spans=spans,
            warnings=[str(item) for item in record.get("warnings", [])][:32],
        )
        return projection.model_dump(mode="json")

    def _node_span(
        self, trace_id: str, index: int, node: dict[str, Any]
    ) -> TraceSpan | None:
        start_time = _parse_datetime(node.get("start_time"))
        end_time = _parse_datetime(node.get("end_time"))
        if start_time is None or end_time is None:
            return None
        duration_ms = max(0, _safe_int(node.get("elapsed_ms")))
        if duration_ms == 0:
            duration_ms = max(0, round((end_time - start_time).total_seconds() * 1000))
        name = str(node.get("node_name", "trace.node"))[:128]
        span_type = _span_type(name)
        return TraceSpan(
            trace_id=trace_id,
            span_id=f"{trace_id}:span:{index}",
            span_type=span_type,
            name=name,
            status=_status(node.get("status")),
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            provider=str(node.get("model_provider", ""))[:128],
            tool_id=_tool_id(node),
            error_code=str(node.get("error_type", ""))[:128],
            input_summary=_redact_summary(node.get("input_summary")),
            output_summary=_redact_summary(node.get("output_summary")),
        )

    @staticmethod
    def _model_span(
        trace_id: str, index: int, record: ModelCallRecord
    ) -> TraceSpan:
        start_time = record.start_time
        end_time = start_time + timedelta(milliseconds=record.elapsed_ms)
        return TraceSpan(
            trace_id=trace_id,
            span_id=f"{trace_id}:span:{index}",
            span_type="model",
            name=f"model.{record.task_type}"[:128],
            status="completed" if record.status == "completed" else "failed",
            start_time=start_time,
            end_time=end_time,
            duration_ms=record.elapsed_ms,
            provider=record.provider,
            error_code=record.error_type or "",
            input_summary={
                "request_id": record.request_id or "",
                "image_count": record.image_count,
            },
            output_summary={
                "model": record.model,
                "total_tokens": record.total_tokens,
                "fallback_used": record.fallback_used,
            },
        )


def _span_type(name: str) -> SpanType:
    value = name.casefold()
    if any(marker in value for marker in ("retrieve", "rag", "knowledge", "evidence")):
        return "retrieval"
    if any(marker in value for marker in ("model", "generate", "llm")):
        return "model"
    if any(marker in value for marker in ("tool", "calculate", "circuit")):
        return "tool"
    if any(marker in value for marker in ("verify", "review", "check", "quality")):
        return "verification"
    if any(marker in value for marker in ("present", "format", "result", "answer")):
        return "presentation"
    if any(marker in value for marker in ("plan", "route", "select", "intent")):
        return "planning"
    return "ingress"


def _status(value: Any) -> SpanStatus:
    normalized = str(getattr(value, "value", value) or "").casefold()
    if normalized in {"success", "succeeded", "completed"}:
        return "completed"
    if normalized in {"failed", "error"}:
        return "failed"
    if normalized in {"running", "started"}:
        return "running"
    return "unknown"


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _tool_id(node: dict[str, Any]) -> str:
    value = node.get("tool_id")
    if isinstance(value, str) and value:
        return value[:128]
    output = node.get("output_summary")
    if isinstance(output, dict) and isinstance(output.get("tool_id"), str):
        return str(output["tool_id"])[:128]
    return ""


def _redact_summary(value: Any) -> dict[str, Any]:
    result = _redact(value, depth=0)
    return result if isinstance(result, dict) else {}


def _redact(value: Any, *, depth: int) -> Any:
    if depth > 3:
        return "[redacted]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:32]:
            name = str(key)
            if any(marker in name.casefold() for marker in _SENSITIVE_KEYS):
                continue
            result[name[:96]] = _redact(item, depth=depth + 1)
        return result
    if isinstance(value, list):
        return [_redact(item, depth=depth + 1) for item in value[:32]]
    if isinstance(value, str):
        if _TOKEN_PATTERN.search(value):
            return "[redacted]"
        return value[:240]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:240]
