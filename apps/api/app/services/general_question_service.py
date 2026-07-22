from __future__ import annotations

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

        answer = first.content.strip()
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
            else:
                responses.append(continuation)
                answer = "\n\n".join(
                    item for item in (answer, continuation.content.strip()) if item
                )
                if (
                    continuation.finish_reason or ""
                ).casefold() in self._TRUNCATED_REASONS:
                    warnings.append("通用回答已自动续写一次，仍可能不完整")
                else:
                    output_status = "completed"

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
            "mode": "general_model_answer",
            "answer_text": answer,
            "question": question,
            "model_execution": model_execution,
            "source_policy": "no_course_evidence_claimed",
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
        system = (
            "你是芯智导学的通用问题回答助手。专用课程或业务工作流无法确定时，"
            "直接回答用户的普通文本问题，不要求用户重新选择Agent。回答应准确、"
            "结构清楚并与问题复杂度匹配；不知道或缺少关键条件时明确说明。"
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
        return [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": "\n".join([*context_parts, f"问题：{question}"]),
            },
        ]

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
