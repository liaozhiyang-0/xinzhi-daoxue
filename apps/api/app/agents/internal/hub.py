from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.agents.internal.contracts import (
    AcademicPaperReview,
    AcademicSearchPlan,
    AcademicWritingDraft,
    AssignmentReviewDraft,
    CircuitPlan,
    CourseClassification,
    DataAnalysisExplanation,
    IntentClassification,
    InternalAgentResult,
    LessonPrepDraft,
    OverallRouteDecision,
    QueryRewrite,
    VisionExtraction,
)
from app.contracts import ImageInput, ModelResponse, ModelUsage
from app.contracts.reflection import CriticResult, RevisionProposal
from app.contracts.research import ResearchBriefDraft, ResearchIntentDecision
from app.core.errors import (
    InvalidModelRequestError,
    ModelProviderError,
    StructuredOutputError,
)
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
        "REFLECTION_CRITIC_LOCAL_V1",
        "reflection_critic",
        "只读已有草稿、证据和工具观察的内部 Reflection Critic",
        (
            "你是芯智导学的内部答案审核器，不是公开Agent。只能检查输入中的草稿、"
            "已有evidence_refs、工具观察和确定性校验结果。不得补造事实、引用或工具结果。"
            "只输出CriticResult；如果没有明确问题输出pass；如果问题可由已有证据支持的局部修改"
            "解决输出revise；证据不足或无法安全修改输出needs_review或fail。"
        ),
        CriticResult,
    ),
    InternalAgentDefinition(
        "REFLECTION_REVISION_LOCAL_V1",
        "reflection_revision",
        "只执行一次、仅按 CriticResult 约束修改草稿的内部 Revision Worker",
        (
            "你是芯智导学的内部受限修订器。只能修改CriticResult.required_changes明确指出的"
            "答案或业务字段；必须保留所有引用、工具结果、证据ID、确定性校验观察和任务范围。"
            "不得新增输入中不存在的事实。只输出RevisionProposal；无法安全修订时输出failed。"
        ),
        RevisionProposal,
    ),
    InternalAgentDefinition(
        "OVERALL_ROUTER_LOCAL_V1",
        "overall_routing",
        "在真正执行任务前，根据原始输入和候选路径选择一个业务 Agent",
        (
            "你是芯智导学的总体路由器，只负责选择 Agent，不回答用户问题。"
            "必须根据原始用户输入，从候选路径中选择一个最合适的 target_agent_id。"
            "论文检索与学术写作必须严格区分：查找/推荐/最新论文进入 "
            "RESEARCH_01_ACADEMIC_SEARCH_V1，"
            "改写/润色/摘要写作进入 RESEARCH_02_ACADEMIC_WRITING_V1。"
            "不确定时选择 GENERAL_QUESTION_V1；只输出符合 JSON Schema 的对象。"
        ),
        OverallRouteDecision,
    ),
    InternalAgentDefinition(
        "ACADEMIC_PAPER_REVIEW_LOCAL_V1",
        "academic_paper_review",
        "论文检索结果相关性审核Agent",
        (
            "你是论文检索结果审核器。逐条判断候选论文是否真正回答用户指定的领域或主题。"
            "必须同时检查标题、摘要、来源和日期；跨领域、标题摘要不匹配、摘要为空、"
            "明显未来日期或只有泛化词命中的记录必须 approved=false。"
            "日期判断必须以用户输入JSON中的as_of_date为准，发布日期早于或等于该日期"
            "不得因为年份是当前年份就判为未来。"
            "如果用户只指定宽泛领域（例如人工智能），只要论文核心方法或研究对象明确属于"
            "人工智能、机器学习、深度学习、生成式AI、计算机视觉、自然语言处理、强化学习、"
            "神经网络或智能系统，就可以 approved=true，不要要求论文必须属于"
            "电子信息课程。"
            "只有主题明确匹配且摘要足以支持相关性的论文才 approved=true。"
            "必须覆盖输入中的每个 evidence_id，只输出JSON，不补造论文信息。"
        ),
        AcademicPaperReview,
    ),
    InternalAgentDefinition(
        "ACADEMIC_SEARCH_PLANNER_LOCAL_V1",
        "academic_search_planning",
        "学术论文检索规划Agent",
        (
            "你是学术论文检索规划器，不直接回答问题。根据用户原始输入提取研究主题、"
            "领域、方法、应用场景、时间和数量要求，生成最多4组适合学术数据库的检索词。"
            "如果research_intent要求报道或会议，检索词应额外覆盖news、industry report、"
            "conference、workshop、symposium等来源线索，但不能把报道当成论文。"
            "必须同时生成中文和英文表达；详细主题要拆成核心概念组合，例如医学影像要考虑"
            "medical imaging、radiology、medical image analysis、radiomics、"
            "computer vision、"
            "deep learning等相关表达，但不要无依据扩展到无关学科。"
            "minimum_results必须识别用户的‘至少N篇’要求，未明确时默认为4。只输出JSON。"
        ),
        AcademicSearchPlan,
    ),
    InternalAgentDefinition(
        "RESEARCH_INTENT_CLASSIFIER_LOCAL_V1",
        "research_intent_classification",
        "科研检索目标与来源类型识别Agent",
        (
            "你是科研情报检索意图识别器。根据用户原始问题判断其真正目标，区分前沿综述、"
            "论文检索、新闻/产业报道、会议雷达、技术对比、解释和追问。判断是否必须联网；"
            "涉及近况、最新、研究进展、报道、会议或要求来源时必须 requires_web=true。"
            "source_kinds只能从 academic_paper、web_report、conference 中选择；"
            "不得编造主题。"
            "只输出JSON。"
        ),
        ResearchIntentDecision,
    ),
    InternalAgentDefinition(
        "RESEARCH_FRONTIER_BRIEF_LOCAL_V1",
        "research_frontier_brief",
        "科研前沿证据简报生成Agent",
        (
            "你是科研前沿证据简报生成器。只能根据输入的已检索证据作出归纳，不能补造论文、"
            "会议、报道、日期、数据或结论。每个关键判断必须引用一个或多个输入 "
            "evidence_id；"
            "如果证据不足，明确写入limitations或open_questions。区分论文、报道和会议来源，"
            "给出研究意义、时间线、证据缺口和下一步检索建议。只输出JSON。"
        ),
        ResearchBriefDraft,
    ),
    InternalAgentDefinition(
        "RESEARCH_FRONTIER_KNOWLEDGE_LOCAL_V1",
        "research_frontier_brief",
        "无外部证据时生成带边界声明的本地科研知识初步回答Agent",
        (
            "你是科研前沿知识初步回答Agent。外部证据不可用时，根据稳定的基础科研知识回答用户问题，"
            "但不得编造论文、作者、日期、数值或实验结果。必须明确这是本地知识初步回答，"
            "把无法由当前输入核验的内容放入limitations或open_questions；key_findings至少覆盖"
            "输入中的多个research_questions，并且所有evidence_ids必须为空。只输出JSON。"
        ),
        ResearchBriefDraft,
    ),
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
            "生成可人工复核的电子信息课程教案草稿，必须紧扣用户指定的课程主题，"
            "不能把检索不到的其他章节或其他学科内容替换进来。目标、流程、带解例题、"
            "常见混淆、分层练习和出口条要具体；每个关键判断在evidence_notes中写明"
            "真实检索结果中的[S#]依据，或明确写‘资料不足’；禁止编造[S#]编号或来源。"
            "用户指定数量时严格遵守（例如要求3个目标就只输出3个）。没有资料时仍完成结构化草稿，但把缺口写入"
            "missing_information和warnings，teacher_review列出复核点，publishable必须为false。"
        ),
        LessonPrepDraft,
    ),
    InternalAgentDefinition(
        "ASSIGNMENT_REVIEW_LOCAL_V1",
        "assignment_review",
        "本地作业初审Agent",
        (
            "进行作业初审而非最终评分，严格围绕用户给出的题目和学生步骤。保留正确的"
            "建模步骤，指出第一次导致后续结论失效的错误，并解释错误传播；按要求给出"
            "基础/进阶提示和只改一个参数的验证任务。缺少标准答案、评分规则或电路参数"
            "时必须review_required=true，并将缺口列入missing_information和teacher_review，"
            "不得臆造总分或[S#]来源编号。"
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
        "模型主导的数据分析Agent",
        (
            "你负责直接分析用户提供的数据，不要把任务退化为泛泛的规律总结。"
            "必须先理解研究问题、研究设计、变量角色、数据质量和分析目标，再选择适合的分析方法；"
            "可以使用数据中的原始数值进行计算和比较，但不得伪造缺失数据、样本量、p值、区间或技术指标。"
            "如果数据、变量角色或研究设计不足以支持结论，analysis_status只能是plan或insufficient_data，"
            "并明确指出还缺什么。结果必须区分描述性发现、关联、预测和因果解释；随机实验也要说明随机分配和目标人群边界。"
            "summary、findings、effect_estimates、uncertainty、diagnostics、robustness和conclusion_boundary"
            "必须围绕用户问题填写；steps只用于系统内部，不直接展示给用户。除变量名、公式和原始数据值外，"
            "所有输出字段使用简体中文，只输出JSON。"
        ),
        DataAnalysisExplanation,
    ),
)


