from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.capabilities import default_capability_registry
from app.contracts.solver import AcademicProblem
from app.courses import default_course_registry
from app.orchestrator.graphs import AcademicProblemSolverGraph
from app.tools import ToolRegistry, default_tool_registry


class CircuitProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_source: str = "text"
    user_intent: str = "solve_problem"
    course: str = "CT"
    chapter: str = ""
    problem_text: str
    known_conditions: list[str] = Field(default_factory=list)
    target_quantities: list[str] = Field(default_factory=list)
    components: list[dict[str, Any]] = Field(default_factory=list)
    circuit_relations: list[str] = Field(default_factory=list)
    reference_directions: list[str] = Field(default_factory=list)
    source_conflicts: list[str] = Field(default_factory=list)
    uncertain_info: list[str] = Field(default_factory=list)
    critical_missing_info: list[str] = Field(default_factory=list)
    retrieval_keywords: list[str] = Field(default_factory=list)
    structure_status: str = "partial"
    can_continue: bool = True
    extraction_confidence: float = Field(default=0, ge=0, le=1)


class SolverExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Literal["fast", "full", "blocked"]
    status: Literal["success", "partial", "failed"]
    answer_text: str
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)


class LocalCircuitSolverGraph:
    """Deprecated CT compatibility adapter over AcademicProblemSolverGraph."""

    def __init__(self, tools: ToolRegistry | None = None) -> None:
        self.tools = tools or default_tool_registry()
        self.graph = AcademicProblemSolverGraph(
            default_course_registry(), default_capability_registry(), self.tools
        )

    def run(self, problem: CircuitProblem) -> SolverExecution:
        academic = AcademicProblem(
            input_source=problem.input_source,
            user_intent=problem.user_intent,
            course="CT",
            chapter=problem.chapter or None,
            problem_text=problem.problem_text,
            known_conditions=[{"value": item} for item in problem.known_conditions],
            target_quantities=[{"name": item} for item in problem.target_quantities],
            entities=list(problem.components),
            relations=[{"equation": item} for item in problem.circuit_relations],
            reference_conventions=[
                {"description": item} for item in problem.reference_directions
            ],
            equations_given=list(problem.circuit_relations),
            source_conflicts=[
                {"description": item} for item in problem.source_conflicts
            ],
            uncertain_info=[{"description": item} for item in problem.uncertain_info],
            critical_missing_info=[
                {"field": item} for item in problem.critical_missing_info
            ],
            retrieval_keywords=problem.retrieval_keywords,
            structure_status=problem.structure_status,
            can_continue=problem.can_continue,
            extraction_confidence=problem.extraction_confidence,
        )
        result = self.graph.run(academic)
        path: Literal["fast", "full", "blocked"] = (
            "blocked"
            if problem.critical_missing_info or not problem.can_continue
            else "fast"
            if result.execution_path == "FAST"
            else "full"
        )
        tool_results = [
            {
                "tool": (
                    "sympy_solver"
                    if item["tool_id"] == "linear_equation_solver"
                    else item["tool_id"]
                ),
                "status": item["status"],
                "result": item.get("result", {}),
            }
            for item in result.tool_verification
        ]
        return SolverExecution(
            path=path,
            status="success" if result.status == "success" else "partial",
            answer_text=result.final_answer,
            warnings=[
                *(["未擅自补充元件参数、拓扑或参考方向"] if path == "blocked" else []),
                *result.remaining_risks,
            ],
            tool_results=tool_results,
        )
