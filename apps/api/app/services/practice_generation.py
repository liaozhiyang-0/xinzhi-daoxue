from __future__ import annotations

import re

from app.contracts.learning import PracticeProblem

CIRCUIT_RE = re.compile(
    r"(?P<voltage>\d+(?:\.\d+)?)\s*V.*?(?P<resistance>\d+(?:\.\d+)?)\s*(?:Ω|欧)",
    re.IGNORECASE | re.DOTALL,
)


class PracticeGenerationService:
    """Produces only deterministic variants whose reference answer can be checked."""

    def generate(self, source_task_id: str, problem_text: str) -> PracticeProblem:
        match = CIRCUIT_RE.search(problem_text)
        if match is None:
            return PracticeProblem(
                status="unsupported",
                source_task_id=source_task_id,
                validation_checks=[
                    {
                        "check": "deterministic_solver_available",
                        "status": "failed",
                        "message": "当前题型不能在本地确定性生成唯一参考答案",
                    }
                ],
            )
        voltage = float(match.group("voltage")) + 2.0
        resistance = float(match.group("resistance")) + 1.0
        current = voltage / resistance
        problem = (
            f"理想 {voltage:g} V 电压源与 {resistance:g} Ω 电阻串联，"
            "求回路电流并写明单位。"
        )
        return PracticeProblem(
            status="ready",
            source_task_id=source_task_id,
            problem_text=problem,
            known_conditions=[
                {"name": "U", "value": voltage, "unit": "V"},
                {"name": "R", "value": resistance, "unit": "Ω"},
            ],
            target_quantities=[{"name": "I", "unit": "A"}],
            reference_answer={
                "value": round(current, 8),
                "unit": "A",
                "equation": "I=U/R",
            },
            validation_checks=[
                {"check": "condition_complete", "status": "passed"},
                {"check": "solvable", "status": "passed"},
                {"check": "unit_consistent", "status": "passed"},
                {"check": "unique_reference_answer", "status": "passed"},
            ],
        )
