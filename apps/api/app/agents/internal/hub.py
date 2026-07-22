from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.agents.internal.contracts import (
    AcademicWritingDraft,
    AssignmentReviewDraft,
    CircuitPlan,
    CourseClassification,
    DataAnalysisExplanation,
    IntentClassification,
    InternalAgentResult,
    LessonPrepDraft,
    QueryRewrite,
    VisionExtraction,
)
from app.contracts import ImageInput, ModelResponse, ModelUsage
from app.core.errors import InvalidModelRequestError, ModelProviderError
from app.services.model_service import ModelService


@dataclass(frozen=True, slots=True)
class InternalAgentDefinition:
    agent_id: str
    task_type: str
    description: str
    system_prompt: str
    output_schema: type[BaseModel]
    modality: str = "text"


INTERNAL_AGENT_DEFINITIONS = (
    InternalAgentDefinition(
        "COURSE_CLASSIFIER_LOCAL_V1",
        "course_classification",
        "课程编码分类器",
        (
            "判断输入所属电子信息课程。编码映射：CT=电路理论，AE=模拟电子技术，"
            "DE=数字电子技术，SS=信号与系统，DSP=数字信号处理，COMM=通信原理，"
            "RF=高频电子线路，EM=电磁场与电磁波，INFO=信息论与编码，"
            "EMBEDDED=嵌入式系统，IC=集成电路。只依据文本，不补充事实；"
            "基础元件伏安关系、电容电感动态特性、KCL/KVL和网络定理优先归CT；"
            "运放、二极管、三极管、MOS管和放大电路优先归AE；"
            "逻辑门、触发器和时序逻辑优先归DE；"
            "不确定时输出UNKNOWN。"
        ),
        CourseClassification,
    ),
    InternalAgentDefinition(
        "INTENT_CLASSIFIER_LOCAL_V1",
        "intent_classification",
        "用户意图分类器",
        "判断用户意图并输出允许的intent枚举；不确定时输出unknown。",
        IntentClassification,
    ),
    InternalAgentDefinition(
        "QUERY_REWRITER_LOCAL_V1",
        "query_rewrite",
        "RAG查询改写器",
        (
            "为课程知识检索改写查询。必须保留数值、单位、参考方向、"
            "否定条件和课程约束，不得生成答案。"
        ),
        QueryRewrite,
    ),
    InternalAgentDefinition(
        "CIRCUIT_PLANNER_LOCAL_V1",
        "complex_circuit_reasoning",
        "电路求解规划器",
        (
            "只规划电路求解步骤，不伪造元件参数、拓扑或参考方向。"
            "信息不足时列入missing_information；确定性计算必须交给工具复核。"
        ),
        CircuitPlan,
    ),
    InternalAgentDefinition(
        "CIRCUIT_VISION_EXTRACTOR_LOCAL_V1",
        "circuit_image_extraction",
        "电路图结构提取器",
        (
            "提取图片中的文字、元件、连接与不确定信息。不得把不清楚的"
            "元件或箭头强行认定为确定事实。描述必须简短；每个元件只输出"
            "component_type、label、value、connections、certainty，不列出缺失字段。"
        ),
        VisionExtraction,
        modality="image",
    ),
    InternalAgentDefinition(
        "LESSON_PREP_LOCAL_V1",
        "lesson_prep",
        "本地备课草稿Agent",
        (
            "生成可人工复核的电子信息课程教案草稿。目标、流程和检查点"
            "必须具体；没有资料依据的内容放入warnings。"
        ),
        LessonPrepDraft,
    ),
    InternalAgentDefinition(
        "ASSIGNMENT_REVIEW_LOCAL_V1",
        "assignment_review",
        "本地作业初审Agent",
        (
            "进行作业初审而非最终评分。区分正确部分、错误和不确定项；"
            "缺少题目、标准或评分规则时必须review_required=true。"
        ),
        AssignmentReviewDraft,
    ),
    InternalAgentDefinition(
        "ACADEMIC_WRITING_LOCAL_V1",
        "academic_writing",
        "本地学术写作Agent",
        (
            "只改写用户提供的文本，不虚构实验、引用、数据或结论；"
            "无法由输入支持的主张列入unsupported_claims。"
        ),
        AcademicWritingDraft,
    ),
    InternalAgentDefinition(
        "DATA_ANALYSIS_LOCAL_V1",
        "data_analysis_explanation",
        "本地数据分析解释Agent",
        (
            "根据用户已提供的数据或统计结果解释分析。没有真实数据时只给"
            "分析计划，analysis_status必须是plan或insufficient_data。"
        ),
        DataAnalysisExplanation,
    ),
)


