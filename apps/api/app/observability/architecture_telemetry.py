from __future__ import annotations

from threading import Lock

ARCHITECTURE_COUNTERS = (
    "taskrouter_final_route_count",
    "overall_router_rewrite_count",
    "planner_shadow_count",
    "planner_controlled_count",
    "planner_active_count",
    "legacy_runtime_invocation_count",
    "fixed_agent_route_count",
    "fallback_route_count",
)


class ArchitectureTelemetry:
    """Small process-local counter set for control-plane migration gates."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._values = {name: 0 for name in ARCHITECTURE_COUNTERS}

    def increment(self, name: str, amount: int = 1) -> None:
        if name not in self._values:
            raise KeyError(f"unknown architecture counter: {name}")
        with self._lock:
            self._values[name] += amount

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._values)

    def reset(self) -> None:
        with self._lock:
            for name in self._values:
                self._values[name] = 0


architecture_telemetry = ArchitectureTelemetry()