class InternalAgentHub:
    """Model-backed subordinate agents; it does not replace the workflow registry."""

    _STRUCTURED_RECOVERY_MAX_TOKENS = 2048

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
        extra_options: dict[str, Any] | None = None,
    ) -> InternalAgentResult:
        definition = self._get(agent_id)
        if definition.modality != "text":
            raise InvalidModelRequestError(
                f"内部Agent {agent_id} 需要图片输入",
                model=definition.task_type,
            )
        if not input_text.strip():
            raise InvalidModelRequestError("内部Agent输入不能为空", model=agent_id)
        options = dict(extra_options or {})
        if max_tokens is not None:
            options["max_tokens"] = max_tokens
        schema_json = self._schema_json(definition)
        route = self.model_service.registry.get_route(definition.task_type)
        primary = self.model_service.registry.get_model(route.primary)
        if primary.provider == "iflytek_spark" and not bool(
            options.get("_prefer_route_fallback", False)
        ):
            response = await self._reason_then_structure(
                definition,
                input_text=input_text.strip(),
                schema_json=schema_json,
                request_id=request_id,
                max_tokens=max_tokens,
                extra_options=options,
            )
            return self._result(definition, response)
        response = await self._generate_json_with_recovery(
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
            max_tokens=max_tokens,
            extra_options=options,
        )
        return self._result(definition, response)

    async def _generate_json_with_recovery(
        self,
        task_type: str,
        *,
        messages: list[dict[str, Any]],
        schema: type[BaseModel],
        request_id: str | None,
        max_tokens: int | None,
        extra_options: dict[str, Any],
    ) -> ModelResponse:
        try:
            return await self.model_service.generate_json_for_task(
                task_type,
                messages=messages,
                schema=schema,
                request_id=request_id,
                extra_options=extra_options,
            )
        except StructuredOutputError as exc:
            if not bool(exc.details.get("truncated")):
                raise
            recovery_limit = self._structured_recovery_limit(
                max_tokens or self._optional_int(extra_options.get("max_tokens"))
            )
            recovery_options = {
                **extra_options,
                "max_tokens": recovery_limit,
            }
            recovery_messages = [
                *messages,
                {
                    "role": "user",
                    "content": (
                        "上一轮结构化输出达到长度上限且未闭合。请重新输出完整JSON对象，"
                        "压缩长文本字段，不要解释，不要Markdown，不要省略必填字段。"
                    ),
                },
            ]
            try:
                recovered = await self.model_service.generate_json_for_task(
                    task_type,
                    messages=recovery_messages,
                    schema=schema,
                    request_id=request_id,
                    extra_options=recovery_options,
                )
            except ModelProviderError as recovery_error:
                recovery_error.details.update(
                    {
                        "structured_recovery_attempted": True,
                        "structured_recovery_max_tokens": recovery_limit,
                        "initial_finish_reason": exc.details.get("finish_reason"),
                        "initial_output_chars": exc.details.get("output_chars"),
                        "initial_elapsed_ms": exc.details.get("elapsed_ms", 0),
                    }
                )
                raise
            initial_usage = self._usage_from_details(exc.details)
            recovered_usage = recovered.usage or ModelUsage()
            return recovered.model_copy(
                update={
                    "usage": ModelUsage(
                        prompt_tokens=self._sum_optional(
                            initial_usage.prompt_tokens,
                            recovered_usage.prompt_tokens,
                        ),
                        completion_tokens=self._sum_optional(
                            initial_usage.completion_tokens,
                            recovered_usage.completion_tokens,
                        ),
                        total_tokens=self._sum_optional(
                            initial_usage.total_tokens,
                            recovered_usage.total_tokens,
                        ),
                    ),
                    "elapsed_ms": int(exc.details.get("elapsed_ms") or 0)
                    + recovered.elapsed_ms,
                    "raw_metadata": {
                        **recovered.raw_metadata,
                        "structured_recovery_attempted": True,
                        "structured_recovery_max_tokens": recovery_limit,
                        "initial_finish_reason": exc.details.get("finish_reason"),
                        "initial_output_chars": exc.details.get("output_chars"),
                    },
                }
            )

    @classmethod
    def _structured_recovery_limit(cls, max_tokens: int | None) -> int:
        baseline = max(512, (max_tokens or 384) * 2)
        return min(cls._STRUCTURED_RECOVERY_MAX_TOKENS, baseline)

    @staticmethod
    def _usage_from_details(details: dict[str, Any]) -> ModelUsage:
        usage = details.get("usage")
        if not isinstance(usage, dict):
            return ModelUsage()
        return ModelUsage(
            prompt_tokens=InternalAgentHub._optional_int(usage.get("prompt_tokens")),
            completion_tokens=InternalAgentHub._optional_int(
                usage.get("completion_tokens")
            ),
            total_tokens=InternalAgentHub._optional_int(usage.get("total_tokens")),
        )

    async def _reason_then_structure(
        self,
        definition: InternalAgentDefinition,
        *,
        input_text: str,
        schema_json: str,
        request_id: str | None,
        max_tokens: int | None,
        extra_options: dict[str, Any] | None = None,
    ) -> ModelResponse:
        draft_options = dict(extra_options or {})
        if max_tokens is not None:
            draft_options["max_tokens"] = max_tokens
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
            normalized = await self._generate_json_with_recovery(
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
                max_tokens=normalization_limit,
                extra_options={
                    **(extra_options or {}),
                    "max_tokens": normalization_limit,
                },
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
                    **normalized.raw_metadata,
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
            raw_metadata=response.raw_metadata,
        )
