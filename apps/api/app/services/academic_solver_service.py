from __future__ import annotations

import asyncio
import json
import logging
from time import perf_counter
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from app.agents.internal.contracts import VisionExtraction
from app.contracts import (
    AgentRequest,
    AgentResult,
    Artifact,
    ArtifactType,
    ImageInput,
    ModelResponse,
    RunMetrics,
)
from app.contracts.solver import (
    AcademicProblem,
    FallbackReason,
    ProblemComplexity,
    ProfessionalValidationResult,
    SolverNodeTiming,
    SolverObservability,
    SolverReviewResult,
    SolverTaskMode,
)
from app.core.config import Settings
from app.core.errors import AppError
from app.multimodal import MultiImageComposer, PreparedImageBatch, SourceImage
from app.orchestrator.graphs import AcademicProblemSolverGraph
from app.orchestrator.state import new_graph_state
from app.services.academic_review import AcademicReviewService
from app.services.ae_validator import AEValidator
from app.services.ct_validator import CTValidator
from app.services.de_validator import DEValidator
from app.services.math_formatting_service import MATH_OUTPUT_INSTRUCTION
from app.services.response_depth import (
    ResponseDepthPolicy,
    depth_instruction,
    policy_for,
)
from app.services.solver_boundary_policy import SolverBoundaryPolicy
from app.services.solver_runtime_policy import (
    FallbackTracker,
    RequestTimeBudget,
    SolverRuntimePolicy,
)

if TYPE_CHECKING:
    from app.services.model_service import ModelService
    from app.services.storage import StorageService

logger = logging.getLogger(__name__)


