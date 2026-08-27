from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, MutableMapping
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any

RUNTIME_TIMING_KEY = "_runtime_timing"
RUNTIME_TIMING_SCHEMA = "runtime_timing.v1"
MAX_EVENTS = 256
MAX_FINGERPRINTS = 16


def _trace(options: MutableMapping[str, Any]) -> dict[str, Any] | None:
    value = options.get(RUNTIME_TIMING_KEY)
    return value if isinstance(value, dict) else None


class RuntimeTimingTrace:
    """Small request-local timing projection; never stores raw payloads."""

    @staticmethod
    def begin(
        options: MutableMapping[str, Any],
        *,
        task_id: str,
        request_id: str,
        trace_id: str,
    ) -> None:
        options[RUNTIME_TIMING_KEY] = {
            "schema_version": RUNTIME_TIMING_SCHEMA,
            "task_id": task_id,
            "request_id": request_id,
            "trace_id": trace_id,
            "run_id": "",
            "events": [],
            "stages": {},
            "fingerprints": {},
            "counters": {
                "model_call_count": 0,
                "tool_call_count": 0,
                "rag_call_count": 0,
                "retry_count": 0,
                "fallback_count": 0,
            },
        }
        RuntimeTimingTrace.mark(options, "request_received")

    @staticmethod
    def set_run_id(options: MutableMapping[str, Any], run_id: str) -> None:
        trace = _trace(options)
        if trace is not None:
            trace["run_id"] = str(run_id)[:128]

    @staticmethod
    def mark(
        options: MutableMapping[str, Any],
        event: str,
        *,
        duration_ms: float | int | None = None,
        details: dict[str, Any] | None = None,
        at: datetime | None = None,
    ) -> None:
        trace = _trace(options)
        if trace is None:
            return
        item: dict[str, Any] = {
            "event": str(event)[:96],
            "at": (at or datetime.now(UTC)).astimezone(UTC).isoformat(),
        }
        if duration_ms is not None:
            item["duration_ms"] = round(max(0.0, float(duration_ms)), 3)
        if details:
            item["details"] = {
                str(key)[:64]: str(value)[:160]
                for key, value in list(details.items())[:8]
            }
        events = trace.setdefault("events", [])
        if isinstance(events, list):
            events.append(item)
            del events[:-MAX_EVENTS]

    @staticmethod
    def observe(
        options: MutableMapping[str, Any],
        stage: str,
        duration_ms: float | int,
        *,
        at: datetime | None = None,
        details: dict[str, Any] | None = None,
        outcome: str = "completed",
    ) -> None:
        trace = _trace(options)
        if trace is None:
            return
        name = str(stage)[:96]
        stages = trace.setdefault("stages", {})
        if not isinstance(stages, dict):
            return
        current = stages.get(name)
        if not isinstance(current, dict):
            current = {"duration_ms": 0.0, "count": 0}
            stages[name] = current
        current["duration_ms"] = round(
            float(current.get("duration_ms", 0.0)) + max(0.0, float(duration_ms)),
            3,
        )
        current["count"] = int(current.get("count", 0)) + 1
        current["outcome"] = str(outcome)[:32] or "completed"
        RuntimeTimingTrace.mark(
            options,
            f"{name}_end",
            duration_ms=duration_ms,
            details=details,
            at=at,
        )

    @staticmethod
    def record_model_calls(
        options: MutableMapping[str, Any], records: list[Any]
    ) -> int:
        """Project bounded model-call metadata into the request trace."""

        recorded = 0
        for index, record in enumerate(records, 1):
            values = (
                record.model_dump(mode="json")
                if hasattr(record, "model_dump")
                else record
            )
            if not isinstance(values, dict):
                continue
            start = values.get("start_time")
            try:
                started_at = datetime.fromisoformat(str(start))
            except ValueError:
                started_at = datetime.now(UTC)
            elapsed = max(0, int(values.get("elapsed_ms", 0) or 0))
            details = {
                "task_type": values.get("task_type", ""),
                "provider": values.get("provider", ""),
                "model": values.get("model", ""),
                "status": values.get("status", ""),
            }
            RuntimeTimingTrace.mark(
                options,
                f"model_call_{index}_start",
                details=details,
                at=started_at,
            )
            RuntimeTimingTrace.observe(
                options,
                f"model_call_{index}",
                elapsed,
                at=started_at + timedelta(milliseconds=elapsed),
                details=details,
                outcome=str(values.get("status") or "completed"),
            )
            RuntimeTimingTrace.increment(options, "model_call_count")
            retry_count = max(0, int(values.get("retry_count", 0) or 0))
            if retry_count:
                RuntimeTimingTrace.increment(options, "retry_count", retry_count)
                RuntimeTimingTrace.mark(
                    options,
                    "model_retry",
                    details={"retry_count": retry_count},
                    at=started_at,
                )
            if values.get("fallback_used") is True:
                RuntimeTimingTrace.increment(options, "fallback_count")
                RuntimeTimingTrace.mark(
                    options,
                    "model_fallback",
                    details={"task_type": values.get("task_type", "")},
                    at=started_at,
                )
            input_hash = values.get("input_hash")
            if input_hash:
                RuntimeTimingTrace.fingerprint(
                    options, f"model_input_hash_{index}", input_hash
                )
            recorded += 1
        return recorded

    @staticmethod
    def record_tool_nodes(
        options: MutableMapping[str, Any], runtime_run: Any
    ) -> int:
        """Record tool-node intervals without persisting node payloads."""

        plan = getattr(runtime_run, "plan", None)
        nodes = getattr(runtime_run, "nodes", {})
        plan_nodes = getattr(plan, "nodes", [])
        recorded = 0
        for node in plan_nodes:
            if str(getattr(node, "node_type", "")).casefold() != "tool":
                continue
            state = nodes.get(getattr(node, "node_id", ""))
            started_at = getattr(state, "started_at", None)
            completed_at = getattr(state, "completed_at", None)
            if started_at is None or completed_at is None:
                continue
            elapsed = max(0.0, (completed_at - started_at).total_seconds() * 1000)
            details = {
                "node_id": getattr(node, "node_id", ""),
                "handler_id": getattr(node, "handler_id", ""),
                "status": getattr(state, "status", ""),
            }
            RuntimeTimingTrace.mark(
                options, "tool_start", details=details, at=started_at
            )
            RuntimeTimingTrace.mark(
                options,
                "tool_end",
                duration_ms=elapsed,
                details=details,
                at=completed_at,
            )
            RuntimeTimingTrace.observe(options, "tool", elapsed)
            RuntimeTimingTrace.observe(
                options,
                "tool_execution",
                elapsed,
                outcome=str(getattr(state, "status", "completed") or "completed"),
            )
            recorded += 1
        return recorded

    @staticmethod
    def increment(
        options: MutableMapping[str, Any], name: str, amount: int = 1
    ) -> None:
        trace = _trace(options)
        if trace is None:
            return
        counters = trace.setdefault("counters", {})
        if isinstance(counters, dict):
            counters[name] = max(0, int(counters.get(name, 0)) + amount)

    @staticmethod
    def fingerprint(
        options: MutableMapping[str, Any], name: str, value: Any
    ) -> None:
        trace = _trace(options)
        if trace is None:
            return
        fingerprints = trace.setdefault("fingerprints", {})
        if not isinstance(fingerprints, dict) or (
            name not in fingerprints and len(fingerprints) >= MAX_FINGERPRINTS
        ):
            return
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        fingerprints[str(name)[:96]] = hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def record_context_usage(
        options: MutableMapping[str, Any],
        *,
        system_prompt_chars: int | None = None,
        conversation_chars: int | None = None,
        memory_chars: int | None = None,
        rag_chars: int | None = None,
        attachment_chars: int | None = None,
        tool_chars: int | None = None,
    ) -> None:
        """Record numeric context-size telemetry without retaining text."""

        trace = _trace(options)
        if trace is None:
            return
        previous = trace.get("context_usage", {})
        previous = previous if isinstance(previous, dict) else {}
        supplied = {
            "system_prompt_chars": system_prompt_chars,
            "conversation_chars": conversation_chars,
            "memory_chars": memory_chars,
            "rag_chars": rag_chars,
            "attachment_chars": attachment_chars,
            "tool_chars": tool_chars,
        }
        values = {
            key: max(0, int(value if value is not None else previous.get(key, 0)))
            for key, value in supplied.items()
        }
        values["total_context_chars"] = sum(values.values())
        trace["context_usage"] = values

    @staticmethod
    def snapshot(options: MutableMapping[str, Any]) -> dict[str, Any]:
        trace = _trace(options)
        if trace is None:
            return {}
        return {
            "schema_version": RUNTIME_TIMING_SCHEMA,
            "task_id": str(trace.get("task_id", "")),
            "request_id": str(trace.get("request_id", "")),
            "trace_id": str(trace.get("trace_id", "")),
            "run_id": str(trace.get("run_id", "")),
            "events": list(trace.get("events", []))[-MAX_EVENTS:],
            "stages": dict(trace.get("stages", {})),
            "fingerprints": dict(trace.get("fingerprints", {})),
            "counters": dict(trace.get("counters", {})),
            "context_usage": dict(trace.get("context_usage", {})),
        }


@contextmanager
def timed_stage(options: MutableMapping[str, Any], stage: str) -> Iterator[None]:
    RuntimeTimingTrace.mark(options, f"{stage}_start")
    started = perf_counter()
    outcome = "completed"
    try:
        yield
    except BaseException:
        outcome = "failed"
        raise
    finally:
        RuntimeTimingTrace.observe(
            options,
            stage,
            (perf_counter() - started) * 1000,
            outcome=outcome,
        )
