from __future__ import annotations

import logging

from app.contracts import (
    AgentRequest,
    AgentResult,
    Artifact,
    ArtifactType,
    ModelResponse,
    RunMetrics,
)
from app.core.errors import ModelProviderError
from app.services.math_formatting_service import MATH_OUTPUT_INSTRUCTION
from app.services.model_service import ModelService

logger = logging.getLogger(__name__)


class GeneralQuestionService:
    """Answer low-confidence text requests without invoking a Xingchen workflow."""

    agent_id = "GENERAL_QUESTION_V1"
    task_type = "general_question_answer"
    _TRUNCATED_REASONS = {"length", "max_tokens"}

    def __init__(self, model_service: ModelService) -> None:
        self.model_service = model_service

    async def run(self, request: AgentRequest) -> AgentResult:
        question = self._question(request)
        messages = self._messages(request, question)
        direct_fallback = self._direct_fallback_context(request)
        max_tokens = self._max_tokens(request)
        try:
            first = await self.model_service.generate_for_task(
                self.task_type,
                messages=messages,
                request_id=str(request.options.get("request_id", "")) or None,
                extra_options={"max_tokens": max_tokens},
            )
        except ModelProviderError as exc:
            return self._unavailable_result(request, question, exc.code)
        except Exception:
            logger.exception(
                "general_question_model_unexpected_error task_id=%s",
                request.task_id,
            )
            return self._unavailable_result(
                request,
                question,
                "general_model_unexpected_error",
            )

        answer = first.content.strip()
        if not answer:
            return self._unavailable_result(
                request,
                question,
                "general_model_empty_response",
            )
        responses = [first]
        warnings: list[str] = []
        output_status = "completed"
        if (first.finish_reason or "").casefold() in self._TRUNCATED_REASONS:
            output_status = "partial"
            try:
                continuation = await self.model_service.generate_for_task(
                    self.task_type,
                    messages=[
                        *messages,
                        {"role": "assistant", "content": answer},
                        {
                            "role": "user",
                            "content": (
                                "请从上文中断处直接续写，避免重复已经给出的内容，"
                                "并完整收束回答。"
                            ),
                        },
                    ],
                    request_id=str(request.options.get("request_id", "")) or None,
                    extra_options={"max_tokens": min(max_tokens, 2048)},
                )
            except ModelProviderError:
                warnings.append("通用回答达到单次输出上限，自动续写未完成")
            except Exception:
                logger.exception(
                    "general_question_continuation_unexpected_error task_id=%s",
                    request.task_id,
                )
                warnings.append("通用回答已返回有效内容，但自动续写暂时不可用")
            else:
                responses.append(continuation)
                continuation_text = continuation.content.strip()
                if continuation_text:
                    answer = "\n\n".join((answer, continuation_text))
                    if (
                        continuation.finish_reason or ""
                    ).casefold() in self._TRUNCATED_REASONS:
                        warnings.append("通用回答已自动续写一次，仍可能不完整")
                    else:
                        output_status = "completed"
                else:
                    warnings.append("通用回答已返回有效内容，但自动续写结果为空")

        usage = self._usage(responses)
        model_execution = {
            "status": "success",
            "output_status": output_status,
            "model_calls": len(responses),
            "models": [item.model for item in responses],
            "finish_reasons": [item.finish_reason or "" for item in responses],
        }
        content = {
            "status": "completed",
            "mode": (
                "direct_model_fallback" if direct_fallback else "general_model_answer"
            ),
            "answer_text": answer,
            "question": question,
            "model_execution": model_execution,
            "source_policy": (
                "method_reference_not_cited"
                if direct_fallback.get("method_reference")
                else "no_course_evidence_claimed"
            ),
        }
        artifact = Artifact(
            artifact_type=ArtifactType.ANSWER,
            owner_id=request.user_id,
            task_id=request.task_id,
            course_id=request.course_id,
            content=content,
        )
        return AgentResult(
            agent_id=self.agent_id,
            provider="local_agent",
            answer=answer,
            structured_result=content,
            artifacts=[artifact],
            warnings=warnings,
            metrics=RunMetrics(
                provider_latency_ms=sum(item.elapsed_ms for item in responses),
                model_calls=len(responses),
                input_tokens=usage[0],
                output_tokens=usage[1],
            ),
            rag_status="disabled",
            evidence_status="not_requested",
            cloud_status="not_required",
        )

    @staticmethod
    def _question(request: AgentRequest) -> str:
        for key in ("text", "question", "problem", "query", "prompt"):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "请说明你希望了解的问题。"

    @staticmethod
    def _messages(request: AgentRequest, question: str) -> list[dict[str, str]]:
        direct_fallback = GeneralQuestionService._direct_fallback_context(request)
        if direct_fallback:
            system = (
                "你是芯智导学的最终直接回答模型。上游专业流程没有形成可展示的"
                "完整答案；请忽略任何占位结果，直接根据用户原问题完成回答。"
                "不要提及路由、上游失败、模型切换、内部工作流或占位结果。"
                "专业计算题应给出结论、必要公式与关键推导；条件不足时优先给出"
                "符号解、分情况结论和可继续计算的方法，只在确实无法唯一确定时"
                "明确列出最少缺失条件。不得补造数值、连接关系、图中信息或引用。"
                "课程资料片段只能作为方法参考，不得声称它直接证明了题目中的"
                "具体数值或拓扑。若上下文提供“上游视觉读取结果”，表示用户图片"
                "已经被视觉模型读取；必须使用其中的题干、参数和拓扑直接解答，"
                "不得声称无法查看图片、无法访问附件或要求用户重新上传。"
                f"{MATH_OUTPUT_INSTRUCTION}"
            )
        else:
            system = (
                "你是芯智导学的通用问题回答助手。专用课程或业务工作流无法确定时，"
                "直接回答用户的普通文本问题，不要求用户重新选择Agent。回答应准确、"
                "自然并与问题复杂度匹配；日常常识、生活、语言和一般科普问题直接给出"
                "简洁答案，不套用课程求解模板，不输出进度、路由或工作流说明，也不强制"
                "使用标题、分点或多级结构。严格遵守用户提出的字数、受众、语气、格式和"
                "是否使用公式等限制；不知道或缺少关键条件时明确说明。"
                "不得声称使用了未提供的课程资料、实时互联网、实验数据或参考文献，"
                "不得编造引文。涉及医疗、法律、金融或人身安全等高风险主题时，只提供"
                "一般信息和风险提示，不替代专业判断；对危险或违法操作不给出可执行步骤。"
                f"{MATH_OUTPUT_INSTRUCTION}"
            )
        context_parts = [f"用户角色：{request.user_role.value}"]
        if request.course_id not in {"", "AUTO", "UNKNOWN"}:
            context_parts.append(f"当前课程提示：{request.course_id}")
        previous = str(
            request.canonical_input.get("previous_answer_summary")
            or request.options.get("previous_answer_summary", "")
        ).strip()
        if previous:
            context_parts.append(f"上一轮摘要：{previous[:3000]}")
        conversation = str(request.options.get("conversation_summary", "")).strip()
        if conversation and conversation != previous:
            context_parts.append(f"对话上下文：{conversation[:6000]}")
        method_reference = str(direct_fallback.get("method_reference", "")).strip()
        if method_reference:
            context_parts.append(
                "课程方法参考（不得当作题目已知条件或直接引用来源）："
                f"\n{method_reference[:6000]}"
            )
        visual_context = str(direct_fallback.get("visual_context", "")).strip()
        if visual_context:
            context_parts.append(
                "上游视觉读取结果（这是从用户原图读取的题目事实，"
                "不是方法参考）："
                f"\n{visual_context[:20_000]}"
            )
        return [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": "\n".join([*context_parts, f"问题：{question}"]),
            },
        ]

    @staticmethod
    def _direct_fallback_context(request: AgentRequest) -> dict[str, object]:
        value = request.options.get("_direct_model_fallback")
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _max_tokens(request: AgentRequest) -> int:
        return {
            "brief": 2048,
            "standard": 4096,
            "deep": 6144,
        }.get(str(request.options.get("response_depth", "standard")), 4096)

    @staticmethod
    def _usage(responses: list[ModelResponse]) -> tuple[int | None, int | None]:
        prompt_values = [
            item.usage.prompt_tokens
            for item in responses
            if item.usage is not None and item.usage.prompt_tokens is not None
        ]
        completion_values = [
            item.usage.completion_tokens
            for item in responses
            if item.usage is not None and item.usage.completion_tokens is not None
        ]
        return (
            sum(prompt_values) if prompt_values else None,
            sum(completion_values) if completion_values else None,
        )

    def _unavailable_result(
        self, request: AgentRequest, question: str, error_code: str
    ) -> AgentResult:
        answer = (
            "这个问题已经进入通用问题模块，但当前配置的通用回答模型暂时不可用。"
            "请稍后重试；如果这是课程问题，也可以补充课程名称、章节或已有材料，"
            "系统会改用可核验的课程检索链路。"
        )
        content = {
            "status": "partial",
            "mode": "general_model_unavailable",
            "answer_text": answer,
            "question": question,
            "model_execution": {
                "status": "failed",
                "output_status": "partial",
                "error_type": error_code,
            },
            "source_policy": "no_course_evidence_claimed",
        }
        return AgentResult(
            agent_id=self.agent_id,
            provider="local_agent",
            answer=answer,
            structured_result=content,
            warnings=["通用回答模型暂不可用，未调用星辰工作流"],
            fallback_used=True,
            fallback_reason="general_model_unavailable",
            rag_status="disabled",
            evidence_status="not_requested",
            cloud_status="not_required",
        )
