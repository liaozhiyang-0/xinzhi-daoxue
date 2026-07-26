from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from app.contracts import (
    AgentRequest,
    AgentResult,
    Artifact,
    ArtifactType,
    ImageInput,
    ModelResponse,
    RunMetrics,
)
from app.contracts.solver import AcademicProblem
from app.core.config import Settings
from app.core.errors import AppError
from app.multimodal import MultiImageComposer, PreparedImageBatch, SourceImage
from app.orchestrator.graphs import AcademicProblemSolverGraph
from app.orchestrator.state import new_graph_state
from app.services.math_formatting_service import MATH_OUTPUT_INSTRUCTION

if TYPE_CHECKING:
    from app.services.model_service import ModelService
    from app.services.storage import StorageService


class AcademicProblemSolverService:
    """Adapts the universal graph to the existing TaskRunner contract."""

    agent_id = "ACADEMIC_PROBLEM_SOLVER"
    completion_marker = "<!-- XZD_ACADEMIC_COMPLETE -->"

    def __init__(
        self,
        graph: AcademicProblemSolverGraph,
        model_service: ModelService | None = None,
        storage: StorageService | None = None,
    ) -> None:
        self.graph = graph
        self.model_service = model_service
        self.storage = storage

    async def run(self, request: AgentRequest, context: Any = None) -> AgentResult:
        problem = self._problem_from_request(request)
        problem, vision_execution = await self._extract_visual_context(request, problem)
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
        result = self.graph.run(problem, retrieved_chunks=citations, state=state)
        request_id = str(request.options.get("request_id", request.task_id))
        result, model_execution = await self._generate_with_model(
            problem, result, request_id=request_id
        )
        if model_execution.get("output_status") == "partial":
            verification_model_execution = {
                "status": "skipped",
                "reason": "generation_incomplete",
            }
        else:
            result, verification_model_execution = await self._review_high_risk(
                problem, result, request_id=request_id
            )
        structured = result.model_dump(mode="json")
        if vision_execution:
            structured["vision_execution"] = vision_execution
        if model_execution:
            structured["model_execution"] = model_execution
        if verification_model_execution:
            structured["verification_model_execution"] = verification_model_execution
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
                model_calls=sum(
                    int(
                        item.get(
                            "model_calls",
                            1
                            if item.get("status") in {"completed", "partial"}
                            else 0,
                        )
                    )
                    for item in (
                        vision_execution,
                        model_execution,
                        verification_model_execution,
                    )
                ),
                tool_calls=len(result.tool_verification),
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
        self, request: AgentRequest, problem: AcademicProblem
    ) -> tuple[AcademicProblem, dict[str, Any]]:
        images = [
            item
            for item in request.attachments
            if item.content_type.startswith("image/")
        ]
        task_type = (
            "circuit_image_extraction"
            if problem.course == "CT"
            else "simple_image_understanding"
        )
        if (
            not images
            or self.model_service is None
            or self.storage is None
            or not self._model_route_available(task_type)
        ):
            return problem, {}
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
                )
            pack = self.graph.courses.get(problem.course)
            response = await self.model_service.analyze_images_for_task(
                task_type,
                prompt=(
                    pack.build_extraction_prompt(problem)
                    + (
                        " 这是按原始顺序拼接的组合图，每个区域标有 Image 编号；"
                        if prepared.strategy == "stitched"
                        else ""
                    )
                    + " 只输出可观察到的实体、关系、标注和不确定项，不补造参数。"
                ),
                images=list(prepared.images),
                request_id=str(request.options.get("request_id", "")) or None,
                json_mode=False,
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
        return (
            problem.model_copy(
                update={
                    "problem_text": (
                        f"{problem.problem_text}\n\n[图片结构化提取]\n{visual_summary}"
                    )[:50_000],
                    "uncertain_info": [
                        *problem.uncertain_info,
                        {"description": "图片内容由视觉模型提取，需以原图为准"},
                    ],
                }
            ),
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
                "composite_width": prepared.composite_width,
                "composite_height": prepared.composite_height,
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
                try:
                    response = await model_service.analyze_images_for_task(
                        task_type,
                        prompt=(
                            pack.build_extraction_prompt(problem)
                            + f" 当前是第 {index}/{prepared.source_count} 张图，"
                            "请保留跨图衔接所需的节点名、题号、方向、参数和不确定项；"
                            "只描述可观察内容，不补造参数。"
                        ),
                        images=[image],
                        request_id=(
                            str(request.options.get("request_id", "")) or None
                        ),
                        json_mode=False,
                    )
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
        )
        visual_summary = summary[:50_000]
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
                str(item.get("model", ""))
                for item in completed
                if item.get("model")
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
        return (
            problem.model_copy(
                update={
                    "problem_text": (
                        f"{problem.problem_text}\n\n[多图内容汇总]\n{visual_summary}"
                    )[:50_000],
                    "uncertain_info": uncertain,
                }
            ),
            {
                "status": "partial" if failed else "completed",
                "strategy": "per_image",
                "fallback_reason": prepared.fallback_reason,
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
                "individual_executions": [
                    {key: value for key, value in item.items() if key != "content"}
                    for item in executions
                ],
                "summary_execution": summary_execution,
            },
        )

    async def _summarize_image_extractions(
        self,
        *,
        request: AgentRequest,
        problem: AcademicProblem,
        extracted_text: str,
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
        try:
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
                extra_options={"max_tokens": 2048},
            )
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
        }

    async def _generate_with_model(
        self, problem: AcademicProblem, result: Any, *, request_id: str
    ) -> tuple[Any, dict[str, Any]]:
        if self.model_service is None or not self._model_route_available(
            "academic_problem_solving"
        ):
            return result, {}
        pack = self.graph.courses.get(problem.course)
        prompt = "\n".join(
            (
                pack.build_planning_prompt(problem),
                pack.build_solving_prompt(problem),
                "必须明确假设、关键方程和适用范围；不得补造题目事实。",
                MATH_OUTPUT_INSTRUCTION,
                (
                    "逐项完成题目全部小问；确认全部完成后，最后一行只输出"
                    f" {self.completion_marker}"
                ),
                f"题目：{problem.problem_text}",
                f"已知结构：{problem.model_dump_json(exclude_none=True)[:8000]}",
            )
        )
        max_tokens, max_continuations, timeout_seconds = self._generation_limits()
        try:
            response = await self.model_service.generate_for_task(
                "academic_problem_solving",
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
                    "timeout": timeout_seconds,
                },
            )
        except AppError as exc:
            return (
                result.model_copy(
                    update={
                        "remaining_risks": [
                            *result.remaining_risks,
                            f"统一模型服务不可用，保留确定性结果: {exc.code}",
                        ]
                    }
                ),
                {"status": "failed", "error_type": exc.code},
            )
        responses = [response]
        answer = response.content.strip()
        require_completion_marker = len(problem.problem_text) >= 1200
        truncated = self._response_truncated(
            response,
            max_tokens,
            require_completion_marker=require_completion_marker,
        )
        truncation_detected = truncated
        continuation_error: str | None = None
        continuation_count = 0
        while truncated and continuation_count < max_continuations:
            continuation_count += 1
            answer = self._trim_incomplete_tail(answer)
            try:
                response = await self.model_service.generate_for_task(
                    "academic_problem_solving",
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
                    extra_options={
                        "max_tokens": max_tokens,
                        "timeout": timeout_seconds,
                    },
                )
            except AppError as exc:
                continuation_error = exc.code
                break
            responses.append(response)
            continuation = response.content.strip()
            if continuation:
                answer = (
                    f"{answer}\n\n### 续答（第 {continuation_count} 部分）\n\n"
                    f"{continuation}"
                )
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
                        "model_calls": len(responses),
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
                "provider": response.provider,
                "model": response.model,
                "elapsed_ms": sum(item.elapsed_ms for item in responses),
                "model_calls": len(responses),
                "continuation_count": continuation_count,
                "max_tokens_per_call": max_tokens,
                "timeout_seconds_per_call": timeout_seconds,
                "finish_reasons": [item.finish_reason for item in responses],
                "truncation_detected": truncation_detected,
                "continuation_error": continuation_error,
                "usage": self._combined_usage(responses),
            },
        )

    def _generation_limits(self) -> tuple[int, int, float]:
        if self.model_service is None:
            return 4096, 2, 240
        settings = getattr(self.model_service, "settings", None)
        if settings is None:
            return 4096, 2, 240
        return (
            min(
                int(settings.academic_solver_max_tokens),
                int(settings.iflytek_spark_max_tokens),
            ),
            int(settings.academic_solver_max_continuations),
            float(settings.academic_solver_timeout_seconds),
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
        if (
            require_completion_marker
            and cls.completion_marker not in response.content
        ):
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
                "上一段回答因输出长度或公式未闭合而中断。",
                f"这是第 {continuation_number} 次续答。",
                "从被中断处继续；先完整重写被截断的最后一句或公式。",
                "完成题目所有尚未回答的小问，不重复已经完成的内容。",
                "保持 Markdown/LaTeX 结构闭合，不补造工具结果或题目事实。",
                (
                    "确认全部小问完成后，最后一行只输出"
                    f" {AcademicProblemSolverService.completion_marker}"
                ),
                f"原题：{problem_text[:16000]}",
                f"已生成回答末尾：{answer[-12000:]}",
            )
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

    async def _review_high_risk(
        self, problem: AcademicProblem, result: Any, *, request_id: str
    ) -> tuple[Any, dict[str, Any]]:
        if result.execution_path != "HIGH_RISK":
            return result, {}
        reviewed = self.graph.verify_high_risk(problem, result)
        report = reviewed.verification_report
        if (
            report is None
            or not report.requires_patch
            or self.model_service is None
            or not self.model_service.settings.enable_dual_model_verification
            or not self._verifier_available("academic_problem_solving")
        ):
            return reviewed, {}
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
            response = await self.model_service.verify_with_secondary_model(
                "academic_problem_solving",
                messages=[
                    {"role": "system", "content": "你是受限的关键问题审核节点。"},
                    {"role": "user", "content": prompt},
                ],
                request_id=request_id,
            )
        except AppError as exc:
            return reviewed, {"status": "failed", "error_type": exc.code}
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
        }

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
