from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from time import perf_counter

from app.contracts.solver import (
    AcademicProblem,
    FallbackReason,
    ProblemComplexity,
    SolverTaskMode,
)

_SUBQUESTION_PATTERN = re.compile(
    r"(?:^|[\s;；])[\(（]\s*\d+\s*[\)）]"
    r"|[①②③④⑤⑥]"
    r"|(?:^|\n)\s*\d+\s*[.、]",
)
_SYNTHESIS_PATTERN = re.compile(
    r"设计|实现|状态转换图|幅度频谱|级联结构|并联结构|"
    r"傅里叶(?:逆)?变换|滤波器",
)
_MATH_FEATURE_PATTERN = re.compile(
    r"\\(?:frac|sum|int|omega|mathrm|operatorname|left|right)|\^|_\{",
)


@dataclass(slots=True)
class RequestTimeBudget:
    """Monotonic request budget used to stop optional solver work early."""

    soft_deadline_seconds: float = 140
    finalization_deadline_seconds: float = 165
    hard_deadline_seconds: float = 175
    started_at: float = field(default_factory=perf_counter)
    clock: Callable[[], float] = field(default=perf_counter, repr=False)

    def __post_init__(self) -> None:
        if not (
            0
            < self.soft_deadline_seconds
            <= self.finalization_deadline_seconds
            <= self.hard_deadline_seconds
        ):
            raise ValueError(
                "solver deadlines must satisfy soft <= finalization <= hard"
            )

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, self.clock() - self.started_at)

    def remaining_ms(self, stage: str = "hard") -> int:
        deadline = {
            "soft": self.soft_deadline_seconds,
            "finalization": self.finalization_deadline_seconds,
            "hard": self.hard_deadline_seconds,
        }[stage]
        return max(0, int((deadline - self.elapsed_seconds) * 1000))

    @property
    def soft_exhausted(self) -> bool:
        return self.remaining_ms("soft") == 0

    @property
    def finalization_required(self) -> bool:
        return self.remaining_ms("finalization") == 0

    @property
    def hard_exhausted(self) -> bool:
        return self.remaining_ms("hard") == 0

    def can_start_optional_call(self, *, minimum_remaining_ms: int = 5_000) -> bool:
        return (
            not self.soft_exhausted
            and self.remaining_ms("finalization") >= minimum_remaining_ms
        )

    def call_timeout_seconds(
        self,
        configured_timeout: float,
        *,
        reserve_for_finalization_seconds: float = 3,
    ) -> float:
        available = max(
            0.05,
            self.remaining_ms("hard") / 1000 - reserve_for_finalization_seconds,
        )
        return min(configured_timeout, available)


class SolverRuntimePolicy:
    """Rule-only complexity and conditional verification policy."""

    @staticmethod
    def text_complexity_signals(problem_text: str) -> list[str]:
        signals: list[str] = []
        if len(problem_text) >= 600:
            signals.append("long_problem_text")
        if len(_SUBQUESTION_PATTERN.findall(problem_text)) >= 3:
            signals.append("multi_part_problem")
        if len(problem_text) >= 24 and _SYNTHESIS_PATTERN.search(problem_text):
            signals.append("synthesis_or_transform_problem")
        if len(_MATH_FEATURE_PATTERN.findall(problem_text)) >= 6:
            signals.append("dense_math_notation")
        return signals

    @staticmethod
    def classify(problem: AcademicProblem) -> ProblemComplexity:
        if (
            problem.source_conflicts
            or problem.extraction_confidence < 0.55
            or len(problem.figures_given) > 1
        ):
            return ProblemComplexity.HIGH_RISK
        if problem.figures_given:
            return ProblemComplexity.COMPLEX
        if SolverRuntimePolicy.text_complexity_signals(problem.problem_text):
            return ProblemComplexity.COMPLEX
        if problem.code_given or problem.tables_given:
            return ProblemComplexity.COMPLEX
        feature_score = 0
        feature_score += 1 if len(problem.equations_given) >= 4 else 0
        feature_score += 1 if len(problem.target_quantities) >= 3 else 0
        if feature_score >= 3:
            return ProblemComplexity.COMPLEX
        if (
            len(problem.problem_text) <= 350
            and len(problem.equations_given) <= 2
            and not problem.figures_given
            and not problem.uncertain_info
        ):
            return ProblemComplexity.SIMPLE
        return ProblemComplexity.MEDIUM

    @staticmethod
    def uses_extended_time_budget(complexity: ProblemComplexity) -> bool:
        return complexity in {
            ProblemComplexity.COMPLEX,
            ProblemComplexity.HIGH_RISK,
        }

    @staticmethod
    def model_call_budget(
        complexity: ProblemComplexity,
        *,
        task_mode: SolverTaskMode,
    ) -> int:
        if task_mode == SolverTaskMode.VERIFY:
            return 1
        return {
            ProblemComplexity.SIMPLE: 1,
            ProblemComplexity.MEDIUM: 2,
            ProblemComplexity.COMPLEX: 3,
            ProblemComplexity.HIGH_RISK: 3,
        }[complexity]

    @staticmethod
    def verification_reason(
        problem: AcademicProblem,
        *,
        complexity: ProblemComplexity,
        confidence: float,
        professional_conflicts: bool,
        explicitly_requested: bool,
    ) -> str | None:
        if explicitly_requested or problem.task_mode == SolverTaskMode.VERIFY:
            return "user_requested"
        if professional_conflicts:
            return "professional_validation_conflict"
        if complexity in {
            ProblemComplexity.COMPLEX,
            ProblemComplexity.HIGH_RISK,
        }:
            return f"complexity_{complexity.value}"
        if confidence < 0.6:
            return "low_confidence"
        if problem.uncertain_info or problem.source_conflicts:
            return "uncertain_structured_input"
        return None


@dataclass(slots=True)
class FallbackTracker:
    """One-request fallback ledger with loop prevention."""

    max_fallbacks: int = 1
    count: int = 0
    route_path: list[str] = field(default_factory=list)
    reason: FallbackReason | None = None
    stage: str = ""

    def start(self, source_agent: str) -> None:
        if not self.route_path:
            self.route_path.append(source_agent)

    def request(
        self,
        *,
        source_agent: str,
        target_agent: str,
        reason: FallbackReason,
        stage: str,
    ) -> bool:
        self.start(source_agent)
        if (
            self.count >= self.max_fallbacks
            or target_agent in self.route_path
            or source_agent != self.route_path[-1]
        ):
            return False
        self.count += 1
        self.reason = reason
        self.stage = stage
        self.route_path.append(target_agent)
        return True
