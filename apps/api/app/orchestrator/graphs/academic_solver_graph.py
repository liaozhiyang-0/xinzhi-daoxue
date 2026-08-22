from __future__ import annotations

import asyncio
from collections.abc import Hashable, Sequence
from time import perf_counter
from typing import Any, Literal, cast
from uuid import uuid4

from app.capabilities import CapabilityRegistry
from app.contracts.solver import AcademicProblem, AcademicSolutionResult, ToolResult
from app.courses import CourseRegistry
from app.orchestrator.state import XZDGraphState
from app.services.high_risk_verification import HighRiskVerificationService
from app.services.solver_quality_gate import SolverQualityGateService
from app.tools import ToolRegistry

ExecutionPath = Literal["FAST", "STANDARD", "HIGH_RISK", "CONDITIONAL", "FALLBACK"]


class GraphInterruptedError(RuntimeError):
    """Raised when a caller asks the graph to pause before a named node."""

    def __init__(self, state: dict[str, Any]) -> None:
        super().__init__("academic solver graph interrupted before completion")
        self.state = state


class AcademicProblemSolverGraph:
    """One bounded academic-solving graph shared by every course pack.

    Nodes contain orchestration only. Parsing, retrieval, model calls, and
    deterministic computation remain injectable services/tools.
    """

    graph_name = "academic_problem_solver"
    node_names = (
        "normalize_problem_input",
        "resolve_course_pack",
        "multimodal_extraction_if_needed",
        "structure_problem",
        "check_problem_quality",
        "assess_solvability",
        "classify_problem_type",
        "select_capabilities",
        "retrieve_domain_knowledge",
        "select_execution_path",
        "fast_generate_solution",
        "lightweight_validation",
        "plan_solution",
        "standard_generate_solution",
        "execute_tools",
        "verify_solution",
        "correct_if_needed",
        "multi_stage_planning",
        "primary_solution",
        "deterministic_tools",
        "secondary_model_review",
        "conflict_resolution",
        "final_correction",
        "conditional_solution",
        "fallback_selection",
        "generate_learning_feedback",
        "format_course_answer",
        "finalize_solver_response",
    )

    def __init__(
        self,
        courses: CourseRegistry,
        capabilities: CapabilityRegistry,
        tools: ToolRegistry,
        *,
        checkpointer: Any = None,
    ) -> None:
        self.courses = courses
        self.capabilities = capabilities
        self.tools = tools
        self.checkpointer = checkpointer
        self.high_risk_verifier = HighRiskVerificationService()
        self.quality_gate = SolverQualityGateService()
        self._compiled = self._compile_langgraph()

    def run(
        self,
        problem: AcademicProblem,
        *,
        retrieved_chunks: list[dict[str, Any]] | None = None,
        state: XZDGraphState | None = None,
        thread_id: str | None = None,
    ) -> AcademicSolutionResult:
        completed = self.invoke_state(
            problem,
            retrieved_chunks=retrieved_chunks,
            state=state,
            thread_id=thread_id,
        )
        return self._result_from_state(completed)

    async def arun(
        self,
        problem: AcademicProblem,
        *,
        retrieved_chunks: list[dict[str, Any]] | None = None,
        state: XZDGraphState | None = None,
        thread_id: str | None = None,
    ) -> AcademicSolutionResult:
        """Run the graph without blocking the RuntimeTaskEngine event loop."""

        completed = await self.ainvoke_state(
            problem,
            retrieved_chunks=retrieved_chunks,
            state=state,
            thread_id=thread_id,
        )
        return self._result_from_state(completed)

    def invoke_state(
        self,
        problem: AcademicProblem,
        *,
        retrieved_chunks: list[dict[str, Any]] | None = None,
        state: XZDGraphState | None = None,
        thread_id: str | None = None,
        interrupt_before: Sequence[str] = (),
    ) -> dict[str, Any]:
        """Invoke and return the resumable state, including interrupt metadata."""

        if self._compiled is None:
            result = self._run_impl(
                problem, retrieved_chunks=retrieved_chunks, state=state
            )
            return dict(state or {}, structured_result=result.model_dump(mode="json"))
        if interrupt_before and self.checkpointer is None:
            raise RuntimeError("interrupt_before requires a configured checkpointer")
        graph_state = self._input_state(problem, retrieved_chunks, state)
        completed = self._compiled.invoke(
            graph_state,
            config=self._graph_config(thread_id or graph_state.get("thread_id")),
            interrupt_before=list(interrupt_before) or None,
        )
        self._merge_state(state, completed)
        return dict(completed)

    async def ainvoke_state(
        self,
        problem: AcademicProblem,
        *,
        retrieved_chunks: list[dict[str, Any]] | None = None,
        state: XZDGraphState | None = None,
        thread_id: str | None = None,
        interrupt_before: Sequence[str] = (),
    ) -> dict[str, Any]:
        """Async counterpart used by the non-blocking task execution path."""

        if self._compiled is None:
            return await asyncio.to_thread(
                self.invoke_state,
                problem,
                retrieved_chunks=retrieved_chunks,
                state=state,
                thread_id=thread_id,
                interrupt_before=interrupt_before,
            )
        if interrupt_before and self.checkpointer is None:
            raise RuntimeError("interrupt_before requires a configured checkpointer")
        graph_state = self._input_state(problem, retrieved_chunks, state)
        completed = await self._compiled.ainvoke(
            graph_state,
            config=self._graph_config(thread_id or graph_state.get("thread_id")),
            interrupt_before=list(interrupt_before) or None,
        )
        self._merge_state(state, completed)
        return dict(completed)

    def resume_state(
        self,
        *,
        thread_id: str,
        resume: Any = None,
        interrupt_before: Sequence[str] = (),
    ) -> dict[str, Any]:
        """Resume a checkpointed graph after an interrupt."""

        if self._compiled is None or self.checkpointer is None:
            raise RuntimeError("resume_state requires LangGraph checkpoint support")
        from langgraph.types import Command

        command: Any = Command(resume=resume) if resume is not None else None
        completed = self._compiled.invoke(
            command,
            config=self._graph_config(thread_id),
            interrupt_before=list(interrupt_before) or None,
        )
        return dict(completed)

    def checkpoint_state(self, *, thread_id: str) -> dict[str, Any]:
        """Return the last checkpoint metadata needed by a resume UI/worker."""

        if self._compiled is None or self.checkpointer is None:
            raise RuntimeError("checkpoint_state requires LangGraph checkpoint support")
        snapshot = self._compiled.get_state(self._graph_config(thread_id))
        return {
            "values": dict(snapshot.values),
            "next": list(snapshot.next),
            "interrupts": list(snapshot.interrupts),
            "checkpoint_id": snapshot.config["configurable"].get("checkpoint_id"),
        }

    def _input_state(
        self,
        problem: AcademicProblem,
        retrieved_chunks: list[dict[str, Any]] | None,
        state: XZDGraphState | None,
    ) -> dict[str, Any]:
        graph_state: dict[str, Any] = dict(state or {})
        graph_state["structured_problem"] = problem.model_dump(mode="json")
        graph_state["retrieved_chunks"] = list(retrieved_chunks or [])
        graph_state.setdefault("thread_id", f"graph_{uuid4().hex}")
        return graph_state

    def _graph_config(self, thread_id: str | None) -> dict[str, Any] | None:
        if self.checkpointer is None:
            return None
        return {"configurable": {"thread_id": thread_id or f"graph_{uuid4().hex}"}}

    @staticmethod
    def _merge_state(
        state: XZDGraphState | None, completed: dict[str, Any]
    ) -> None:
        if state is None:
            return
        known_keys = XZDGraphState.__annotations__
        state.update(
            cast(
                Any,
                {
                    key: value for key, value in completed.items() if key in known_keys
                },
            )
        )

    @staticmethod
    def _result_from_state(completed: dict[str, Any]) -> AcademicSolutionResult:
        structured_result = completed.get("structured_result")
        if not isinstance(structured_result, dict) or not structured_result:
            raise GraphInterruptedError(completed)
        return AcademicSolutionResult.model_validate(structured_result)

    def _run_impl(
        self,
        problem: AcademicProblem,
        *,
        retrieved_chunks: list[dict[str, Any]] | None = None,
        state: XZDGraphState | None = None,
    ) -> AcademicSolutionResult:
        prepared = bool(state and state.get("selected_course_pack"))
        if prepared:
            assert state is not None
            pack = self.courses.get(str(state["selected_course_pack"]))
            normalized = AcademicProblem.model_validate(state["structured_problem"])
            problem_type = str(state.get("problem_type") or "general")
            normalized = normalized.model_copy(update={"problem_type": problem_type})
            errors = [
                str(item.get("message", item))
                for item in state.get("errors", [])
                if isinstance(item, dict)
            ]
            selected_capabilities = list(state.get("selected_capabilities", []))
            selected_tools = list(state.get("selected_tools", []))
            path_value = str(state.get("execution_path") or "CONDITIONAL")
            path = cast(ExecutionPath, path_value)
        else:
            pack = self.courses.get(problem.course)
            normalized = pack.normalize_problem(problem)
            problem_type = pack.classify_problem_type(normalized)
            normalized = normalized.model_copy(update={"problem_type": problem_type})
            errors = pack.validate_structured_problem(normalized)
            path = self._select_path(normalized, pack.implementation_status)
            selected_capabilities = pack.select_capabilities(normalized)
            selected_tools = self._select_tools(selected_capabilities)
        if state is not None:
            state.update(
                {
                    "current_stage": "select_execution_path",
                    "course": pack.course_code,
                    "problem_type": problem_type,
                    "selected_course_pack": pack.course_code,
                    "selected_capabilities": selected_capabilities,
                    "selected_tools": selected_tools,
                    "execution_path": path,
                    "structured_problem": normalized.model_dump(mode="json"),
                    "retrieved_chunks": list(retrieved_chunks or []),
                }
            )
        if errors or not normalized.problem_text.strip():
            return self._insufficient_result(normalized, path, errors)

        assumptions = [
            str(item.get("description", item)) for item in normalized.uncertain_info
        ]
        missing = [
            str(item.get("field", item)) for item in normalized.critical_missing_info
        ]
        tool_results = self._execute_tools(normalized, selected_tools)
        successful = next(
            (item for item in tool_results if item.status == "success"), None
        )
        unsupported_type = bool(
            pack.supported_problem_types
            and problem_type not in pack.supported_problem_types
            and problem_type != "general"
        )
        if unsupported_type:
            status: Literal["success", "partial", "failed", "unsupported"] = (
                "unsupported"
            )
            final_answer = f"{pack.display_name}课程包暂不支持题型：{problem_type}。"
        elif successful is not None:
            status = "success"
            final_answer = f"确定性工具校验结果：{successful.result.get('value')}"
        elif missing:
            status = "partial"
            final_answer = (
                "当前信息不足以唯一确定数值结果；已保留可继续推导的结构。"
                f"阻断字段：{'、'.join(missing)}。"
            )
        else:
            status = "partial"
            final_answer = (
                f"已识别为{pack.display_name}的{problem_type}问题，并完成能力与路径选择；"
                "当前没有足够的确定性方程产生数值解，未擅自补造条件。"
            )
        conflict_risks = [
            str(item.get("description", item)) for item in normalized.source_conflicts
        ]
        risks = [*missing, *conflict_risks]
        fallback = pack.get_fallback_config(normalized)
        fallback_target = (
            fallback.target_agent_id
            if fallback.enabled and path in fallback.trigger_paths
            else None
        )
        result = AcademicSolutionResult(
            status=status,
            course=pack.course_code,
            problem_type=problem_type,
            problem_summary=normalized.problem_text[:500],
            assumptions=assumptions,
            known_conditions=normalized.known_conditions,
            target_quantities=normalized.target_quantities,
            solution_method=self._method(path, selected_capabilities),
            solution_steps=[
                {"stage": "structure", "status": normalized.structure_status},
                {"stage": "capability_selection", "items": selected_capabilities},
                {"stage": "deterministic_validation", "tools": selected_tools},
                *pack.required_solution_steps(normalized),
            ],
            key_equations=normalized.equations_given,
            intermediate_results=[
                item.result for item in tool_results if item.status == "success"
            ],
            final_answer=final_answer,
            tool_verification=[item.model_dump(mode="json") for item in tool_results],
            consistency_status="verified" if successful else "not_fully_verified",
            remaining_risks=risks,
            knowledge_points=[problem_type] if problem_type != "general" else [],
            common_mistakes=["不要补造未给出的参数、参考方向或实验数据"],
            learning_suggestions=["先核对已知条件与目标量，再检查方程和单位"],
            citations=list(retrieved_chunks or []),
            confidence=self._confidence(normalized, successful is not None),
            execution_path=path,
            fallback_used=False,
            fallback_target=fallback_target,
        )
        validation_errors = pack.validate_solution(result)
        if validation_errors:
            result = result.model_copy(
                update={
                    "status": "partial",
                    "remaining_risks": [*result.remaining_risks, *validation_errors],
                }
            )
        if path == "HIGH_RISK":
            result = self.verify_high_risk(normalized, result, tool_results)
        result = self.quality_gate.evaluate(result, pack)
        if state is not None:
            state.update(
                {
                    "current_stage": "finalize_solver_response",
                    "tool_results": result.tool_verification,
                    "verification_result": (
                        result.verification_report.model_dump(mode="json")
                        if result.verification_report is not None
                        else {
                            "verification_status": result.consistency_status,
                            "issues": [],
                        }
                    ),
                    "final_answer": result.final_answer,
                    "structured_result": result.model_dump(mode="json"),
                    "confidence": result.confidence,
                    "fallback_target": result.fallback_target,
                }
            )
        return result

    def verify_high_risk(
        self,
        problem: AcademicProblem,
        result: AcademicSolutionResult,
        tool_results: list[ToolResult] | None = None,
    ) -> AcademicSolutionResult:
        resolved_tools = tool_results or [
            ToolResult.model_validate(item) for item in result.tool_verification
        ]
        report = self.high_risk_verifier.verify(problem, result, resolved_tools)
        patches = self.high_risk_verifier.patches_for(report)
        return self.high_risk_verifier.apply_patches(result, patches, report)

    def _compile_langgraph(self) -> Any:
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            return None
        builder = StateGraph(XZDGraphState)

        def normalize_problem_input(value: XZDGraphState) -> dict[str, Any]:
            problem = AcademicProblem.model_validate(value["structured_problem"])
            return {
                "current_stage": "normalize_problem_input",
                "normalized_input": {
                    "problem_text": problem.problem_text.strip(),
                    "input_source": problem.input_source,
                    "user_intent": problem.user_intent,
                },
            }

        def resolve_course_pack(value: XZDGraphState) -> dict[str, Any]:
            problem = AcademicProblem.model_validate(value["structured_problem"])
            pack = self.courses.get(problem.course)
            return {
                "current_stage": "resolve_course_pack",
                "course": pack.course_code,
                "selected_course_pack": pack.course_code,
            }

        def structure_problem(value: XZDGraphState) -> dict[str, Any]:
            problem = AcademicProblem.model_validate(value["structured_problem"])
            pack = self.courses.get(
                str(value.get("selected_course_pack", problem.course))
            )
            normalized = pack.normalize_problem(problem)
            problem_type = pack.classify_problem_type(normalized)
            normalized = normalized.model_copy(update={"problem_type": problem_type})
            return {
                "current_stage": "structure_problem",
                "structured_problem": normalized.model_dump(mode="json"),
                "course": pack.course_code,
                "problem_type": problem_type,
            }

        def check_problem_quality(value: XZDGraphState) -> dict[str, Any]:
            problem = AcademicProblem.model_validate(value["structured_problem"])
            pack = self.courses.get(problem.course)
            errors = pack.validate_structured_problem(problem)
            return {
                "current_stage": "check_problem_quality",
                "errors": [
                    {"code": "invalid_problem", "message": error} for error in errors
                ],
            }

        def assess_solvability(value: XZDGraphState) -> dict[str, Any]:
            problem = AcademicProblem.model_validate(value["structured_problem"])
            return {
                "current_stage": "assess_solvability",
                "risk_level": "high"
                if problem.source_conflicts or problem.critical_missing_info
                else "medium"
                if problem.extraction_confidence < 0.85
                else "low",
            }

        def classify_problem_type(value: XZDGraphState) -> dict[str, Any]:
            problem = AcademicProblem.model_validate(value["structured_problem"])
            return {
                "current_stage": "classify_problem_type",
                "problem_type": problem.problem_type or "general",
            }

        def select_capabilities(value: XZDGraphState) -> dict[str, Any]:
            problem = AcademicProblem.model_validate(value["structured_problem"])
            pack = self.courses.get(problem.course)
            capabilities = pack.select_capabilities(problem)
            return {
                "current_stage": "select_capabilities",
                "selected_capabilities": capabilities,
                "selected_tools": self._select_tools(capabilities),
            }

        def retrieve_domain_knowledge(value: XZDGraphState) -> dict[str, Any]:
            chunks = list(value.get("retrieved_chunks", []))
            return {
                "current_stage": "retrieve_domain_knowledge",
                "citations": chunks,
            }

        preparation_nodes = (
            ("normalize_problem_input", normalize_problem_input),
            ("resolve_course_pack", resolve_course_pack),
            ("multimodal_extraction_if_needed", lambda value: {
                "current_stage": "multimodal_extraction_if_needed",
                "warnings": list(value.get("warnings", [])),
            }),
            ("structure_problem", structure_problem),
            ("check_problem_quality", check_problem_quality),
            ("assess_solvability", assess_solvability),
            ("classify_problem_type", classify_problem_type),
            ("select_capabilities", select_capabilities),
            ("retrieve_domain_knowledge", retrieve_domain_knowledge),
        )
        previous = START
        for name, node in preparation_nodes:
            builder.add_node(name, cast(Any, node))
            builder.add_edge(previous, name)
            previous = name

        def select_execution_path(value: XZDGraphState) -> dict[str, Any]:
            problem = AcademicProblem.model_validate(value["structured_problem"])
            pack = self.courses.get(problem.course)
            problem_type = str(
                value.get("problem_type") or problem.problem_type or "general"
            )
            normalized = problem.model_copy(
                update={"problem_type": problem_type}
            )
            capabilities = list(value.get("selected_capabilities", []))
            path = self._select_path(normalized, pack.implementation_status)
            return {
                "current_stage": "select_execution_path",
                "course": pack.course_code,
                "problem_type": problem_type,
                "selected_course_pack": pack.course_code,
                "selected_capabilities": capabilities,
                "selected_tools": self._select_tools(capabilities),
                "execution_path": path,
                "structured_problem": normalized.model_dump(mode="json"),
            }

        builder.add_node("select_execution_path", cast(Any, select_execution_path))
        builder.add_edge(previous, "select_execution_path")

        path_chains = {
            "FAST": ("fast_generate_solution", "lightweight_validation"),
            "STANDARD": (
                "plan_solution",
                "standard_generate_solution",
                "execute_tools",
                "verify_solution",
                "correct_if_needed",
            ),
            "HIGH_RISK": (
                "multi_stage_planning",
                "primary_solution",
                "deterministic_tools",
                "secondary_model_review",
                "conflict_resolution",
                "final_correction",
            ),
            "CONDITIONAL": ("conditional_solution",),
            "FALLBACK": ("fallback_selection",),
        }
        first_nodes: dict[Hashable, str] = {}
        for path, nodes in path_chains.items():
            first_nodes[path] = nodes[0]
            for index, name in enumerate(nodes):
                builder.add_node(
                    name,
                    cast(
                        Any,
                        lambda value, stage_name=name: {
                            "current_stage": stage_name,
                            "solution_plan": {
                                "execution_path": value.get("execution_path", ""),
                                "active_stage": stage_name,
                            },
                        },
                    ),
                )
                if index:
                    builder.add_edge(nodes[index - 1], name)
        builder.add_conditional_edges(
            "select_execution_path",
            cast(Any, lambda value: value["execution_path"]),
            first_nodes,
        )

        builder.add_node(
            "generate_learning_feedback",
            cast(
                Any,
                lambda value: {
                    "current_stage": "generate_learning_feedback",
                    "solution_plan": {
                        "execution_path": value.get("execution_path", ""),
                        "feedback_ready": True,
                    },
                },
            ),
        )
        for nodes in path_chains.values():
            builder.add_edge(nodes[-1], "generate_learning_feedback")
        builder.add_node(
            "format_course_answer",
            cast(
                Any,
                lambda value: {
                    "current_stage": "format_course_answer",
                    "final_answer": str(value.get("final_answer", "")),
                },
            ),
        )
        builder.add_edge("generate_learning_feedback", "format_course_answer")

        def finalize(value: XZDGraphState) -> dict[str, Any]:
            result = self._run_impl(
                AcademicProblem.model_validate(value["structured_problem"]),
                retrieved_chunks=value.get("retrieved_chunks", []),
                state=value,
            )
            return {
                "current_stage": "finalize_solver_response",
                "structured_result": result.model_dump(mode="json"),
                "final_answer": result.final_answer,
                "confidence": result.confidence,
            }

        builder.add_node("finalize_solver_response", cast(Any, finalize))
        builder.add_edge("format_course_answer", "finalize_solver_response")
        builder.add_edge("finalize_solver_response", END)
        return builder.compile(checkpointer=self.checkpointer, name=self.graph_name)

    def _select_tools(self, capability_ids: list[str]) -> list[str]:
        selected: list[str] = []
        for capability_id in capability_ids:
            capability = self.capabilities.get(capability_id)
            for tool_id in capability.tool_ids:
                if tool_id not in selected and self.tools.describe(tool_id).enabled:
                    selected.append(tool_id)
        return selected

    def _execute_tools(
        self, problem: AcademicProblem, selected_tools: list[str]
    ) -> list[ToolResult]:
        if not problem.equations_given:
            return []
        symbols = [
            str(item.get("symbol") or item.get("name") or "").strip()
            for item in problem.target_quantities
        ]
        symbols = [item for item in symbols if item]
        tool_id = (
            "linear_equation_solver"
            if "linear_equation_solver" in selected_tools
            else "sympy_solver"
        )
        if not symbols or tool_id not in self.tools.capabilities():
            return []
        started = perf_counter()
        try:
            value = self.tools.get(tool_id)(problem.equations_given, symbols)
            return [
                ToolResult(
                    tool_id=tool_id,
                    status="success",
                    result={"value": value},
                    elapsed_ms=int((perf_counter() - started) * 1000),
                )
            ]
        except Exception as exc:
            return [
                ToolResult(
                    tool_id=tool_id,
                    status="failed",
                    warnings=[f"{type(exc).__name__}: deterministic tool failed"],
                    elapsed_ms=int((perf_counter() - started) * 1000),
                )
            ]

    @staticmethod
    def _select_path(problem: AcademicProblem, pack_status: str) -> ExecutionPath:
        if pack_status in {"skeleton", "fallback"}:
            return "CONDITIONAL"
        if not problem.can_continue or problem.critical_missing_info:
            return "CONDITIONAL"
        risk = (
            len(problem.figures_given)
            + len(problem.source_conflicts) * 2
            + (2 if problem.code_given else 0)
            + (2 if problem.extraction_confidence < 0.55 else 0)
        )
        if risk >= 4:
            return "HIGH_RISK"
        if (
            problem.extraction_confidence >= 0.85
            and len(problem.equations_given) <= 2
            and not problem.source_conflicts
        ):
            return "FAST"
        return "STANDARD"

    @staticmethod
    def _method(path: ExecutionPath, capabilities: list[str]) -> str:
        joined = "、".join(capabilities) or "课程规则"
        return f"{path} 路径；使用 {joined}"

    @staticmethod
    def _confidence(problem: AcademicProblem, verified: bool) -> float:
        value = problem.extraction_confidence
        if problem.critical_missing_info:
            value -= 0.25
        if problem.source_conflicts:
            value -= 0.15
        if verified:
            value += 0.1
        return max(0.05, min(0.98, value))

    @staticmethod
    def _insufficient_result(
        problem: AcademicProblem, path: ExecutionPath, errors: list[str]
    ) -> AcademicSolutionResult:
        return AcademicSolutionResult(
            status="failed",
            course=problem.course,
            problem_type=problem.problem_type or "unknown",
            problem_summary=problem.problem_text[:500],
            final_answer="没有可识别的有效题目内容。",
            remaining_risks=errors,
            confidence=0.05,
            execution_path=path,
        )
