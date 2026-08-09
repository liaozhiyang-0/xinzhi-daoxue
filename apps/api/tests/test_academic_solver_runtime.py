from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.contracts import (
    AgentRequest,
    AgentResult,
    AgentResultStatus,
    Intent,
    RetrievalResult,
)
from app.runtime import (
    AgentRun,
    RuntimeEvaluationCase,
    RuntimeNodeStatus,
    evaluate_runtime_run,
)
from app.services.academic_solver_runtime import AcademicSolverRuntimeService
from app.services.retrieval_context import RetrievalContextService


class FakeSolverAgents:
    def __init__(self, results: list[AgentResult]) -> None:
        self.results = results
        self.calls = 0
        self.last_context: object = None

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        context: object = None,
    ) -> AgentResult:
        assert agent_id == AcademicSolverRuntimeService.agent_id
        assert request.task_id == "task-solver-runtime"
        self.last_context = context
        result = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        return result


class FakeRetrieval:
    def search(self, **kwargs: object) -> RetrievalResult:
        return RetrievalResult(
            query=str(kwargs.get("query_text", "")),
            normalized_query=str(kwargs.get("query_text", "")),
            course_ids=["CT"],
            latency_ms=2,
            retrieval_trace_id="trace-solver-runtime",
            index_version="solver-index-v1",
        )


def make_request() -> AgentRequest:
    return AgentRequest(
        task_id="task-solver-runtime",
        session_id="session-solver",
        user_id="user-solver",
        intent=Intent.SOLVE_PROBLEM,
        course_id="CT",
        canonical_input={"text": "Find the equivalent resistance."},
        options={"academic_solver_runtime": {"execute": True}},
    )


def make_result(status: AgentResultStatus = AgentResultStatus.COMPLETED) -> AgentResult:
    return AgentResult(
        status=status,
        agent_id=AcademicSolverRuntimeService.agent_id,
        provider="local_graph",
        answer="The equivalent resistance is 10 ohms."
        if status == AgentResultStatus.COMPLETED
        else "",
        structured_result={"status": status.value},
    )


def test_academic_solver_runtime_wraps_the_frozen_solver_boundary() -> None:
    fake = FakeSolverAgents([make_result()])
    service = AcademicSolverRuntimeService(
        fake, enabled=True  # type: ignore[arg-type]
    )
    request = make_request()
    run = AgentRun(
        run_id="run-solver-runtime",
        task_id=request.task_id,
        goal="solve the circuit problem",
        plan=service.build_plan(request),
    )

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.calls == 1
    assert [node.node_id for node in run.plan.nodes] == [
        "solver.observe",
        "solver.execute",
        "solver.verify",
    ]
    assert run.nodes["solver.execute"].status == RuntimeNodeStatus.SUCCEEDED
    assert run.nodes["solver.verify"].status == RuntimeNodeStatus.SUCCEEDED
    assert run.budget.model_calls == 1


def test_academic_solver_runtime_replans_failed_solver_attempt() -> None:
    fake = FakeSolverAgents([make_result(AgentResultStatus.FAILED), make_result()])
    service = AcademicSolverRuntimeService(
        fake, enabled=True  # type: ignore[arg-type]
    )
    request = make_request()
    run = AgentRun(
        run_id="run-solver-replan",
        task_id=request.task_id,
        goal="retry the circuit problem",
        plan=service.build_plan(request),
    )

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.calls == 2
    assert run.iteration == 1
    assert run.nodes["solver.execute.replan.1"].status == (
        RuntimeNodeStatus.SUCCEEDED
    )


def test_academic_solver_runtime_passes_bounded_retrieval_context_to_solver() -> None:
    fake = FakeSolverAgents([make_result()])
    service = AcademicSolverRuntimeService(
        fake,  # type: ignore[arg-type]
        enabled=True,
        rag_retrieval=FakeRetrieval(),  # type: ignore[arg-type]
        retrieval_context=RetrievalContextService(2_000),
    )
    request = make_request().model_copy(
        update={
            "options": {
                "academic_solver_runtime": {
                    "execute": True,
                    "retrieve": True,
                }
            }
        }
    )
    run = AgentRun(
        run_id="run-solver-retrieval",
        task_id=request.task_id,
        goal="solve with bounded retrieval",
        plan=service.build_plan(request),
    )

    result = asyncio.run(service.run(request, run))

    assert result.status == AgentResultStatus.COMPLETED
    assert fake.last_context is not None
    assert run.nodes["solver.retrieve"].status == RuntimeNodeStatus.SUCCEEDED
    assert result.metrics.retrieval_calls == 1


def test_academic_solver_runtime_uses_versioned_evaluation_case() -> None:
    fake = FakeSolverAgents([make_result()])
    service = AcademicSolverRuntimeService(
        fake, enabled=True  # type: ignore[arg-type]
    )
    request = make_request()
    run = AgentRun(
        run_id="run-solver-case",
        task_id=request.task_id,
        goal="evaluate the solver boundary",
        plan=service.build_plan(request),
    )
    asyncio.run(service.run(request, run))
    case_path = (
        Path(__file__).resolve().parents[3]
        / "evaluation"
        / "runtime_cases"
        / "academic_solver_v1.json"
    )
    case = RuntimeEvaluationCase.model_validate(
        json.loads(case_path.read_text(encoding="utf-8"))
    )

    evaluation = evaluate_runtime_run(run, case, checkpoint_count=1)

    assert evaluation.passed is True
