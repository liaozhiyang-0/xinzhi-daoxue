from __future__ import annotations

from time import perf_counter

from app.contracts import (
    StudentAttempt,
    TeachingExecutionPath,
    TeachingExecutionPlanV1,
    TeachingMode,
    TeachingStateV1,
)

SUPPORTED_TEACHING_COURSES = frozenset({"CT", "AE", "DE"})


class TeachingExecutionPlanner:
    """Deterministic teaching-path planning with no Provider calls."""

    def plan(
        self,
        *,
        mode: TeachingMode,
        course_id: str,
        attempt: StudentAttempt | None,
        reusable_solution_packet: bool,
        state: TeachingStateV1 | None = None,
        original_model_call_budget: int = 1,
    ) -> tuple[TeachingExecutionPlanV1, float]:
        started = perf_counter()
        warnings: list[str] = []
        supported = course_id.upper() in SUPPORTED_TEACHING_COURSES
        if not supported and mode != TeachingMode.DIRECT_ANSWER:
            warnings.append(
                f"teaching diagnosis unavailable for course {course_id.upper()}"
            )
        if mode == TeachingMode.DIRECT_ANSWER:
            plan = TeachingExecutionPlanV1(
                path=TeachingExecutionPath.DIRECT,
                require_solver=not reusable_solution_packet,
                reuse_solution_packet=reusable_solution_packet,
                require_student_verification=False,
                require_hint=False,
                require_next_check=False,
                maximum_disclosure_level="H5",
                model_call_budget=max(0, original_model_call_budget),
                warnings=warnings,
            )
        elif mode == TeachingMode.GUIDED_LEARNING:
            plan = TeachingExecutionPlanV1(
                path=TeachingExecutionPath.GUIDED,
                require_solver=not reusable_solution_packet,
                reuse_solution_packet=reusable_solution_packet,
                require_student_verification=False,
                require_hint=True,
                require_next_check=True,
                maximum_disclosure_level="H2",
                model_call_budget=0,
                warnings=warnings,
            )
        elif mode == TeachingMode.CHECK_MY_WORK:
            if attempt is None:
                warnings.append("check_my_work requires StudentAttempt")
            plan = TeachingExecutionPlanV1(
                path=TeachingExecutionPath.CHECK,
                require_solver=not reusable_solution_packet,
                reuse_solution_packet=reusable_solution_packet,
                require_student_verification=True,
                require_hint=True,
                require_next_check=True,
                maximum_disclosure_level="H2",
                model_call_budget=0,
                warnings=warnings,
            )
        else:
            warnings.append("review remains foundation_only")
            plan = TeachingExecutionPlanV1(
                path=TeachingExecutionPath.DIRECT,
                require_solver=not reusable_solution_packet,
                reuse_solution_packet=reusable_solution_packet,
                require_student_verification=False,
                require_hint=False,
                require_next_check=False,
                maximum_disclosure_level="H5",
                model_call_budget=0,
                warnings=warnings,
            )
        if state and state.solution_packet_task_id:
            plan.warnings.append("existing teaching state detected")
        return plan, (perf_counter() - started) * 1000