class InternalAgentHub:
    """Model-backed subordinate agents; it does not replace the workflow registry."""

    def __init__(self, model_service: ModelService) -> None:
        self.model_service = model_service
        self._definitions = {item.agent_id: item for item in INTERNAL_AGENT_DEFINITIONS}
        self._validate_routes()

    def list_agents(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for definition in self._definitions.values():
            route = self.model_service.registry.get_route(definition.task_type)
            model = self.model_service.registry.get_model(route.primary)
            provider = self.model_service.providers.get(model.provider)
            configured = bool(provider and provider.configured)
            if model.provider == "iflytek_spark":
                normalizer_route = self.model_service.registry.get_route(
                    "structured_output_normalization"
                )
                normalizer_model = self.model_service.registry.get_model(
                    normalizer_route.primary
                )
                normalizer_provider = self.model_service.providers.get(
                    normalizer_model.provider
                )
                configured = configured and bool(
                    normalizer_provider and normalizer_provider.configured
                )
            result.append(
                {
                    "agent_id": definition.agent_id,
                    "task_type": definition.task_type,
                    "description": definition.description,
                    "modality": definition.modality,
                    "primary_model_alias": route.primary,
                    "fallback_model_alias": route.fallback,
                    "configured": configured,
                    "enabled": self.model_service.registry.enabled(model),
                }
            )
        return result

    @property
    def definitions(self) -> tuple[InternalAgentDefinition, ...]:
        return tuple(self._definitions.values())

    async def run_text(
        self,
        agent_id: str,
        *,
        input_text: str,
        request_id: str | None = None,
        max_tokens: int | None = None,
    ) -> InternalAgentResult:
        definition = self._get(agent_id)
        if definition.modality != "text":
            raise InvalidModelRequestError(
                f"内部Agent {agent_id} 需要图片输入",
                model=definition.task_type,
            )
        if not input_text.strip():
            raise InvalidModelRequestError("内部Agent输入不能为空", model=agent_id)
        options = {"max_tokens": max_tokens} if max_tokens is not None else None
        schema_json = self._schema_json(definition)
        route = self.model_service.registry.get_route(definition.task_type)
        primary = self.model_service.registry.get_model(route.primary)
        if primary.provider == "iflytek_spark":
            response = await self._reason_then_structure(
                definition,
                input_text=input_text.strip(),
                schema_json=schema_json,
                request_id=request_id,
                max_tokens=max_tokens,
            )
            return self._result(definition, response)
        response = await self.model_service.generate_json_for_task(
            definition.task_type,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{definition.system_prompt}\n"
                        "只输出符合下列JSON Schema的对象，不要解释或使用Markdown：\n"
                        f"{schema_json}"
                    ),
                },
                {"role": "user", "content": input_text.strip()},
            ],
            schema=definition.output_schema,
            request_id=request_id,
            extra_options=options,
        )
        return self._result(definition, response)

    async def _reason_then_structure(
        self,
        definition: InternalAgentDefinition,
        *,
        input_text: str,
        schema_json: str,
        request_id: str | None,
        max_tokens: int | None,
    ) -> ModelResponse:
        draft_options = {"max_tokens": max_tokens} if max_tokens is not None else None
        draft = await self.model_service.generate_for_task(
            definition.task_type,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{definition.system_prompt}\n"
                        "先生成完整、可核验的业务草稿；不要输出隐藏思考过程。"
                    ),
                },
                {"role": "user", "content": input_text},
            ],
            request_id=request_id,
            extra_options=draft_options,
        )
        normalization_limit = min(max_tokens or 384, 384)
        try:
            normalized = await self.model_service.generate_json_for_task(
                "structured_output_normalization",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "把上游草稿转换为指定JSON对象。不得添加草稿中没有的数值、"
                            "引用、条件或结论；缺失项使用空列表或保守状态。"
                            "只输出JSON，不要解释。\nJSON Schema:\n"
                            f"{schema_json}"
                        ),
                    },
                    {"role": "user", "content": draft.content},
                ],
                schema=definition.output_schema,
                request_id=request_id,
                extra_options={"max_tokens": normalization_limit},
            )
        except ModelProviderError as exc:
            downstream_usage = exc.details.get("usage", {})
            if not isinstance(downstream_usage, dict):
                downstream_usage = {}
            draft_usage = draft.usage or ModelUsage()
            exc.details["usage"] = {
                "prompt_tokens": self._sum_optional(
                    draft_usage.prompt_tokens,
                    self._optional_int(downstream_usage.get("prompt_tokens")),
                ),
                "completion_tokens": self._sum_optional(
                    draft_usage.completion_tokens,
                    self._optional_int(downstream_usage.get("completion_tokens")),
                ),
                "total_tokens": self._sum_optional(
                    draft_usage.total_tokens,
                    self._optional_int(downstream_usage.get("total_tokens")),
                ),
            }
            exc.details["elapsed_ms"] = draft.elapsed_ms + int(
                exc.details.get("elapsed_ms") or 0
            )
            exc.details["pipeline"] = "reason_then_structure"
            raise
        draft_usage = draft.usage or ModelUsage()
        normalized_usage = normalized.usage or ModelUsage()
        usage = ModelUsage(
            prompt_tokens=self._sum_optional(
                draft_usage.prompt_tokens, normalized_usage.prompt_tokens
            ),
            completion_tokens=self._sum_optional(
                draft_usage.completion_tokens, normalized_usage.completion_tokens
            ),
            total_tokens=self._sum_optional(
                draft_usage.total_tokens, normalized_usage.total_tokens
            ),
        )
        return normalized.model_copy(
            update={
                "provider": f"{draft.provider}+{normalized.provider}",
                "model": f"{draft.model}->{normalized.model}",
                "usage": usage,
                "elapsed_ms": draft.elapsed_ms + normalized.elapsed_ms,
                "raw_metadata": {
                    "pipeline": "reason_then_structure",
                    "draft_provider_request_id": draft.provider_request_id,
                    "normalized_provider_request_id": normalized.provider_request_id,
                },
            }
        )

    async def run_vision(
        self,
        agent_id: str,
        *,
        prompt: str,
        images: list[ImageInput],
        request_id: str | None = None,
        max_tokens: int | None = None,
        high_resolution: bool | None = None,
    ) -> InternalAgentResult:
        definition = self._get(agent_id)
        if definition.modality != "image":
            raise InvalidModelRequestError(
                f"内部Agent {agent_id} 不接受图片输入",
                model=definition.task_type,
            )
        options = {"max_tokens": max_tokens} if max_tokens is not None else None
        schema_json = self._schema_json(definition)
        response = await self.model_service.analyze_images_for_task(
            definition.task_type,
            prompt=(
                f"{definition.system_prompt}\n"
                "只输出符合下列JSON Schema的对象，不要解释或使用Markdown：\n"
                f"{schema_json}\n\n用户任务：{prompt.strip()}"
            ),
            images=images,
            request_id=request_id,
            json_mode=True,
            high_resolution=high_resolution,
            extra_options=options,
        )
        structured = definition.output_schema.model_validate_json(response.content)
        normalized = response.model_copy(
            update={
                "content": json.dumps(
                    structured.model_dump(mode="json"), ensure_ascii=False
                )
            }
        )
        return self._result(definition, normalized)

    def _get(self, agent_id: str) -> InternalAgentDefinition:
        try:
            return self._definitions[agent_id]
        except KeyError as exc:
            raise InvalidModelRequestError(
                f"内部Agent未注册: {agent_id}", model=agent_id
            ) from exc

    def _validate_routes(self) -> None:
        for definition in self._definitions.values():
            self.model_service.registry.get_route(definition.task_type)
        self.model_service.registry.get_route("structured_output_normalization")

    @staticmethod
    def _schema_json(definition: InternalAgentDefinition) -> str:
        return json.dumps(
            definition.output_schema.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @staticmethod
    def _sum_optional(left: int | None, right: int | None) -> int | None:
        if left is None and right is None:
            return None
        return (left or 0) + (right or 0)

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        return int(value) if value is not None else None

    @staticmethod
    def _result(
        definition: InternalAgentDefinition, response: ModelResponse
    ) -> InternalAgentResult:
        structured = json.loads(response.content)
        usage = response.usage
        return InternalAgentResult(
            agent_id=definition.agent_id,
            task_type=definition.task_type,
            provider=response.provider,
            model=response.model,
            content=response.content,
            structured_result=structured,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            elapsed_ms=response.elapsed_ms,
            provider_request_id=response.provider_request_id,
        )
