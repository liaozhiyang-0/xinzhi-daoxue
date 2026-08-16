from __future__ import annotations

import asyncio
import logging
import mimetypes
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

import httpx
from fastapi import FastAPI

from app.contracts import AttachmentRef
from app.evaluation.cache import EvaluationCache
from app.evaluation.contracts import (
    EvaluationCase,
    EvaluationErrorType,
    EvaluationResult,
    FailureStage,
    SuiteReport,
)
from app.evaluation.reporting import (
    build_evaluation_run_metadata,
    build_statistics,
    resolve_evaluation_attachment,
    write_report,
)
from app.evaluation.scorers import EvaluationScorer
from app.services.evaluation_attachment_cleanup import (
    cleanup_evaluation_attachments,
)
from app.services.solver_runtime_policy import SolverRuntimePolicy

STANDARD_EVALUATION_TIMEOUT_SECONDS = 180
COMPLEX_EVALUATION_TIMEOUT_SECONDS = 240
_COMPLEX_TAGS = {
    "complex",
    "high_risk",
    "long_context",
    "multi_step",
    "quality_flagged",
}
logger = logging.getLogger(__name__)


def evaluation_timeout_decision(case: EvaluationCase) -> tuple[int, list[str]]:
    """Keep standard cases bounded while giving multi-stage cases 240 seconds."""

    if case.timeout_seconds != STANDARD_EVALUATION_TIMEOUT_SECONDS:
        return case.timeout_seconds, ["explicit_case_timeout"]
    signals: list[str] = []
    if case.file_refs or "image" in case.input_type.casefold():
        signals.append("visual_input")
    if case.difficulty == "hard":
        signals.append("hard_difficulty")
    signals.extend(SolverRuntimePolicy.text_complexity_signals(case.message))
    if _COMPLEX_TAGS.intersection(item.casefold() for item in case.tags):
        signals.append("complexity_tag")
    if str(case.task_options.get("complexity", "")).casefold() in {
        "complex",
        "high_risk",
    }:
        signals.append("explicit_complexity")
    if signals:
        return COMPLEX_EVALUATION_TIMEOUT_SECONDS, signals
    return STANDARD_EVALUATION_TIMEOUT_SECONDS, []


