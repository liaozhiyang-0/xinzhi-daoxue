from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

import httpx
from fastapi import FastAPI

from app.evaluation.cache import EvaluationCache
from app.evaluation.contracts import (
    EvaluationCase,
    EvaluationErrorType,
    EvaluationResult,
    FailureStage,
    SuiteReport,
)
from app.evaluation.reporting import build_statistics, write_report
from app.evaluation.scorers import EvaluationScorer


class EvaluationRunner:
    """Drive the production sessions/tasks API and collect TaskRunner results."""

    def __init__(
        self,
        app: FastAPI,
        *,
        mode: Literal[
            "offline",
            "live",
            "local_deterministic",
            "local_mock",
            "real_model",
            "real_xingchen",
        ],
        cache: EvaluationCache,
        report_root: Path,
        use_cache: bool = True,
        rerun_failed: bool = False,
    ) -> None:
        self.app = app
        self.mode = mode
        self.cache = cache
        self.report_root = report_root
        self.use_cache = use_cache
        self.rerun_failed = rerun_failed
        self.scorer: EvaluationScorer | None = None
        self.client: httpx.AsyncClient | None = None
        self._lifespan: AbstractAsyncContextManager[Any] | None = None

    async def __aenter__(self) -> EvaluationRunner:
        self._lifespan = self.app.router.lifespan_context(self.app)
        await self._lifespan.__aenter__()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://evaluation.local",
        )
        self.scorer = EvaluationScorer(self.app.state.tool_registry)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self.client is not None:
            await self.client.aclose()
        if self._lifespan is not None:
            await self._lifespan.__aexit__(*exc)

    async def run_case(self, case: EvaluationCase) -> EvaluationResult:
        cache_key = self.cache.key(case, mode=self.mode)
        if self.use_cache:
            cached = self.cache.load(cache_key)
            if cached is not None and not (
                self.rerun_failed and cached.status != "passed"
            ):
                return cached.model_copy(
                    update={
                        "warnings": [*cached.warnings, "result_loaded_from_cache"],
                    }
                )
        started = perf_counter()
        trace_id = f"eval_{case.case_id}_{uuid4().hex[:8]}"
        before_traces = len(self.app.state.model_tracer.list())
        try:
            async with asyncio.timeout(case.timeout_seconds):
                task = await self._execute(case, trace_id)
        except TimeoutError:
            result = self._terminal_result(
                case,
                status="timeout",
                stage=FailureStage.TIMEOUT,
                error=EvaluationErrorType.TIMEOUT,
                elapsed_ms=int((perf_counter() - started) * 1000),
                trace_id=trace_id,
                cache_key=cache_key,
                mode=self.mode,
            )
            self.cache.save(cache_key, result)
            return result
        except Exception as exc:
            result = self._terminal_result(
                case,
                status="error",
                stage=FailureStage.UNKNOWN,
                error=EvaluationErrorType.EXECUTION_ERROR,
                elapsed_ms=int((perf_counter() - started) * 1000),
                trace_id=trace_id,
                cache_key=cache_key,
                mode=self.mode,
                warning=f"{type(exc).__name__}: {str(exc)[:160]}",
            )
            self.cache.save(cache_key, result)
            return result
        model_calls = [
            {
                **item.model_dump(mode="json"),
                "usage_status": (
                    "available" if item.total_tokens is not None else "unavailable"
                ),
            }
            for item in self.app.state.model_tracer.list()[before_traces:]
            if item.request_id == trace_id
        ]
        actual = self._observation(task)
        assert self.scorer is not None
        result = self.scorer.score(
            case,
            actual,
            elapsed_ms=int((perf_counter() - started) * 1000),
            model_calls=model_calls,
            trace_id=trace_id,
            cache_key=cache_key,
        )
        result = result.model_copy(update={"evaluation_mode": self.mode})
        self.cache.save(cache_key, result)
        return result

    async def run_suite(
        self,
        cases: list[EvaluationCase],
        *,
        filters: dict[str, Any] | None = None,
    ) -> SuiteReport:
        started = datetime.now(UTC)
        results = [await self.run_case(case) for case in cases]
        completed = datetime.now(UTC)
        passed = sum(item.status == "passed" for item in results)
        summary = {
            "total": len(results),
            "passed": passed,
            "failed": sum(item.status == "failed" for item in results),
            "errors": sum(item.status == "error" for item in results),
            "timeouts": sum(item.status == "timeout" for item in results),
            "cached": sum(
                "result_loaded_from_cache" in item.warnings for item in results
            ),
            "pass_rate": passed / len(results) if results else 0.0,
        }
        report = SuiteReport(
            mode=self.mode,
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            filters=filters or {},
            summary=summary,
            statistics=build_statistics(cases, results),
            results=results,
            estimated_cost=None,
        )
        write_report(report, self.report_root)
        return report

    async def _execute(self, case: EvaluationCase, trace_id: str) -> dict[str, Any]:
        assert self.client is not None
        session_response = await self.client.post(
            "/api/v1/sessions",
            json={
                "user_id": "evaluation-user",
                "course_id": case.course,
                "title": f"Evaluation {case.case_id}",
            },
        )
        session_response.raise_for_status()
        canonical = {"text": case.message, **case.structured_input}
        task_response = await self.client.post(
            "/api/v1/tasks",
            json={
                "session_id": session_response.json()["id"],
                "user_id": "evaluation-user",
                "user_role": "student",
                "scene": "solving",
                "course_id": case.course,
                "intent": case.intent,
                "canonical_input": canonical,
                "attachments": case.file_refs,
                "context_refs": [],
                "options": {
                    "request_id": trace_id,
                    "trace_id": trace_id,
                    "input_type": case.input_type,
                    "evaluation_case_id": case.case_id,
                    "evaluation_mode": self.mode,
                    "allow_cloud": self.mode in {"live", "real_model", "real_xingchen"},
                },
            },
        )
        task_response.raise_for_status()
        task = task_response.json()
        while task["status"] not in {"completed", "failed", "cancelled"}:
            await asyncio.sleep(0.02)
            response = await self.client.get(f"/api/v1/tasks/{task['id']}")
            response.raise_for_status()
            task = response.json()
        return task

    def _observation(self, task: dict[str, Any]) -> dict[str, Any]:
        result = task.get("result_content") or {}
        structured = result.get("structured_result") or {}
        routing = (
            (task.get("input_content") or {}).get("options", {}).get("_routing", {})
        )
        execution_agent = str(task.get("agent_id", ""))
        agent_id = str(
            structured.get("original_agent_id")
            or routing.get("original_agent_id")
            or routing.get("agent_id")
            or execution_agent
        )
        try:
            definition = self.app.state.agent_registry.get(agent_id)
            task_families = sorted(definition.task_families)
        except KeyError:
            task_families = []
        solution_steps = structured.get("solution_steps", [])
        selected_tools: list[str] = []
        for step in solution_steps if isinstance(solution_steps, list) else []:
            if (
                isinstance(step, dict)
                and step.get("stage") == "deterministic_validation"
            ):
                selected_tools.extend(str(item) for item in step.get("tools", []))
        verification = structured.get("verification_report") or {}
        return {
            "task_status": str(task.get("status", "")),
            "route_status": str(task.get("route_status", "")),
            "route_reason": str(task.get("route_reason", "")),
            "task_families": task_families,
            "course": str(task.get("course_id", "")),
            "intent": str(task.get("intent", "")),
            "agent_id": agent_id,
            "execution_agent": execution_agent,
            "course_pack": structured.get("course"),
            "problem_type": structured.get("problem_type"),
            "execution_path": structured.get("execution_path"),
            "status": structured.get(
                "status", "failed" if task.get("status") == "failed" else "success"
            ),
            "answer": result.get("answer", ""),
            "structured_result": structured,
            "selected_tools": list(dict.fromkeys(selected_tools)),
            "tool_calls": structured.get("tool_verification", []),
            "citations": result.get("citations", []),
            "warnings": result.get("warnings", []),
            "assumptions": result.get("assumptions", []),
            "remaining_risks": result.get("remaining_risks", []),
            "verification_status": verification.get("verification_status"),
            "fallback_used": result.get(
                "fallback_used", routing.get("fallback_used", False)
            ),
            "metrics": result.get("metrics", {}),
        }

    @staticmethod
    def _terminal_result(
        case: EvaluationCase,
        *,
        status: Literal["error", "timeout"],
        stage: FailureStage,
        error: EvaluationErrorType,
        elapsed_ms: int,
        trace_id: str,
        cache_key: str,
        mode: str,
        warning: str | None = None,
    ) -> EvaluationResult:
        return EvaluationResult(
            case_id=case.case_id,
            status=status,
            route_passed=False,
            course_passed=False,
            agent_passed=False,
            structure_passed=False,
            execution_path_passed=False,
            tools_passed=False,
            answer_passed=False,
            citations_passed=False,
            safety_passed=False,
            total_score=0,
            expected={"course": case.course, "agent_id": case.expected_agent},
            actual={},
            failure_stage=stage,
            error_types=[error],
            warnings=[warning] if warning else [],
            elapsed_ms=elapsed_ms,
            trace_id=trace_id,
            cache_key=cache_key,
            evaluation_mode=mode,
        )
