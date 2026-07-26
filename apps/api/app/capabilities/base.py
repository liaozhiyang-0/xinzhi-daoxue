from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts.solver import AcademicProblem
from app.courses.base import BaseCoursePack


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    capability_id: str
    status: str
    result: dict[str, Any]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BaseCapability:
    """Reusable professional ability; it is not an autonomous Agent."""

    capability_id: str
    display_name: str
    tool_ids: tuple[str, ...] = ()

    def supports(self, problem: AcademicProblem, course_pack: BaseCoursePack) -> bool:
        return self.capability_id in course_pack.supported_capabilities

    def validate_input(self, problem: AcademicProblem) -> list[str]:
        return [] if problem.problem_text.strip() else ["problem_text_missing"]

    def summarize_result(self, result: CapabilityResult) -> dict[str, Any]:
        return {
            "capability_id": result.capability_id,
            "status": result.status,
            "warnings": list(result.warnings),
        }