class EvaluationRunner:
    """Drive the production sessions/tasks API and collect Runtime results."""

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
        self._case_attachment_root: Path | None = None

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
        timeout_seconds, complexity_signals = evaluation_timeout_decision(case)
        try:
            async with asyncio.timeout(timeout_seconds):
                task = await self._execute(case, trace_id)
        except TimeoutError:
            model_calls = self._model_calls_since(before_traces, trace_id)
            result = self._terminal_result(
                case,
                status="timeout",
                stage=FailureStage.TIMEOUT,
                error=EvaluationErrorType.TIMEOUT,
                elapsed_ms=int((perf_counter() - started) * 1000),
                trace_id=trace_id,
                cache_key=cache_key,
                mode=self.mode,
                warning=(
                    f"evaluation_timeout_seconds={timeout_seconds}; "
                    "complexity_signals="
                    f"{','.join(complexity_signals) or 'none'}"
                ),
                model_calls=model_calls,
                timeout_seconds=timeout_seconds,
                complexity_signals=complexity_signals,
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
        model_calls = self._model_calls_since(before_traces, trace_id)
        actual = self._observation(task)
        actual["evaluation_timeout_seconds"] = timeout_seconds
        actual["evaluation_complexity_signals"] = complexity_signals
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

    def _model_calls_since(
        self,
        before_traces: int,
        trace_id: str,
    ) -> list[dict[str, Any]]:
        return [
            {
                **item.model_dump(mode="json"),
                "usage_status": (
                    "available" if item.total_tokens is not None else "unavailable"
                ),
            }
            for item in self.app.state.model_tracer.list()[before_traces:]
            if item.request_id == trace_id
        ]

    async def run_suite(
        self,
        cases: list[EvaluationCase],
        *,
        filters: dict[str, Any] | None = None,
        case_catalog_sha256: str = "",
        case_catalog_content_sha256: str = "",
        case_source_files_sha256: str = "",
        case_attachment_manifest_sha256: str = "",
        case_attachment_count: int = 0,
        case_attachment_root: Path | None = None,
    ) -> SuiteReport:
        started = datetime.now(UTC)
        previous_attachment_root = self._case_attachment_root
        self._case_attachment_root = case_attachment_root
        try:
            results = [await self.run_case(case) for case in cases]
        finally:
            self._case_attachment_root = previous_attachment_root
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
        run_id = f"eval_run_{uuid4().hex}"
        report = SuiteReport(
            mode=self.mode,
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            filters=filters or {},
            summary=summary,
            statistics=build_statistics(cases, results),
            results=results,
            estimated_cost=None,
            run_metadata=build_evaluation_run_metadata(
                cases,
                run_id=run_id,
                implementation_fingerprint=self.cache.fingerprint,
                filters=filters,
                case_catalog_sha256=case_catalog_sha256,
                case_catalog_content_sha256=case_catalog_content_sha256,
                case_source_files_sha256=case_source_files_sha256,
                case_attachment_manifest_sha256=case_attachment_manifest_sha256,
                case_attachment_count=case_attachment_count,
            ),
        )
        write_report(report, self.report_root)
        return report

    async def _execute(self, case: EvaluationCase, trace_id: str) -> dict[str, Any]:
        assert self.client is not None
        evaluation_controls = {
            key: value
            for key, value in case.task_options.items()
            if key.startswith("_evaluation_")
        }
        task_options = {
            key: value
            for key, value in case.task_options.items()
            if not key.startswith("_evaluation_")
        }
        attachments = await self._build_evaluation_attachments(case)
        task: dict[str, Any] | None = None
        try:
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
                    "attachments": attachments,
                    "context_refs": [],
                    "options": {
                        "request_id": trace_id,
                        "trace_id": trace_id,
                        "input_type": case.input_type,
                        "evaluation_case_id": case.case_id,
                        "evaluation_mode": self.mode,
                        **task_options,
                    },
                },
            )
            task_response.raise_for_status()
            task = task_response.json()
            while task["status"] not in {"completed", "failed", "cancelled"}:
                await asyncio.sleep(0.02)
                response = await self.client.get(
                    f"/api/v1/tasks/{task['id']}?user_id=evaluation-user"
                )
                response.raise_for_status()
                task = response.json()
            actions = evaluation_controls.get("_evaluation_follow_up_actions", [])
            for index, item in enumerate(actions if isinstance(actions, list) else []):
                action = item if isinstance(item, str) else str(item.get("action", ""))
                student_answer = (
                    "" if isinstance(item, str) else str(item.get("student_answer", ""))
                )
                action_response = await self.client.post(
                    "/api/v1/learning/actions",
                    json={
                        "source_task_id": task["id"],
                        "user_id": "evaluation-user",
                        "action": action,
                        "idempotency_key": (
                            f"{trace_id}_{case.case_id}_{index}_{action}"
                        )[:128],
                        "student_answer": student_answer,
                        "payload": {},
                    },
                )
                action_response.raise_for_status()
                response = await self.client.get(
                    f"/api/v1/tasks/{task['id']}?user_id=evaluation-user"
                )
                response.raise_for_status()
                task = response.json()
            if evaluation_controls.get("_evaluation_cross_user_check"):
                cross_user = await self.client.get(
                    f"/api/v1/tasks/{task['id']}?user_id=another-evaluation-user"
                )
                task["_evaluation_cross_user_isolated"] = cross_user.status_code in {
                    403,
                    404,
                }
            return task
        finally:
            if task is None:
                await self._cleanup_evaluation_attachments(attachments)

    async def _cleanup_evaluation_attachments(
        self, attachments: list[dict[str, Any]]
    ) -> None:
        """Delete only files uploaded by this evaluation run after task use."""

        if not attachments:
            return
        session_factory = getattr(self.app.state, "session_factory", None)
        settings = getattr(self.app.state, "settings", None)
        if session_factory is None or settings is None:
            return
        try:
            async with session_factory() as db:
                await cleanup_evaluation_attachments(
                    db,
                    settings,
                    file_ids=(str(item.get("file_id", "")) for item in attachments),
                )
                await db.commit()
        except Exception:
            logger.warning(
                "evaluation attachment cleanup failed",
                extra={"file_ids": [item.get("file_id") for item in attachments]},
                exc_info=True,
            )

    async def _build_evaluation_attachments(
        self, case: EvaluationCase
    ) -> list[dict[str, Any]]:
        """Upload validated local case files and return safe AttachmentRefs."""

        if not case.file_refs:
            return []
        if self._case_attachment_root is None:
            raise ValueError(
                f"{case.case_id}: file_refs require an explicit case attachment root"
            )
        assert self.client is not None
        attachments: list[dict[str, Any]] = []
        try:
            for ordinal, reference in enumerate(case.file_refs):
                _relative, path = resolve_evaluation_attachment(
                    reference,
                    root=self._case_attachment_root,
                    case_id=case.case_id,
                    ordinal=ordinal,
                )
                content_type = mimetypes.guess_type(path.name)[0]
                if content_type is None:
                    raise ValueError(
                        f"{case.case_id}: attachment {ordinal} content type is unknown"
                    )
                response = await self.client.post(
                    "/api/v1/files",
                    files={
                        "upload": (
                            path.name,
                            path.read_bytes(),
                            content_type,
                        )
                    },
                    data={"purpose": "evaluation_attachment"},
                )
                response.raise_for_status()
                payload = response.json()
                attachment_index = len(attachments)
                uploaded_file_id = str(payload.get("id", ""))
                if not uploaded_file_id:
                    raise ValueError(
                        f"{case.case_id}: attachment {ordinal} upload returned no id"
                    )
                # Keep a cleanup handle even when ingestion is pending/failed.
                attachments.append({"file_id": uploaded_file_id})
                ingestion_status = str(payload.get("ingestion_status", ""))
                if ingestion_status in {"pending", "processing"}:
                    raise ValueError(
                        f"{case.case_id}: attachment {ordinal} ingestion is "
                        "not complete"
                    )
                if ingestion_status == "failed":
                    detail = str(payload.get("extraction_error") or "ingestion failed")
                    raise ValueError(
                        f"{case.case_id}: attachment {ordinal} ingestion failed: "
                        f"{detail}"
                    )
                attachment = AttachmentRef(
                    file_id=str(payload["id"]),
                    filename=str(payload["filename"]),
                    content_type=str(payload["content_type"]),
                    size_bytes=int(payload["size_bytes"]),
                    storage_key=str(payload["storage_key"]),
                    checksum_sha256=str(payload["checksum_sha256"]),
                    ingestion_status=ingestion_status,
                    page_count=int(payload.get("page_count", 0)),
                    extracted_text=str(payload.get("extracted_text", "")),
                    extraction_metadata=dict(payload.get("extraction_metadata") or {}),
                )
                attachments[attachment_index] = attachment.model_dump(mode="json")
        except Exception:
            await self._cleanup_evaluation_attachments(attachments)
            raise
        return attachments

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
        input_options = (task.get("input_content") or {}).get("options", {})
        input_options = input_options if isinstance(input_options, dict) else {}
        teaching = structured.get("teaching") or {}
        teaching = teaching if isinstance(teaching, dict) else {}
        solution_packet = structured.get("solution_packet") or {}
        solution_packet = solution_packet if isinstance(solution_packet, dict) else {}
        evidence_packet = structured.get("evidence_packet") or {}
        evidence_packet = evidence_packet if isinstance(evidence_packet, dict) else {}
        error_pool = structured.get("error_pool") or {}
        error_pool = error_pool if isinstance(error_pool, dict) else {}
        teaching_loop = structured.get("teaching_loop") or {}
        teaching_loop = teaching_loop if isinstance(teaching_loop, dict) else {}
        teaching_plan = teaching_loop.get("execution_plan") or {}
        teaching_plan = teaching_plan if isinstance(teaching_plan, dict) else {}
        phase2_verification = (
            structured.get("verification_report_v1")
            or teaching_loop.get("verification")
            or {}
        )
        phase2_verification = (
            phase2_verification if isinstance(phase2_verification, dict) else {}
        )
        phase2_steps = phase2_verification.get("step_results") or []
        phase2_steps = phase2_steps if isinstance(phase2_steps, list) else []
        first_verification = (
            phase2_steps[0]
            if phase2_steps and isinstance(phase2_steps[0], dict)
            else {}
        )
        hint = teaching_loop.get("hint") or {}
        hint = hint if isinstance(hint, dict) else {}
        disclosure = teaching_loop.get("disclosure_policy") or {}
        disclosure = disclosure if isinstance(disclosure, dict) else {}
        next_check = teaching_loop.get("next_check") or {}
        next_check = next_check if isinstance(next_check, dict) else {}
        metrics = result.get("metrics", {})
        metrics = metrics if isinstance(metrics, dict) else {}
        expected_mode = str(input_options.get("teaching_mode", "direct_answer"))
        mapping_status = str(solution_packet.get("mapping_status", ""))
        mapped_skill_ids = [str(item) for item in solution_packet.get("skill_ids", [])]
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
            "metrics": metrics,
            "student_attempt_parsed": isinstance(
                input_options.get("student_attempt"), dict
            ),
            "teaching_mode_respected": (
                str(teaching.get("teaching_mode", "")) == expected_mode
            ),
            "solution_packet_valid": (
                solution_packet.get("version") == "v1"
                and bool(solution_packet.get("course_id"))
            ),
            "skill_mapping_valid": (
                (mapping_status == "mapped" and bool(mapped_skill_ids))
                or (
                    mapping_status in {"partial", "unavailable"}
                    and not mapped_skill_ids
                )
            ),
            "skill_ids": mapped_skill_ids,
            "evidence_packet_valid": (
                evidence_packet.get("version") == "v1"
                and "evidence_sufficiency" in evidence_packet
            ),
            "error_pool_match_valid": error_pool.get("status") == "matched",
            "answer_disclosure_compliant": bool(
                teaching.get("answer_disclosure_compliant", False)
            ),
            "requires_manual_review": bool(
                teaching.get("requires_manual_review", False)
            ),
            "expected_teaching_execution_path": str(teaching_plan.get("path", "")),
            "verification_report_valid": (
                phase2_verification.get("version") == "v1"
                and bool(phase2_verification.get("overall_status"))
            ),
            "expected_verification_status": str(
                phase2_verification.get("overall_status", "")
            ),
            "expected_error_type": str(first_verification.get("error_type", "")),
            "expected_hint_level": str(hint.get("hint_level", "")),
            "expected_disclosure_mode": str(disclosure.get("mode", "")),
            "next_check_valid": (
                next_check.get("version") == "v1"
                and bool(next_check.get("question_text"))
                and "answer_key_internal" not in next_check
            ),
            "solution_packet_reused": bool(
                teaching_loop.get(
                    "solution_packet_reused",
                    metrics.get("solution_packet_reused", False),
                )
            ),
            "full_solution_disclosed": bool(
                teaching_loop.get(
                    "full_solution_disclosed",
                    disclosure.get("reveal_final_answer", False),
                )
            ),
            "no_additional_model_calls": (
                int(metrics.get("additional_model_calls", 0)) == 0
            ),
            "first_confirmed_error_found": bool(
                phase2_verification.get("first_confirmed_error_step")
            ),
            "cross_user_isolated": bool(
                task.get("_evaluation_cross_user_isolated", False)
            ),
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
        model_calls: list[dict[str, Any]] | None = None,
        timeout_seconds: int | None = None,
        complexity_signals: list[str] | None = None,
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
            expected={
                "course": case.course,
                "agent_id": case.expected_agent,
                "timeout_seconds": timeout_seconds,
            },
            actual={
                "evaluation_timeout_seconds": timeout_seconds,
                "evaluation_complexity_signals": complexity_signals or [],
            },
            failure_stage=stage,
            error_types=[error],
            warnings=[warning] if warning else [],
            elapsed_ms=elapsed_ms,
            model_calls=model_calls or [],
            trace_id=trace_id,
            cache_key=cache_key,
            evaluation_mode=mode,
        )