class AcademicProblemSolverService:
    """Adapt the universal graph to the shared Agent request/result contract."""

    agent_id = "ACADEMIC_PROBLEM_SOLVER"
    completion_marker = "<!-- XZD_ACADEMIC_COMPLETE -->"
    complex_model_task_type = "academic_problem_solving"
    standard_model_task_type = "academic_problem_solving_simple"

    def __init__(
        self,
        graph: AcademicProblemSolverGraph,
        model_service: ModelService | None = None,
        storage: StorageService | None = None,
    ) -> None:
        self.graph = graph
        self.model_service = model_service
        self.storage = storage
        self.runtime_policy = SolverRuntimePolicy()
        self.boundary_policy = SolverBoundaryPolicy()
        self.ae_validator = AEValidator()
        self.ct_validator = CTValidator()
        self.de_validator = DEValidator()
        self.review_service = AcademicReviewService()

    async def run(self, request: AgentRequest, context: Any = None) -> AgentResult:
        settings = self._settings()
        node_timings: list[SolverNodeTiming] = []
        problem = self._problem_from_request(request)
        complexity = self.runtime_policy.classify(problem)
        budget = self._request_time_budget(
            settings,
            complexity,
            upstream_elapsed_seconds=float(
                request.options.get("_upstream_elapsed_seconds", 0.0)
            ),
        )
        fallback_tracker = FallbackTracker()
        fallback_tracker.start(self.agent_id)
        boundary_started = perf_counter()
        boundary = self.boundary_policy.evaluate(problem, check_visual_topology=False)
        node_timings.append(
            self._node_timing(
                "boundary_policy",
                boundary_started,
                "intercepted" if boundary.intercepted else "passed",
            )
        )
        if boundary.intercepted:
            vision_execution: dict[str, Any] = {
                "status": "skipped",
                "reason": "boundary_intercepted",
                "model_calls": 0,
            }
        else:
            vision_started = perf_counter()
            problem, vision_execution = await self._extract_visual_context(
                request,
                problem,
                budget=budget,
            )
            node_timings.append(
                self._node_timing(
                    "multimodal_extraction",
                    vision_started,
                    str(vision_execution.get("status", "not_required")),
                    model=str(vision_execution.get("model") or "") or None,
                    error_type=(
                        str(vision_execution.get("error_type"))
                        if vision_execution.get("error_type")
                        else None
                    ),
                )
            )
            self._record_execution_fallback(vision_execution, fallback_tracker)
            if not boundary.intercepted:
                visual_boundary_started = perf_counter()
                visual_boundary = self.boundary_policy.evaluate(problem)
                if visual_boundary.intercepted:
                    boundary = visual_boundary
                    node_timings.append(
                        self._node_timing(
                            "visual_boundary_policy",
                            visual_boundary_started,
                            "intercepted",
                            error_type=visual_boundary.reason,
                        )
                    )
        citations = self._citations(context)
        state = new_graph_state(
            request_id=str(request.options.get("request_id", request.task_id)),
            session_id=request.session_id,
            user_id=request.user_id,
            message=problem.problem_text,
            file_refs=[
                {
                    "file_id": item.file_id,
                    "filename": item.filename,
                    "content_type": item.content_type,
                }
                for item in request.attachments
            ],
        )
        state.update(
            {
                "task_family": "ACADEMIC_SOLVING",
                "selected_agent": self.agent_id,
                "route_status": "selected",
            }
        )
        graph_started = perf_counter()
        result = await self.graph.arun(
            problem,
            retrieved_chunks=citations,
            state=state,
            thread_id=state["thread_id"],
        )
        node_timings.append(
            self._node_timing(
                "academic_solver_graph",
                graph_started,
                result.status,
            )
        )
        request_id = str(request.options.get("request_id", request.task_id))
        depth_policy = policy_for(request.options, "academic_solver")
        if boundary.intercepted:
            result = self.boundary_policy.apply(result, boundary)
            model_execution = {
                "status": "skipped",
                "reason": boundary.reason,
                "model_calls": 0,
            }
        else:
            generation_started = perf_counter()
            result, model_execution = await self._generate_with_model(
                problem,
                result,
                request_id=request_id,
                budget=budget,
                complexity=complexity,
                allow_route_fallback=fallback_tracker.count == 0,
                knowledge_context=self._retrieved_context(context),
                depth_policy=depth_policy,
            )
            node_timings.append(
                self._node_timing(
                    "model_generation",
                    generation_started,
                    str(model_execution.get("status", "not_available")),
                    model=str(model_execution.get("model") or "") or None,
                    error_type=(
                        str(model_execution.get("error_type"))
                        if model_execution.get("error_type")
                        else None
                    ),
                )
            )
            self._record_execution_fallback(model_execution, fallback_tracker)
        professional_started = perf_counter()
        professional_validation = self._professional_validation(problem, result)
        result = self._apply_professional_validation(result, professional_validation)
        node_timings.append(
            self._node_timing(
                "professional_validation",
                professional_started,
                "passed" if professional_validation.valid else "conflict",
            )
        )
        verification_reason = self.runtime_policy.verification_reason(
            problem,
            complexity=complexity,
            confidence=result.confidence,
            professional_conflicts=not professional_validation.valid,
            explicitly_requested=bool(request.options.get("verify_answer"))
            or depth_policy.level.value == "deep",
        )
        verification_model_execution: dict[str, Any]
        if model_execution.get("output_status") == "partial":
            verification_model_execution = {
                "status": "skipped",
                "reason": "generation_incomplete",
            }
        elif verification_reason is None:
            verification_model_execution = {
                "status": "skipped",
                "reason": "conditional_verification_not_triggered",
                "model_calls": 0,
            }
        elif not budget.can_start_optional_call():
            verification_model_execution = {
                "status": "skipped",
                "reason": "time_budget_exhausted",
                "model_calls": 0,
            }
        else:
            verification_started = perf_counter()
            result, verification_model_execution = await self._review_high_risk(
                problem,
                result,
                request_id=request_id,
                budget=budget,
                verification_reason=verification_reason,
            )
            node_timings.append(
                self._node_timing(
                    "conditional_verification",
                    verification_started,
                    str(verification_model_execution.get("status", "deterministic")),
                    model=(
                        str(verification_model_execution.get("model") or "") or None
                    ),
                    error_type=(
                        str(verification_model_execution.get("error_type"))
                        if verification_model_execution.get("error_type")
                        else None
                    ),
                )
            )
        review_result: SolverReviewResult | None = None
        if problem.task_mode in {SolverTaskMode.REVIEW, SolverTaskMode.VERIFY}:
            review_started = perf_counter()
            raw_attempt = request.options.get("student_attempt")
            review_result = self.review_service.review(
                problem,
                result,
                raw_attempt if isinstance(raw_attempt, dict) else None,
            )
            result = result.model_copy(
                update={
                    "final_answer": self._format_review_result(review_result),
                    "confidence": min(result.confidence, review_result.confidence),
                }
            )
            node_timings.append(
                self._node_timing(
                    "student_answer_review",
                    review_started,
                    review_result.student_answer_status,
                )
            )

        fallback_decision = self._fallback_decision(
            request,
            problem,
            result,
            model_execution,
            professional_validation,
            fallback_tracker,
        )
        result = result.model_copy(
            update={
                "fallback_target": (
                    str(fallback_decision.get("target_agent") or "") or None
                )
            }
        )
        answer = self.boundary_policy.condition_absolute_claims(
            result.final_answer,
            has_assumptions=bool(result.assumptions or boundary.assumptions),
        )
        if answer != result.final_answer:
            result = result.model_copy(update={"final_answer": answer})
        structured = result.model_dump(mode="json")
        structured["response_depth"] = depth_policy.metadata()
        if vision_execution:
            structured["vision_execution"] = vision_execution
        if model_execution:
            structured["model_execution"] = model_execution
        if verification_model_execution:
            structured["verification_model_execution"] = verification_model_execution
        structured["professional_validation"] = professional_validation.model_dump(
            mode="json"
        )
        structured["boundary_decision"] = {
            "answer_status": boundary.answer_status,
            "can_continue": boundary.can_continue,
            "missing_information": boundary.missing_information,
            "uncertain_points": boundary.uncertain_points,
            "reason": boundary.reason,
        }
        if boundary.intercepted:
            structured["retrieval_preflight"] = {
                "status": "skipped",
                "reason": boundary.reason,
                "saved_stage": "knowledge_retrieval",
            }
        if review_result is not None:
            structured["review_result"] = review_result.model_dump(mode="json")
        structured["fallback_decision"] = fallback_decision
        model_call_count = sum(
            self._execution_model_calls(item)
            for item in (
                vision_execution,
                model_execution,
                verification_model_execution,
            )
        )
        observability = SolverObservability(
            request_id=request_id,
            course=problem.course,
            task_mode=problem.task_mode,
            complexity=complexity,
            route_path=fallback_tracker.route_path,
            fallback_reason=fallback_tracker.reason,
            fallback_count=fallback_tracker.count,
            model_call_count=model_call_count,
            rag_call_count=1 if citations else 0,
            vision_call_count=int(vision_execution.get("model_calls", 0)),
            verification_triggered=(
                verification_model_execution.get("status") == "completed"
            ),
            verification_reason=verification_reason,
            time_budget_exhausted=budget.soft_exhausted,
            deadline_remaining_ms=budget.remaining_ms(),
            partial_result_available=bool(result.final_answer.strip()),
            verification_skipped_reason=(
                str(verification_model_execution.get("reason"))
                if verification_model_execution.get("status") == "skipped"
                else None
            ),
            node_timings=node_timings,
        )
        structured["solver_observability"] = observability.model_dump(mode="json")
        artifact = Artifact(
            artifact_type=ArtifactType.STRUCTURED_RESULT,
            owner_id=request.user_id,
            task_id=request.task_id,
            course_id=request.course_id,
            content={
                "academic_solution": structured,
                "execution_source": "academic_problem_solver_graph",
            },
        )
        return AgentResult(
            agent_id=self.agent_id,
            provider="local_graph",
            answer=result.final_answer,
            structured_result=structured,
            business_data=structured,
            artifacts=[artifact],
            citations=[],
            warnings=result.remaining_risks,
            confidence=result.confidence,
            metrics=RunMetrics(
                model_calls=model_call_count,
                tool_calls=len(result.tool_verification),
                deadline_remaining_ms=observability.deadline_remaining_ms,
                time_budget_exhausted=observability.time_budget_exhausted,
                partial_result_available=observability.partial_result_available,
                verification_skipped_reason=(
                    observability.verification_skipped_reason or ""
                ),
                fallback_count=observability.fallback_count,
                vision_calls=observability.vision_call_count,
                verification_triggered=observability.verification_triggered,
                verification_reason=observability.verification_reason or "",
                complexity=complexity.value,
                task_mode=problem.task_mode.value,
                route_path=observability.route_path,
                node_timings=[item.model_dump(mode="json") for item in node_timings],
            ),
            rag_status="retrieved" if citations else "not_available",
            evidence_status="sufficient" if citations else "insufficient",
            course_id=result.course,
            intent=request.intent.value,
            assumptions=result.assumptions,
            remaining_risks=result.remaining_risks,
            request_id=str(request.options.get("request_id", "")),
            trace_id=str(request.options.get("trace_id", "")),
            task_id=request.task_id,
            cloud_status="not_required",
            fallback_used=result.fallback_used,
            schema_version="1.0",
        )

    async def _extract_visual_context(
        self,
        request: AgentRequest,
        problem: AcademicProblem,
        *,
        budget: RequestTimeBudget,
    ) -> tuple[AcademicProblem, dict[str, Any]]:
        images = [
            item
            for item in request.attachments
            if item.content_type.startswith("image/")
        ]
        task_type = self._visual_task_type(problem.course)
        if (
            not images
            or self.model_service is None
            or self.storage is None
            or not self._model_route_available(task_type)
        ):
            return problem, {}
        if budget.finalization_required:
            return problem, {
                "status": "skipped",
                "reason": "time_budget_exhausted",
                "model_calls": 0,
            }
        try:
            sources = [
                SourceImage(
                    filename=item.filename,
                    mime_type=item.content_type,
                    data=await self.storage.read(item.storage_key),
                )
                for item in images
            ]
            settings = getattr(self.model_service, "settings", None)
            if not isinstance(settings, Settings):
                settings = Settings.model_validate({"app_env": "test"})
            prepared = await asyncio.to_thread(
                MultiImageComposer(settings).prepare,
                sources,
            )
            if prepared.strategy == "per_image":
                return await self._extract_images_individually(
                    request=request,
                    problem=problem,
                    prepared=prepared,
                    filenames=[item.filename for item in images],
                    task_type=task_type,
                    budget=budget,
                )
            pack = self.graph.courses.get(problem.course)
            async with asyncio.timeout(
                self._vision_call_timeout_seconds(budget, settings)
            ):
                response = await self.model_service.analyze_images_for_task(
                    task_type,
                    prompt=(
                        pack.build_extraction_prompt(problem)
                        + (
                            " 这是按原始顺序拼接的组合图，每个区域标有 Image 编号；"
                            if prepared.strategy == "stitched"
                            else (
                                f" 以下是按用户上传顺序提供的 {prepared.source_count} "
                                "张独立原图；必须同时阅读全部图片并恢复跨图题干、"
                                "续页、图号、连接和条件关系，不得把任一图片孤立解释；"
                                if prepared.strategy == "ordered_multi_image"
                                else ""
                            )
                        )
                        + self._visual_extraction_instruction()
                    ),
                    images=list(prepared.images),
                    request_id=str(request.options.get("request_id", "")) or None,
                    json_mode=False,
                )
        except TimeoutError:
            return (
                problem.model_copy(
                    update={
                        "uncertain_info": [
                            *problem.uncertain_info,
                            {"description": "视觉提取达到请求时间预算"},
                        ]
                    }
                ),
                {
                    "status": "failed",
                    "error_type": "vision_time_budget_exhausted",
                    "model_calls": 1,
                },
            )
        except AppError as exc:
            return (
                problem.model_copy(
                    update={
                        "uncertain_info": [
                            *problem.uncertain_info,
                            {"description": f"视觉提取失败: {exc.code}"},
                        ]
                    }
                ),
                {"status": "failed", "error_type": exc.code},
            )
        visual_summary = response.content[:20_000]
        problem, visual_structure = self._merge_visual_extraction(
            problem,
            visual_summary,
        )
        return (
            problem,
            {
                "status": "completed",
                "strategy": prepared.strategy,
                "provider": response.provider,
                "model": response.model,
                "elapsed_ms": response.elapsed_ms,
                "image_count": len(images),
                "source_image_count": len(images),
                "model_image_count": len(prepared.images),
                "model_calls": 1,
                "original_order_preserved": (
                    prepared.strategy == "ordered_multi_image"
                ),
                "composite_width": prepared.composite_width,
                "composite_height": prepared.composite_height,
                **visual_structure,
                **self._fallback_metadata(response),
            },
        )

    async def _extract_images_individually(
        self,
        *,
        request: AgentRequest,
        problem: AcademicProblem,
        prepared: PreparedImageBatch,
        filenames: list[str],
        task_type: str,
        budget: RequestTimeBudget,
    ) -> tuple[AcademicProblem, dict[str, Any]]:
        model_service = self.model_service
        assert model_service is not None
        settings = getattr(model_service, "settings", None)
        concurrency = (
            settings.multi_image_fallback_concurrency
            if isinstance(settings, Settings)
            else 2
        )
        semaphore = asyncio.Semaphore(concurrency)
        pack = self.graph.courses.get(problem.course)

        async def extract_one(index: int, image: ImageInput) -> dict[str, Any]:
            async with semaphore:
                if budget.finalization_required:
                    return {
                        "index": index,
                        "filename": filenames[index - 1],
                        "status": "failed",
                        "error_type": "vision_time_budget_exhausted",
                        "content": "",
                    }
                try:
                    async with asyncio.timeout(
                        self._vision_call_timeout_seconds(budget, settings)
                    ):
                        response = await model_service.analyze_images_for_task(
                            task_type,
                            prompt=(
                                pack.build_extraction_prompt(problem)
                                + f" 当前是第 {index}/{prepared.source_count} 张图，"
                                "请保留跨图衔接所需的节点名、题号、方向、参数和不确定项；"
                                + self._visual_extraction_instruction()
                            ),
                            images=[image],
                            request_id=(
                                str(request.options.get("request_id", "")) or None
                            ),
                            json_mode=False,
                            extra_options={"_allow_route_fallback": index == 1},
                        )
                except TimeoutError:
                    return {
                        "index": index,
                        "filename": filenames[index - 1],
                        "status": "failed",
                        "error_type": "vision_time_budget_exhausted",
                        "content": "",
                    }
                except AppError as exc:
                    return {
                        "index": index,
                        "filename": filenames[index - 1],
                        "status": "failed",
                        "error_type": exc.code,
                        "content": "",
                    }
                return {
                    "index": index,
                    "filename": filenames[index - 1],
                    "status": "completed",
                    "provider": response.provider,
                    "model": response.model,
                    "elapsed_ms": response.elapsed_ms,
                    "content": response.content[:12_000],
                    **self._fallback_metadata(response),
                }

        executions = await asyncio.gather(
            *(
                extract_one(index, image)
                for index, image in enumerate(prepared.images, start=1)
            )
        )
        completed = [item for item in executions if item["status"] == "completed"]
        failed = [item for item in executions if item["status"] == "failed"]
        if not completed:
            return (
                problem.model_copy(
                    update={
                        "uncertain_info": [
                            *problem.uncertain_info,
                            {"description": "多图逐图识别全部失败"},
                        ]
                    }
                ),
                {
                    "status": "failed",
                    "strategy": "per_image",
                    "fallback_reason": prepared.fallback_reason,
                    "image_count": prepared.source_count,
                    "source_image_count": prepared.source_count,
                    "model_image_count": len(prepared.images),
                    "model_calls": len(prepared.images),
                    "individual_executions": [
                        {key: value for key, value in item.items() if key != "content"}
                        for item in executions
                    ],
                },
            )

        extracted_text = "\n\n".join(
            f"[Image {item['index']} · {item['filename']}]\n{item['content']}"
            for item in completed
        )
        summary, summary_execution = await self._summarize_image_extractions(
            request=request,
            problem=problem,
            extracted_text=extracted_text,
            budget=budget,
            allow_route_fallback=not any(
                int(item.get("fallback_count", 0)) > 0 for item in executions
            ),
        )
        visual_summary = summary[:50_000]
        problem, visual_structure = self._merge_visual_extraction(
            problem,
            visual_summary,
            section_title="多图内容汇总",
        )
        uncertain = [
            *problem.uncertain_info,
            {"description": "多图内容由逐图视觉识别后合并，需以原图为准"},
        ]
        if failed:
            uncertain.append(
                {
                    "description": (
                        f"{len(failed)} 张图片未完成识别，当前解答可能缺少条件"
                    )
                }
            )
        model_names = list(
            dict.fromkeys(
                str(item.get("model", "")) for item in completed if item.get("model")
            )
        )
        provider_names = list(
            dict.fromkeys(
                str(item.get("provider", ""))
                for item in completed
                if item.get("provider")
            )
        )
        summary_calls = int(summary_execution.get("model_calls", 0))
        route_fallbacks = [
            item for item in executions if int(item.get("fallback_count", 0)) > 0
        ]
        route_fallbacks.extend(
            [summary_execution]
            if int(summary_execution.get("fallback_count", 0)) > 0
            else []
        )
        return (
            problem.model_copy(update={"uncertain_info": uncertain}),
            {
                "status": "partial" if failed else "completed",
                "strategy": "per_image",
                "image_count": prepared.source_count,
                "source_image_count": prepared.source_count,
                "model_image_count": len(prepared.images),
                "model_calls": len(prepared.images) + summary_calls,
                "provider": (
                    provider_names[0] if len(provider_names) == 1 else "multiple"
                ),
                "model": model_names[0] if len(model_names) == 1 else "multiple",
                "providers": provider_names,
                "models": model_names,
                "fallback_count": min(1, len(route_fallbacks)),
                "fallback_reason": (
                    str(route_fallbacks[0].get("fallback_reason"))
                    if route_fallbacks
                    else prepared.fallback_reason
                ),
                "source_model": (
                    str(route_fallbacks[0].get("source_model"))
                    if route_fallbacks
                    else None
                ),
                "target_model": (
                    str(route_fallbacks[0].get("target_model"))
                    if route_fallbacks
                    else None
                ),
                "individual_executions": [
                    {key: value for key, value in item.items() if key != "content"}
                    for item in executions
                ],
                "summary_execution": summary_execution,
                **visual_structure,
            },
        )

    async def _summarize_image_extractions(
        self,
        *,
        request: AgentRequest,
        problem: AcademicProblem,
        extracted_text: str,
        budget: RequestTimeBudget,
        allow_route_fallback: bool,
    ) -> tuple[str, dict[str, Any]]:
        assert self.model_service is not None
        settings = getattr(self.model_service, "settings", None)
        max_chars = (
            settings.multi_image_summary_max_chars
            if isinstance(settings, Settings)
            else 24_000
        )
        if not self._model_route_available("multi_image_summary"):
            return extracted_text[:max_chars], {
                "status": "skipped",
                "reason": "summary_model_unavailable",
                "model_calls": 0,
            }
        if not budget.can_start_optional_call():
            return extracted_text[:max_chars], {
                "status": "skipped",
                "reason": "time_budget_exhausted",
                "model_calls": 0,
            }
        try:
            async with asyncio.timeout(
                self._vision_call_timeout_seconds(budget, settings)
            ):
                response = await self.model_service.generate_for_task(
                    "multi_image_summary",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "你负责合并多张题目图片的逐图识别结果。只整理题目事实，"
                                "按图片顺序恢复跨图关系、题号、条件和待求量；不解题、"
                                "不补造缺失参数，冲突和不确定项必须保留。"
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"课程：{problem.course}\n"
                                f"用户问题：{problem.problem_text[:4000]}\n"
                                f"逐图结果：\n{extracted_text[:max_chars]}"
                            ),
                        },
                    ],
                    request_id=str(request.options.get("request_id", "")) or None,
                    extra_options={
                        "max_tokens": 2048,
                        "timeout": budget.call_timeout_seconds(
                            self._generation_limits()[2]
                        ),
                        "_allow_route_fallback": allow_route_fallback,
                    },
                )
        except TimeoutError:
            return extracted_text[:max_chars], {
                "status": "failed",
                "error_type": "summary_time_budget_exhausted",
                "model_calls": 1,
            }
        except AppError as exc:
            return extracted_text[:max_chars], {
                "status": "failed",
                "error_type": exc.code,
                "model_calls": 1,
            }
        return response.content.strip(), {
            "status": "completed",
            "provider": response.provider,
            "model": response.model,
            "elapsed_ms": response.elapsed_ms,
            "model_calls": 1,
            **self._fallback_metadata(response),
        }

    async def _generate_with_model(
        self,
        problem: AcademicProblem,
        result: Any,
        *,
        request_id: str,
        budget: RequestTimeBudget,
        complexity: ProblemComplexity,
        allow_route_fallback: bool,
        knowledge_context: str = "",
        depth_policy: ResponseDepthPolicy | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        depth_policy = depth_policy or policy_for({}, "academic_solver")
        model_task_type = self._generation_task_type(complexity)
        if self.model_service is None or not self._model_route_available(
            model_task_type
        ):
            return result, {}
        if budget.finalization_required:
            return (
                result.model_copy(
                    update={
                        "status": "partial",
                        "remaining_risks": [
                            *result.remaining_risks,
                            "请求时间预算已进入最终整理阶段，未启动新的模型生成",
                        ],
                    }
                ),
                {
                    "status": "skipped",
                    "reason": "time_budget_exhausted",
                    "model_calls": 0,
                    "task_type": model_task_type,
                },
            )
        pack = self.graph.courses.get(problem.course)
        grounded_context = (
            "\n".join(
                (
                    "课程资料（只作为方法、图号和课程约定的证据；题目事实以用户输入"
                    "和原图为准）：",
                    knowledge_context[:4_000],
                )
            )
            if knowledge_context
            else ""
        )
        prompt = "\n".join(
            (
                pack.build_planning_prompt(problem),
                pack.build_solving_prompt(problem),
                self._mode_instruction(problem),
                depth_instruction(depth_policy),
                "必须明确假设、关键方程和适用范围；不得补造题目事实。",
                (
                    "先在内部完成推导、方向/符号检查和全部小问核对，再输出唯一的"
                    "“结论汇总”和最少充分的关键推导。不得展示试错、自我对话、"
                    "旧结论或“修正前/修正后”两套答案；结论汇总必须与后文一致。"
                    "不得逐字复述题目，不要长篇讨论多个假设；若图中连接或端点"
                    "可辨认，必须按图作答，不得以无法获取原图为由拒答。"
                ),
                (
                    "题目中标记为“图片结构化提取”或“多图内容汇总”的内容，"
                    "是上游视觉模型已经从用户原图读取出的题目事实。你必须直接"
                    "据此解题，不得声称图片无法查看、无法访问或要求用户重新上传；"
                    "若视觉结果明确标记某个局部不确定，只指出该局部的最少不确定项。"
                ),
                (
                    "等价公式、分段式和统一式均可；画图题应至少给出可复现的节点、"
                    "连接、方向、逐时钟取值或关键坐标描述，不能只讲通用原理。"
                    "设计题必须覆盖题目点名的每个输入、输出和实现连接。"
                ),
                MATH_OUTPUT_INSTRUCTION,
                (
                    "逐项完成题目全部小问；确认全部完成后，最后一行只输出"
                    f" {self.completion_marker}"
                ),
                f"题目：{problem.problem_text}",
                f"已知结构：{problem.model_dump_json(exclude_none=True)[:8000]}",
                grounded_context,
            )
        )
        (
            max_tokens,
            max_continuations,
            configured_timeout_seconds,
        ) = self._generation_limits(depth_policy)
        call_budget = self.runtime_policy.model_call_budget(
            complexity,
            task_mode=problem.task_mode,
        )
        call_timeout_seconds = budget.call_timeout_seconds(configured_timeout_seconds)
        try:
            async with asyncio.timeout(call_timeout_seconds):
                response = await self.model_service.generate_for_task(
                    model_task_type,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是受控的多学科专业问题求解节点。",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    request_id=request_id,
                    extra_options={
                        "max_tokens": max_tokens,
                        "timeout": configured_timeout_seconds,
                        **(
                            {}
                            if allow_route_fallback
                            else {"_allow_route_fallback": False}
                        ),
                    },
                )
        except TimeoutError:
            return self._generation_failure(
                result,
                "primary_model_time_budget_exhausted",
                task_type=model_task_type,
            )
        except AppError as exc:
            return self._generation_failure(
                result,
                exc.code,
                fallback_attempted=bool(exc.details.get("fallback_attempted")),
                task_type=model_task_type,
            )
        except Exception:
            logger.exception(
                "academic_solver_model_unexpected_error request_id=%s",
                request_id,
            )
            return self._generation_failure(
                result,
                "academic_model_unexpected_error",
                task_type=model_task_type,
            )
        responses = [response]
        answer = response.content.strip()
        require_completion_marker = self._requires_completion_marker(
            problem,
            complexity,
        )
        truncated = self._response_truncated(
            response,
            max_tokens,
            require_completion_marker=require_completion_marker,
        )
        truncation_detected = truncated
        continuation_error: str | None = None
        continuation_count = 0
        while (
            truncated
            and continuation_count < max_continuations
            and (
                self._response_call_count(responses) < call_budget
                or self._explicit_length_truncation(response)
            )
            and budget.can_start_optional_call()
        ):
            continuation_count += 1
            answer = self._trim_incomplete_tail(answer)
            try:
                call_timeout = budget.call_timeout_seconds(configured_timeout_seconds)
                continuation_options: dict[str, Any] = {
                    "max_tokens": max_tokens,
                    "timeout": configured_timeout_seconds,
                }
                successful_fallback_alias = response.raw_metadata.get("target_model")
                if (
                    response.raw_metadata.get("route_fallback_used")
                    and successful_fallback_alias
                ):
                    continuation_options.update(
                        {
                            "_preferred_route_alias": successful_fallback_alias,
                            "_allow_route_fallback": False,
                        }
                    )
                elif self._response_call_count(responses) != 1:
                    continuation_options["_allow_route_fallback"] = False
                async with asyncio.timeout(call_timeout):
                    response = await self.model_service.generate_for_task(
                        model_task_type,
                        messages=[
                            {
                                "role": "system",
                                "content": "你是受控的多学科专业问题求解节点。",
                            },
                            {
                                "role": "user",
                                "content": self._continuation_prompt(
                                    problem.problem_text,
                                    answer,
                                    continuation_count,
                                ),
                            },
                        ],
                        request_id=request_id,
                        extra_options=continuation_options,
                    )
            except TimeoutError:
                continuation_error = "continuation_time_budget_exhausted"
                break
            except AppError as exc:
                continuation_error = exc.code
                break
            except Exception:
                logger.exception(
                    "academic_solver_continuation_unexpected_error request_id=%s",
                    request_id,
                )
                continuation_error = "academic_continuation_unexpected_error"
                break
            responses.append(response)
            continuation = response.content.strip()
            if continuation:
                answer = continuation
            truncated = self._response_truncated(
                response,
                max_tokens,
                require_completion_marker=require_completion_marker,
            )
            truncation_detected = truncation_detected or truncated

        if truncated:
            answer = self._trim_incomplete_tail(answer)
        answer = answer.replace(self.completion_marker, "").rstrip()
        output_complete = not truncated and continuation_error is None
        generation_risks = list(result.remaining_risks)
        if not result.tool_verification:
            generation_risks.append("模型解答尚未被确定性工具完整验证")
        if not output_complete:
            generation_risks.append(
                "模型输出达到续答上限，当前回答仍可能不完整，请按章节继续追问"
            )
        output_status = "complete" if output_complete else "partial"
        updated = result.model_copy(
            update={
                "status": result.status if output_complete else "partial",
                "final_answer": answer,
                "solution_steps": [
                    *result.solution_steps,
                    {
                        "stage": "model_reasoning",
                        "status": output_status,
                        "model_calls": self._response_call_count(responses),
                        "continuation_count": continuation_count,
                    },
                ],
                "remaining_risks": generation_risks,
                "confidence": min(0.9, max(result.confidence, 0.65)),
            }
        )
        return (
            updated,
            {
                "status": "completed" if output_complete else "partial",
                "output_status": output_status,
                "task_type": model_task_type,
                "routing_tier": (
                    "complex_qwen_primary"
                    if model_task_type == self.complex_model_task_type
                    else "standard_spark_primary"
                ),
                "provider": response.provider,
                "model": response.model,
                "elapsed_ms": sum(item.elapsed_ms for item in responses),
                "model_calls": self._response_call_count(responses),
                "continuation_count": continuation_count,
                "continuation_mode": "replace_consolidated",
                "max_tokens_per_call": max_tokens,
                "timeout_seconds_per_call": configured_timeout_seconds,
                "finish_reasons": [item.finish_reason for item in responses],
                "truncation_detected": truncation_detected,
                "continuation_error": continuation_error,
                "usage": self._combined_usage(responses),
                **self._combined_fallback_metadata(responses),
            },
        )

    @classmethod
    def _generation_task_type(cls, complexity: ProblemComplexity) -> str:
        if complexity in {
            ProblemComplexity.COMPLEX,
            ProblemComplexity.HIGH_RISK,
        }:
            return cls.complex_model_task_type
        return cls.standard_model_task_type

    def _generation_limits(
        self, depth_policy: ResponseDepthPolicy | None = None
    ) -> tuple[int, int, float]:
        if self.model_service is None:
            return 4096, 2, 240
        settings = getattr(self.model_service, "settings", None)
        if settings is None:
            return 4096, 2, 240
        configured_max_tokens = min(
            int(settings.academic_solver_max_tokens),
            int(settings.iflytek_spark_max_tokens),
        )
        if depth_policy is not None:
            configured_max_tokens = min(
                configured_max_tokens, depth_policy.max_output_tokens
            )
        return (
            configured_max_tokens,
            int(settings.academic_solver_max_continuations),
            float(settings.academic_solver_timeout_seconds),
        )

    def _vision_call_timeout_seconds(
        self,
        budget: RequestTimeBudget,
        settings: object,
    ) -> float:
        """Bound vision work while reserving time for the actual solver answer."""

        runtime_settings = (
            settings if isinstance(settings, Settings) else self._settings()
        )
        return budget.call_timeout_seconds(
            float(runtime_settings.academic_solver_vision_timeout_seconds),
            reserve_for_finalization_seconds=(
                float(runtime_settings.academic_solver_min_generation_seconds) + 3
            ),
        )

    @classmethod
    def _response_truncated(
        cls,
        response: ModelResponse,
        max_tokens: int,
        *,
        require_completion_marker: bool = False,
    ) -> bool:
        finish_reason = (response.finish_reason or "").strip().casefold()
        if finish_reason in {"length", "max_tokens", "max_token", "token_limit"}:
            return True
        if "length" in finish_reason or "max_token" in finish_reason:
            return True
        if cls._looks_structurally_incomplete(response.content):
            return True
        if require_completion_marker and cls.completion_marker not in response.content:
            return True
        if finish_reason in {"stop", "completed", "complete", "end_turn"}:
            return False
        if (
            response.usage is not None
            and response.usage.completion_tokens is not None
            and response.usage.completion_tokens >= max(1, max_tokens - 8)
        ):
            return True
        return False

    @staticmethod
    def _explicit_length_truncation(response: ModelResponse) -> bool:
        finish_reason = (response.finish_reason or "").strip().casefold()
        return finish_reason in {
            "length",
            "max_tokens",
            "max_token",
            "token_limit",
        } or any(marker in finish_reason for marker in ("length", "max_token"))

    @staticmethod
    def _requires_completion_marker(
        problem: AcademicProblem,
        complexity: ProblemComplexity,
    ) -> bool:
        """Use marker-based continuation only for genuinely long composite prompts.

        Short multi-image prompts often receive a complete answer without the
        private marker. Treating marker absence alone as truncation duplicates
        otherwise complete answers and wastes a model call.
        """

        return (
            complexity
            in {
                ProblemComplexity.COMPLEX,
                ProblemComplexity.HIGH_RISK,
            }
            and len(problem.problem_text) >= 1200
        )

    @staticmethod
    def _looks_structurally_incomplete(content: str) -> bool:
        text = content.rstrip()
        if len(text) < 512:
            return False
        if text.count("$$") % 2 or text.count("\\[") > text.count("\\]"):
            return True
        return text.endswith(("_", "^", "\\", "{", "[", "(", "=", "+", "-"))

    @classmethod
    def _trim_incomplete_tail(cls, content: str) -> str:
        text = content.rstrip()
        if text.count("$$") % 2:
            text = text[: text.rfind("$$")].rstrip()
        elif text.count("\\[") > text.count("\\]"):
            text = text[: text.rfind("\\[")].rstrip()
        elif cls._looks_structurally_incomplete(text) and "\n" in text:
            text = text.rsplit("\n", 1)[0].rstrip()
        return text

    @staticmethod
    def _continuation_prompt(
        problem_text: str, answer: str, continuation_number: int
    ) -> str:
        return "\n".join(
            (
                "上一版回答因输出长度、结构未闭合或小问未完成，需要整体整理。",
                f"这是第 {continuation_number} 次完整整理。",
                "请返回一份可直接替换上一版的完整最终答案，不要只续写尾部。",
                "先在内部核对全部小问、数值、符号、方向、单位和图形/连接要求。",
                "只保留唯一最终结论；删除试错、自我纠正、互相冲突的旧结论。",
                "保持答案简洁且 Markdown/LaTeX 结构闭合，不补造题目事实。",
                (
                    "确认全部小问完成后，最后一行只输出"
                    f" {AcademicProblemSolverService.completion_marker}"
                ),
                f"原题：{problem_text[:16000]}",
                f"待整理的上一版回答：{AcademicProblemSolverService._draft_excerpt(answer)}",
            )
        )

    @staticmethod
    def _draft_excerpt(answer: str, *, max_chars: int = 24_000) -> str:
        if len(answer) <= max_chars:
            return answer
        half = max_chars // 2
        return (
            f"{answer[:half]}\n\n[中间部分因上下文预算省略]\n\n{answer[-half:]}"
        )

    @staticmethod
    def _combined_usage(responses: list[ModelResponse]) -> dict[str, int] | None:
        fields = ("prompt_tokens", "completion_tokens", "total_tokens")
        totals: dict[str, int] = {}
        for field in fields:
            values = [
                getattr(item.usage, field)
                for item in responses
                if item.usage is not None and getattr(item.usage, field) is not None
            ]
            if values:
                totals[field] = sum(values)
        return totals or None

    @staticmethod
    def _fallback_metadata(response: ModelResponse) -> dict[str, Any]:
        metadata = response.raw_metadata
        if not metadata.get("route_fallback_used"):
            return {}
        return {
            "fallback_count": 1,
            "fallback_reason": str(
                metadata.get("fallback_reason") or "primary_model_error"
            ),
            "source_model": str(metadata.get("source_model") or ""),
            "target_model": str(metadata.get("target_model") or ""),
        }

    @classmethod
    def _combined_fallback_metadata(
        cls,
        responses: list[ModelResponse],
    ) -> dict[str, Any]:
        values = [
            cls._fallback_metadata(item)
            for item in responses
            if cls._fallback_metadata(item)
        ]
        if not values:
            return {}
        return {
            "fallback_count": 1,
            "fallback_reason": values[0]["fallback_reason"],
            "source_model": values[0]["source_model"],
            "target_model": values[0]["target_model"],
        }

    @staticmethod
    def _response_call_count(responses: list[ModelResponse]) -> int:
        return sum(
            1 + int(item.raw_metadata.get("fallback_count", 0) or 0)
            for item in responses
        )

    @staticmethod
    def _execution_model_calls(execution: dict[str, Any]) -> int:
        raw_count = execution.get("model_calls")
        if isinstance(raw_count, int):
            return max(0, raw_count)
        return 1 if execution.get("status") in {"completed", "partial"} else 0

    @staticmethod
    def _record_execution_fallback(
        execution: dict[str, Any],
        tracker: FallbackTracker,
    ) -> None:
        if int(execution.get("fallback_count", 0) or 0) < 1:
            return
        raw_reason = str(execution.get("fallback_reason") or "primary_model_error")
        reason = (
            FallbackReason.PRIMARY_MODEL_TIMEOUT
            if "timeout" in raw_reason
            else FallbackReason.PRIMARY_MODEL_ERROR
        )
        source = tracker.route_path[-1] if tracker.route_path else "unknown"
        target = f"model:{execution.get('target_model') or 'route_fallback'}"
        tracker.request(
            source_agent=source,
            target_agent=target,
            reason=reason,
            stage="model_route",
        )

    async def _review_high_risk(
        self,
        problem: AcademicProblem,
        result: Any,
        *,
        request_id: str,
        budget: RequestTimeBudget,
        verification_reason: str,
    ) -> tuple[Any, dict[str, Any]]:
        if result.execution_path != "HIGH_RISK":
            return result, {
                "status": "skipped",
                "reason": "deterministic_validation_sufficient",
                "trigger": verification_reason,
                "model_calls": 0,
            }
        reviewed = self.graph.verify_high_risk(problem, result)
        report = reviewed.verification_report
        if (
            report is None
            or not report.requires_patch
            or self.model_service is None
            or not self.model_service.settings.enable_dual_model_verification
            or not self._verifier_available("academic_problem_solving")
        ):
            return reviewed, {
                "status": "skipped",
                "reason": "secondary_model_not_required",
                "trigger": verification_reason,
                "model_calls": 0,
            }
        if not budget.can_start_optional_call():
            return reviewed, {
                "status": "skipped",
                "reason": "time_budget_exhausted",
                "trigger": verification_reason,
                "model_calls": 0,
            }
        prompt = "\n".join(
            (
                "只审核列出的关键问题，不重新完整解题，也不要输出整份替代答案。",
                f"问题摘要：{result.problem_summary[:1200]}",
                f"关键方程：{result.key_equations[:20]}",
                f"工具结果：{result.tool_verification[:20]}",
                f"待审核步骤：{result.solution_steps[:20]}",
                f"已有问题：{report.model_dump_json(exclude_none=True)[:4000]}",
                "输出简短审核线索；没有确定性证据时必须说明不确定。",
            )
        )
        try:
            timeout = budget.call_timeout_seconds(self._generation_limits()[2])
            async with asyncio.timeout(timeout):
                response = await self.model_service.verify_with_secondary_model(
                    "academic_problem_solving",
                    messages=[
                        {"role": "system", "content": "你是受限的关键问题审核节点。"},
                        {"role": "user", "content": prompt},
                    ],
                    request_id=request_id,
                )
        except TimeoutError:
            return reviewed, {
                "status": "failed",
                "error_type": "verification_time_budget_exhausted",
                "trigger": verification_reason,
                "model_calls": 1,
            }
        except AppError as exc:
            return reviewed, {
                "status": "failed",
                "error_type": exc.code,
                "trigger": verification_reason,
                "model_calls": 1,
            }
        except Exception:
            logger.exception(
                "academic_solver_verification_unexpected_error request_id=%s",
                request_id,
            )
            return reviewed, {
                "status": "failed",
                "error_type": "academic_verification_unexpected_error",
                "trigger": verification_reason,
                "model_calls": 1,
            }
        merged = self.graph.high_risk_verifier.merge_secondary_review(
            report, response.content
        )
        patches = self.graph.high_risk_verifier.patches_for(merged)
        reviewed = self.graph.high_risk_verifier.apply_patches(
            reviewed, patches, merged
        )
        return reviewed, {
            "status": "completed",
            "provider": response.provider,
            "model": response.model,
            "elapsed_ms": response.elapsed_ms,
            "deterministic": False,
            "trigger": verification_reason,
            "model_calls": 1,
        }

    @staticmethod
    def _generation_failure(
        result: Any,
        error_type: str,
        *,
        fallback_attempted: bool = False,
        task_type: str | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        return (
            result.model_copy(
                update={
                    "remaining_risks": [
                        *result.remaining_risks,
                        (f"统一模型服务不可用，已保留确定性结果: {error_type}"),
                    ]
                }
            ),
            {
                "status": "failed",
                "error_type": error_type,
                "task_type": task_type,
                "model_calls": 2 if fallback_attempted else 1,
                "fallback_count": 1 if fallback_attempted else 0,
                "fallback_reason": error_type if fallback_attempted else None,
            },
        )

    def _settings(self) -> Settings:
        if self.model_service is not None:
            settings = getattr(self.model_service, "settings", None)
            if isinstance(settings, Settings):
                return settings
        return Settings()

    def _professional_validation(
        self,
        problem: AcademicProblem,
        result: Any,
    ) -> ProfessionalValidationResult:
        if problem.course == "AE":
            return self.ae_validator.validate(problem, result)
        if problem.course == "CT":
            return self.ct_validator.validate(problem, result)
        if problem.course == "DE":
            return self.de_validator.validate(problem, result)
        return ProfessionalValidationResult(
            validator="course_validator_not_required",
            analysis_mode=problem.problem_type or "unknown",
        )

    @staticmethod
    def _apply_professional_validation(
        result: Any,
        validation: ProfessionalValidationResult,
    ) -> Any:
        if validation.valid:
            return result
        conflict_messages = [item.message for item in validation.conflicts]
        return result.model_copy(
            update={
                "status": "partial",
                "remaining_risks": list(
                    dict.fromkeys([*result.remaining_risks, *conflict_messages])
                ),
                "remaining_issues": list(
                    dict.fromkeys(
                        [
                            *result.remaining_issues,
                            *(item.conflict_type for item in validation.conflicts),
                        ]
                    )
                ),
                "consistency_status": "professional_conflict",
                "confidence": max(0.2, min(result.confidence, 0.6)),
            }
        )

    def _fallback_decision(
        self,
        request: AgentRequest,
        problem: AcademicProblem,
        result: Any,
        model_execution: dict[str, Any],
        professional_validation: ProfessionalValidationResult,
        tracker: FallbackTracker,
    ) -> dict[str, Any]:
        target = str(result.fallback_target or "")
        decision: dict[str, Any] = {
            "source_agent": self.agent_id,
            "target_agent": target or None,
            "fallback_reason": None,
            "fallback_stage": "",
            "fallback_count": tracker.count,
            "approved": False,
            "blocked_reason": "",
        }
        if problem.course != "CT" or not target:
            decision["blocked_reason"] = "no_course_fallback_target"
            return decision
        reason: FallbackReason | None = None
        stage = "generation"
        explicit_legacy = bool(request.options.get("legacy_baseline_required"))
        model_status = str(model_execution.get("status", ""))
        error_type = str(model_execution.get("error_type", ""))
        if explicit_legacy:
            reason = FallbackReason.LEGACY_BASELINE_REQUIRED
            stage = "request_policy"
        elif (
            result.execution_path == "HIGH_RISK"
            and model_status == "failed"
            and problem.can_continue
            and not problem.critical_missing_info
        ):
            reason = (
                FallbackReason.PRIMARY_MODEL_TIMEOUT
                if "timeout" in error_type or "time_budget" in error_type
                else FallbackReason.PRIMARY_MODEL_ERROR
            )
        elif result.execution_path == "HIGH_RISK" and not professional_validation.valid:
            reason = FallbackReason.PROFESSIONAL_VALIDATION_FAILED
            stage = "professional_validation"
        if reason is None:
            decision["blocked_reason"] = "fallback_not_required"
            return decision
        approved = tracker.request(
            source_agent=self.agent_id,
            target_agent=target,
            reason=reason,
            stage=stage,
        )
        decision.update(
            {
                "fallback_reason": reason.value,
                "fallback_stage": stage,
                "fallback_count": tracker.count,
                "approved": approved,
                "blocked_reason": "" if approved else "fallback_limit_or_loop",
            }
        )
        return decision

    @staticmethod
    def _format_review_result(review: SolverReviewResult) -> str:
        if review.student_answer_status == "correct":
            return "当前审查范围内未发现实质错误。"
        if not review.first_error_step:
            return review.why_incorrect or "当前信息不足以完成审查。"
        return "\n".join(
            (
                f"第一处实质错误：{review.first_error_step}",
                f"错误类型：{review.error_type}",
                f"原因：{review.why_incorrect}",
                f"正确写法：{review.corrected_step}",
                f"后续影响：{review.downstream_impact}",
            )
        )

    @staticmethod
    def _mode_instruction(problem: AcademicProblem) -> str:
        if problem.task_mode == SolverTaskMode.REVIEW:
            return (
                "本次生成只用于建立内部参考解；后续只审查学生答案的第一处"
                "实质错误，不把完整参考解直接作为审查反馈。"
            )
        if problem.task_mode == SolverTaskMode.VERIFY:
            return "只推导验证指定步骤所需的最小前置关系，不扩展为无关的完整长篇解答。"
        return "完成题目要求的求解，并保留可核验的关键步骤。"

    @staticmethod
    def _node_timing(
        node_id: str,
        started: float,
        status: str,
        *,
        model: str | None = None,
        error_type: str | None = None,
    ) -> SolverNodeTiming:
        return SolverNodeTiming(
            node_id=node_id,
            elapsed_ms=max(0, int((perf_counter() - started) * 1000)),
            status=status,
            model=model,
            error_type=error_type,
        )

    @staticmethod
    def _request_time_budget(
        settings: Settings,
        complexity: ProblemComplexity,
        *,
        upstream_elapsed_seconds: float = 0.0,
    ) -> RequestTimeBudget:
        started_at = perf_counter() - max(0.0, upstream_elapsed_seconds)
        if SolverRuntimePolicy.uses_extended_time_budget(complexity):
            return RequestTimeBudget(
                soft_deadline_seconds=(
                    settings.academic_solver_complex_soft_deadline_seconds
                ),
                finalization_deadline_seconds=(
                    settings.academic_solver_complex_finalization_deadline_seconds
                ),
                hard_deadline_seconds=(
                    settings.academic_solver_complex_hard_deadline_seconds
                ),
                started_at=started_at,
            )
        return RequestTimeBudget(
            soft_deadline_seconds=settings.academic_solver_soft_deadline_seconds,
            finalization_deadline_seconds=(
                settings.academic_solver_finalization_deadline_seconds
            ),
            hard_deadline_seconds=settings.academic_solver_hard_deadline_seconds,
            started_at=started_at,
        )

    def _model_route_available(self, task_type: str) -> bool:
        assert self.model_service is not None
        route = self.model_service.registry.get_route(task_type)
        definition = self.model_service.registry.get_model(route.primary)
        provider = self.model_service.providers.get(definition.provider)
        return bool(
            provider is not None
            and provider.available
            and self.model_service.registry.enabled(definition)
        )

    def _verifier_available(self, task_type: str) -> bool:
        assert self.model_service is not None
        route = self.model_service.registry.get_route(task_type)
        if not route.verifier:
            return False
        definition = self.model_service.registry.get_model(route.verifier)
        provider = self.model_service.providers.get(definition.provider)
        return bool(
            provider is not None
            and provider.available
            and self.model_service.registry.enabled(definition)
        )

    @staticmethod
    def _problem_from_request(request: AgentRequest) -> AcademicProblem:
        canonical = request.canonical_input
        raw_mode = str(
            request.options.get(
                "task_mode",
                canonical.get("task_mode", SolverTaskMode.SOLVE.value),
            )
        ).upper()
        try:
            task_mode = SolverTaskMode(raw_mode)
        except ValueError:
            task_mode = SolverTaskMode.SOLVE
        raw_attempt = request.options.get("student_attempt")
        student_answer = (
            str(raw_attempt.get("raw_text") or raw_attempt.get("final_answer") or "")
            if isinstance(raw_attempt, dict)
            else ""
        )
        raw_known = canonical.get("known_conditions", [])
        raw_targets = canonical.get("target_quantities", [])
        raw_entities = canonical.get("entities", canonical.get("components", []))
        raw_relations = canonical.get(
            "relations", canonical.get("circuit_relations", [])
        )
        raw_conventions = canonical.get(
            "reference_conventions", canonical.get("reference_directions", [])
        )
        equations = canonical.get("equations_given", [])
        if not equations and raw_relations:
            equations = [
                item if isinstance(item, str) else str(item.get("equation", ""))
                for item in raw_relations
            ]
        return AcademicProblem(
            input_source=str(request.options.get("input_type", "text")),
            user_intent=request.intent.value,
            task_mode=task_mode,
            student_answer=student_answer or None,
            verify_target=(
                str(
                    request.options.get(
                        "verify_target",
                        canonical.get("verify_target", ""),
                    )
                )
                or None
            ),
            course=request.course_id.upper(),
            chapter=str(canonical.get("chapter", "")) or None,
            topic=str(canonical.get("topic", "")) or None,
            problem_type=str(canonical.get("problem_type", "")) or None,
            problem_text=AcademicProblemSolverService._text(canonical),
            known_conditions=AcademicProblemSolverService._dicts(raw_known, "value"),
            target_quantities=AcademicProblemSolverService._dicts(raw_targets, "name"),
            entities=AcademicProblemSolverService._dicts(raw_entities, "value"),
            relations=AcademicProblemSolverService._dicts(raw_relations, "equation"),
            reference_conventions=AcademicProblemSolverService._dicts(
                raw_conventions, "description"
            ),
            equations_given=[str(item) for item in equations if str(item).strip()],
            code_given=(str(canonical.get("code_given", "")) or None),
            tables_given=AcademicProblemSolverService._dicts(
                canonical.get("tables_given", []), "value"
            ),
            figures_given=[
                {"file_id": item.file_id, "content_type": item.content_type}
                for item in request.attachments
                if item.content_type.startswith("image/")
            ],
            source_conflicts=AcademicProblemSolverService._dicts(
                canonical.get("source_conflicts", []), "description"
            ),
            uncertain_info=AcademicProblemSolverService._dicts(
                canonical.get("uncertain_info", []), "description"
            ),
            critical_missing_info=AcademicProblemSolverService._dicts(
                canonical.get("critical_missing_info", []), "field"
            ),
            retrieval_keywords=[
                str(item) for item in canonical.get("retrieval_keywords", [])
            ],
            required_capabilities=[
                str(item) for item in canonical.get("required_capabilities", [])
            ],
            structure_status=str(canonical.get("structure_status", "partial")),
            can_continue=bool(canonical.get("can_continue", True)),
            extraction_confidence=float(canonical.get("extraction_confidence", 0.7)),
        )

    @staticmethod
    def _text(canonical: dict[str, Any]) -> str:
        for key in ("problem_text", "question", "text"):
            value = str(canonical.get(key, "")).strip()
            if value:
                return value
        return ""

    @staticmethod
    def _dicts(value: Any, key: str) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item if isinstance(item, dict) else {key: str(item)} for item in value]

    @staticmethod
    def _visual_task_type(course: str) -> str:
        return (
            "circuit_image_extraction"
            if course.upper() == "CT"
            else "academic_image_extraction"
        )

    @staticmethod
    def _visual_extraction_instruction() -> str:
        return (
            " 只输出可观察内容，不补造参数。电路或逻辑图必须逐个子图列出器件、"
            "器件端点与节点连接、控制端、极性、参考方向和标号；波形图必须列出"
            "分段区间、关键坐标、跳变以及端点是否包含。先覆盖全部子图，再描述"
            "不确定项，不得用通用电路类型替代实际拓扑。优先输出 JSON 对象，字段为"
            " recognized_text（字符串数组）、diagram_description（字符串）、components"
            "（数组；每项包含 component_type、label、value、connections、certainty）、"
            "uncertain_info（字符串数组）和 confidence（0 到 1）；若无法可靠结构化，"
            "仍需保留不确定项，不得臆造连接。"
        )

    @staticmethod
    def _parse_visual_extraction(content: str) -> VisionExtraction | None:
        """Parse a typed envelope without requiring every provider to emit JSON."""
        decoder = json.JSONDecoder()
        for index, character in enumerate(content):
            if character != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(content[index:])
            except json.JSONDecodeError:
                continue
            try:
                return VisionExtraction.model_validate(payload)
            except ValidationError:
                continue
        return None

    @staticmethod
    def _merge_visual_extraction(
        problem: AcademicProblem,
        content: str,
        *,
        section_title: str = "图片结构化提取",
    ) -> tuple[AcademicProblem, dict[str, Any]]:
        parsed = AcademicProblemSolverService._parse_visual_extraction(content)
        if parsed is None:
            return (
                problem.model_copy(
                    update={
                        "problem_text": (
                            f"{problem.problem_text}\n\n[{section_title}]\n{content}"
                        )[:50_000],
                        "uncertain_info": [
                            *problem.uncertain_info,
                            {"description": "图片内容由视觉模型提取，需以原图为准"},
                        ],
                    }
                ),
                {
                    "structured_extraction": False,
                    "visual_structure_status": "unstructured",
                    "visual_component_count": 0,
                    "visual_relation_count": 0,
                },
            )

        entities = [
            {
                "component_type": item.component_type,
                "label": item.label,
                "value": item.value,
                "connections": list(item.connections),
                "certainty": item.certainty,
                "source": "visual_extraction",
            }
            for item in parsed.components
        ]
        relations = [
            {
                "component": item.label or item.component_type,
                "node": connection,
                "relation_type": "connected_to",
                "certainty": item.certainty,
                "source": "visual_extraction",
            }
            for item in parsed.components
            for connection in item.connections
        ]
        topology_complete = bool(
            parsed.components
            and parsed.confidence >= 0.75
            and all(
                item.certainty == "certain"
                and len(set(item.connections)) >= 2
                for item in parsed.components
            )
        )
        recognized_text = "\n".join(parsed.recognized_text).strip()
        summary_parts = [parsed.diagram_description.strip()]
        if recognized_text:
            summary_parts.append(f"识别文字：{recognized_text}")
        if parsed.uncertain_info:
            summary_parts.append(
                "不确定项：" + "；".join(parsed.uncertain_info)
            )
        merged = problem.model_copy(
            update={
                "problem_text": (
                    f"{problem.problem_text}\n\n[{section_title}]\n"
                    + "\n".join(summary_parts)
                )[:50_000],
                "entities": [*problem.entities, *entities],
                "relations": [*problem.relations, *relations],
                "uncertain_info": [
                    *problem.uncertain_info,
                    *({"description": item} for item in parsed.uncertain_info),
                    {"description": "图片内容由视觉模型提取，需以原图为准"},
                ],
                "structure_status": (
                    "complete" if topology_complete else problem.structure_status
                ),
                "can_continue": problem.can_continue and topology_complete,
                "extraction_confidence": min(
                    problem.extraction_confidence,
                    parsed.confidence,
                ),
            }
        )
        return (
            merged,
            {
                "structured_extraction": True,
                "visual_structure_status": (
                    "complete" if topology_complete else "partial"
                ),
                "visual_component_count": len(entities),
                "visual_relation_count": len(relations),
                "visual_extraction_confidence": parsed.confidence,
            },
        )

    @staticmethod
    def _retrieved_context(context: Any, *, max_chars: int = 4_000) -> str:
        if context is None or not getattr(context, "evidence", []):
            return ""
        formatter = getattr(context, "to_retrieved_context", None)
        if callable(formatter):
            value = str(formatter()).strip()
        else:
            value = str(getattr(context, "retrieved_context", "")).strip()
        return value[:max_chars]

    @staticmethod
    def _citations(context: Any) -> list[dict[str, Any]]:
        if context is None:
            return []
        values: list[dict[str, Any]] = []
        for item in getattr(context, "evidence", []):
            values.append(
                {
                    "source_ref": str(getattr(item, "source_ref", "")),
                    "title": str(getattr(item, "title", "")),
                    "score": float(getattr(item, "score", 0) or 0),
                }
            )
        return values
