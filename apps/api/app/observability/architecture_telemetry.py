from __future__ import annotations

from threading import Lock

ARCHITECTURE_COUNTERS = (
    "taskrouter_final_route_count",
    "overall_router_rewrite_count",
    "planner_shadow_count",
    "planner_controlled_count",
    "planner_active_count",
    "legacy_runtime_invocation_count",
    "legacy_router_invocation_count",
    "legacy_handler_invocation_count",
    "legacy_plan_creation_count",
    "legacy_checkpoint_execution_count",
    "shadow_result_mutation_count",
    "execution_target_not_active_count",
    "stale_task_rejected_count",
    "compatibility_read_count",
    "startup_fingerprint_mismatch_count",
    "registry_drift_count",
    "fixed_agent_route_count",
    "fallback_route_count",
    "circuit_decision_total",
    "circuit_decision_total_skip",
    "circuit_decision_total_optional",
    "circuit_decision_total_required",
    "circuit_render_total",
    "circuit_render_total_rendered",
    "circuit_render_total_degraded",
    "circuit_render_total_failed",
    "circuit_renderer_total",
    "circuit_renderer_total_professional_svg",
    "circuit_renderer_total_schemdraw",
    "circuit_renderer_total_fallback",
    "circuit_renderer_total_none",
    "circuit_validation_state_total",
    "circuit_validation_state_total_validated",
    "circuit_validation_state_total_partially_validated",
    "circuit_validation_state_total_needs_review",
    "circuit_validation_state_total_invalid",
    "circuit_nonfatal_failure_total",
    "multimodal_task_count",
    "unknown_image_role_count",
    "circuit_ir_requested_count",
    "circuit_ir_skipped_count",
    "circuit_ir_failure_count",
    "general_vision_count",
    "reused_multimodal_observation_count",
    "duplicate_vision_call_count",
    "image_role_count_text_screenshot",
    "image_role_count_problem_statement",
    "image_role_count_circuit_diagram",
    "image_role_count_student_solution",
    "image_role_count_table",
    "image_role_count_chart",
    "image_role_count_waveform",
    "image_role_count_formula",
    "image_role_count_document_page",
    "image_role_count_reference_image",
    "image_role_count_general_image",
    "image_role_count_unknown",
)

ARCHITECTURE_OBSERVATIONS = ("circuit_render_latency_ms",)


class ArchitectureTelemetry:
    """Small process-local counter set for control-plane migration gates."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._values: dict[str, int | float] = {
            name: 0 for name in (*ARCHITECTURE_COUNTERS, *ARCHITECTURE_OBSERVATIONS)
        }

    def increment(self, name: str, amount: int = 1) -> None:
        if name not in self._values:
            raise KeyError(f"unknown architecture counter: {name}")
        with self._lock:
            self._values[name] += amount

    def observe(self, name: str, value: float) -> None:
        if name not in ARCHITECTURE_OBSERVATIONS:
            raise KeyError(f"unknown architecture observation: {name}")
        with self._lock:
            self._values[name] += max(0.0, float(value))

    def snapshot(self) -> dict[str, int | float]:
        with self._lock:
            return dict(self._values)

    def reset(self) -> None:
        with self._lock:
            for name in self._values:
                self._values[name] = 0


architecture_telemetry = ArchitectureTelemetry()
