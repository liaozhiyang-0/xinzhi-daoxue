"""Runtime adapter for the unified academic solver.

The adapter owns durable observe/retrieve/act/verify control while delegating
the actual solver graph to ``InternalAgentExecutionService``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.contracts import AgentRequest
from app.services.academic_solver_service import AcademicProblemSolverService
from app.services.circuit_visualization import extract_circuit_ir
from app.services.general_question_runtime import GeneralQuestionRuntimeService
from app.services.solver_boundary_policy import SolverBoundaryPolicy


class AcademicSolverRuntimeService(GeneralQuestionRuntimeService):
    """Expose the existing solver as an explicit Runtime action boundary."""

    agent_id = "ACADEMIC_PROBLEM_SOLVER"
    observe_node_id = "solver.observe"
    retrieve_node_id = "solver.retrieve"
    tool_node_id = "solver.tool"
    execute_node_id = "solver.execute"
    verify_node_id = "solver.verify"
    runtime_option_key = "academic_solver_runtime"
    runtime_plan_prefix = "academic-solver-runtime"
    runtime_plan_version = "solver-runtime-v1"
    runtime_name = "academic_solver"
    observe_handler_id = "academic.solver.observe"
    retrieve_handler_id = "academic.solver.retrieve"
    tool_handler_prefix = "academic.solver.tool"
    execute_handler_id = "academic.solver.execute"
    verify_handler_id = "academic.solver.verify"
    # Keep the frozen solver action on its existing Provider-style adapter
    # until its real paired parity corpus is approved for migration.
    use_typed_subagent = False

    @classmethod
    def _requested_tool_id(cls, request: AgentRequest) -> str:
        requested = super()._requested_tool_id(request)
        if requested:
            return requested
        if extract_circuit_ir(request) is None:
            return ""
        snapshot = request.options.get("_planner_snapshot")
        canonical = request.options.get("_canonical_plan")
        if not isinstance(canonical, Mapping) and isinstance(snapshot, Mapping):
            canonical = snapshot.get("canonical_plan")
        decision = (
            canonical.get("circuit_visualization")
            if isinstance(canonical, Mapping)
            else None
        )
        if not isinstance(decision, Mapping):
            return ""
        if (
            decision.get("feature_mode") == "controlled"
            and decision.get("decision") in {"OPTIONAL", "REQUIRED"}
            and not decision.get("blocked", False)
        ):
            return "circuit.render"
        return ""

    @staticmethod
    def _question(request: AgentRequest) -> str:
        return next(
            (
                str(request.canonical_input[key]).strip()
                for key in (
                    "text",
                    "question",
                    "problem",
                    "query",
                    "prompt",
                )
                if request.canonical_input.get(key)
            ),
            "academic problem",
        )

    @classmethod
    def _retrieval_requested(cls, request: AgentRequest) -> bool:
        runtime_options = request.options.get(cls.runtime_option_key)
        if isinstance(runtime_options, Mapping) and "retrieve" in runtime_options:
            requested = runtime_options.get("retrieve") is True
        else:
            execution_plan = request.options.get("_execution_plan")
            requested = isinstance(execution_plan, Mapping) and bool(
                execution_plan.get("use_rag", False)
            )
        if not requested:
            return False

        # The solver has a deterministic boundary policy.  Do not spend a
        # retrieval call on a problem that policy will intercept before any
        # answer generation.
        problem = AcademicProblemSolverService._problem_from_request(request)
        return not SolverBoundaryPolicy().evaluate(problem).intercepted

    @classmethod
    def _retrieval_must_precede_execution(cls, request: AgentRequest) -> bool:
        """Only serialize when user-provided material must reach the model."""

        extracted = request.options.get("_material_extraction", {})
        explicit_materials = (
            isinstance(extracted, Mapping)
            and isinstance(extracted.get("materials"), Mapping)
            and bool(extracted.get("materials"))
        )
        return bool(request.attachments or request.context_refs or explicit_materials)

    def _provider_context(
        self, context: Any, retrieved_context: Any = None
    ) -> Any:
        return retrieved_context if retrieved_context is not None else context
