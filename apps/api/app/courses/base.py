from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.contracts.solver import AcademicProblem, AcademicSolutionResult


@dataclass(frozen=True, slots=True)
class CourseFallbackConfig:
    target_agent_id: str | None = None
    enabled: bool = False
    trigger_paths: frozenset[str] = frozenset({"HIGH_RISK", "FALLBACK"})


@dataclass(frozen=True, slots=True)
class BaseCoursePack:
    """Declarative course policy. Course packs never call a model or Provider."""

    course_code: str
    display_name: str
    supported_problem_types: tuple[str, ...]
    supported_capabilities: tuple[str, ...]
    topic_keywords: dict[str, tuple[str, ...]] = field(default_factory=dict)
    verification_rules: tuple[str, ...] = ()
    fallback: CourseFallbackConfig = CourseFallbackConfig()
    implementation_status: str = "skeleton"

    def normalize_problem(self, problem: AcademicProblem) -> AcademicProblem:
        return problem.model_copy(update={"course": self.course_code})

    def classify_problem_type(self, problem: AcademicProblem) -> str:
        text = problem.problem_text.casefold()
        for problem_type, keywords in self.topic_keywords.items():
            if any(keyword.casefold() in text for keyword in keywords):
                return problem_type
        return problem.problem_type or "general"

    def select_capabilities(self, problem: AcademicProblem) -> list[str]:
        requested = set(problem.required_capabilities)
        if requested:
            return [item for item in self.supported_capabilities if item in requested]
        return list(self.supported_capabilities)

    def build_extraction_prompt(self, problem: AcademicProblem) -> str:
        return f"按{self.display_name}规则提取已知量、目标量、实体、关系与参考约定。"

    def build_planning_prompt(self, problem: AcademicProblem) -> str:
        return f"使用{self.display_name}课程规则规划，不补造题目未给出的事实。"

    def build_solving_prompt(self, problem: AcademicProblem) -> str:
        return f"求解{self.classify_problem_type(problem)}并保留可核验的关键方程。"

    def build_verification_prompt(self, problem: AcademicProblem) -> str:
        return "只报告错误类型、位置、修正指令和置信度，不重新生成整份答案。"

    def validate_structured_problem(self, problem: AcademicProblem) -> list[str]:
        errors: list[str] = []
        if not problem.problem_text.strip():
            errors.append("problem_text_missing")
        return errors

    def validate_solution(self, result: AcademicSolutionResult) -> list[str]:
        return [] if result.final_answer.strip() else ["final_answer_missing"]

    def format_answer(self, result: AcademicSolutionResult) -> str:
        return result.final_answer

    def get_fallback_config(self, _problem: AcademicProblem) -> CourseFallbackConfig:
        return self.fallback

    def summary(self) -> dict[str, Any]:
        return {
            "course_code": self.course_code,
            "display_name": self.display_name,
            "implementation_status": self.implementation_status,
            "supported_problem_types": list(self.supported_problem_types),
            "supported_capabilities": list(self.supported_capabilities),
            "verification_rules": list(self.verification_rules),
            "fallback_agent_id": self.fallback.target_agent_id,
        }
