from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import (
    AgentEventType,
    AnswerDisclosureMode,
    HintDecisionV1,
    NextCheckQuestionV1,
    SolutionPacketV1,
    StudentAttempt,
    TeachingMode,
    VerificationReportV1,
)
from app.contracts.learning import LearningActionRequest
from app.models.entities import ConversationMessageModel, TaskModel
from app.services.answer_disclosure import (
    INTERNAL_TEACHING_KEY,
    AnswerDisclosureService,
)
from app.services.event_service import append_task_event
from app.services.hint_policy import HintPolicyService
from app.services.next_check_question import NextCheckQuestionService
from app.services.session_working_state import SessionWorkingStateService
from app.services.student_verification import StudentVerificationService

PHASE2_ACTIONS = frozenset(
    {
        "request_more_hint",
        "submit_check_response",
        "switch_to_direct_answer",
    }
)


class TeachingInteractionService:
    """Mutates the existing source task for bounded multi-round teaching actions."""

    def __init__(
        self,
        verifier: StudentVerificationService,
        hints: HintPolicyService,
        next_checks: NextCheckQuestionService,
        disclosure: AnswerDisclosureService,
    ) -> None:
        self.verifier = verifier
        self.hints = hints
        self.next_checks = next_checks
        self.disclosure = disclosure

    async def act(
        self,
        session: AsyncSession,
        task: TaskModel,
        request: LearningActionRequest,
    ) -> tuple[str, dict[str, Any]]:
        result_content = deepcopy(task.result_content or {})
        structured = result_content.setdefault("structured_result", {})
        if not isinstance(structured, dict):
            structured = {}
            result_content["structured_result"] = structured
        internal = structured.get(INTERNAL_TEACHING_KEY)
        if not isinstance(internal, dict):
            return "当前任务没有可复用的受保护标准解，请重新提交原题。", {}
        raw_packet = internal.get("full_solution_packet")
        if not isinstance(raw_packet, dict):
            return "当前任务缺少可复用 SolutionPacket。", {}
        packet = SolutionPacketV1.model_validate(raw_packet)
        teaching_loop = dict(structured.get("teaching_loop") or {})
        mode = TeachingMode(
            str(
                (structured.get("teaching") or {}).get(
                    "teaching_mode", TeachingMode.GUIDED_LEARNING
                )
            )
        )
        report = self._report(structured)
        if request.action == "switch_to_direct_answer":
            message = self._restore_full_answer(
                result_content,
                structured,
                internal,
                teaching_loop,
            )
        else:
            if request.action == "submit_check_response":
                if not request.student_answer.strip():
                    return "请先填写你对理解检查的回答。", teaching_loop
                report, _ = self.verifier.verify(
                    StudentAttempt(raw_text=request.student_answer),
                    packet,
                )
                structured["verification_report_v1"] = report.model_dump(
                    mode="json"
                )
                teaching_loop["verification"] = report.model_dump(mode="json")
                mode = TeachingMode.CHECK_MY_WORK
            count = int(teaching_loop.get("hint_request_count", 0))
            if request.action == "request_more_hint":
                count += 1
            hint, _ = self.hints.decide(
                mode=mode,
                packet=packet,
                report=report,
                hint_request_count=count,
            )
            if count > 1:
                hint = hint.model_copy(
                    update={
                        "hint_level": "H2",
                        "hint_text": (
                            "当前版本已达到可用提示上限，可切换为直接解答模式"
                            "查看完整解答。"
                        ),
                        "source": "controlled_template:H2_LIMIT",
                        "next_action": "switch_to_direct_answer",
                    }
                )
            next_check = self.next_checks.generate(
                task_id=task.id,
                packet=packet,
                hint=hint,
            )
            self._update_learning_view(
                result_content,
                structured,
                teaching_loop,
                report,
                hint,
                next_check,
                count,
            )
            message = (
                "已提供下一层提示。"
                if request.action == "request_more_hint"
                else "已检查本轮回答，并更新有限诊断。"
            )
        task.result_content = result_content
        await SessionWorkingStateService(session).update_from_teaching_interaction(
            task,
            teaching_loop=dict(structured.get("teaching_loop") or {}),
        )
        await append_task_event(
            session,
            task.id,
            AgentEventType.AGENT_PROGRESS,
            agent_id=task.agent_id,
            data={
                "stage": "teaching_state_updated",
                "learning_action": request.action,
                "hint_level": str(
                    (
                        (structured.get("teaching_loop") or {}).get("hint")
                        or {}
                    ).get("hint_level", "")
                ),
                "full_solution_disclosed": bool(
                    (structured.get("teaching_loop") or {}).get(
                        "full_solution_disclosed", False
                    )
                ),
            },
        )
        await self._update_assistant_message(session, task, result_content)
        return message, dict(structured.get("teaching_loop") or {})

    def _restore_full_answer(
        self,
        result_content: dict[str, Any],
        structured: dict[str, Any],
        internal: dict[str, Any],
        teaching_loop: dict[str, Any],
    ) -> str:
        full_answer = str(internal.get("full_answer", "")).strip()
        full_packet = internal.get("full_solution_packet")
        full_fields = internal.get("full_structured_fields")
        if isinstance(full_fields, dict):
            structured.update(deepcopy(full_fields))
        if isinstance(full_packet, dict):
            structured["solution_packet"] = deepcopy(full_packet)
        result_content["answer"] = full_answer
        result_content.pop("math_content", None)
        structured["answer_text"] = full_answer
        structured.pop("math_content", None)
        policy = self.disclosure.policy(TeachingMode.DIRECT_ANSWER)
        teaching_loop.update(
            {
                "disclosure_policy": policy.model_dump(mode="json"),
                "awaiting_student_response": False,
                "solution_packet_reused": True,
                "full_solution_disclosed": True,
            }
        )
        structured["teaching_loop"] = teaching_loop
        teaching = dict(structured.get("teaching") or {})
        teaching.update(
            {
                "teaching_mode": TeachingMode.DIRECT_ANSWER.value,
                "mode_status": "available",
            }
        )
        structured["teaching"] = teaching
        metrics = dict(result_content.get("metrics") or {})
        metrics.update(
            {
                "teaching_mode": TeachingMode.DIRECT_ANSWER.value,
                "teaching_execution_path": "direct",
                "solution_packet_reused": True,
                "answer_disclosure_mode": AnswerDisclosureMode.FULL.value,
                "full_solution_disclosed": True,
                "additional_model_calls": 0,
            }
        )
        result_content["metrics"] = metrics
        return "已复用本题标准解并切换为完整解答，没有重新执行 Solver。"

    @staticmethod
    def _update_learning_view(
        result_content: dict[str, Any],
        structured: dict[str, Any],
        teaching_loop: dict[str, Any],
        report: VerificationReportV1 | None,
        hint: HintDecisionV1,
        next_check: NextCheckQuestionV1,
        count: int,
    ) -> None:
        public_next = next_check.model_dump(
            mode="json", exclude={"answer_key_internal"}
        )
        teaching_loop.update(
            {
                "verification": (
                    report.model_dump(mode="json") if report else None
                ),
                "hint": hint.model_dump(mode="json"),
                "next_check": public_next,
                "hint_request_count": count,
                "awaiting_student_response": True,
                "full_solution_disclosed": False,
            }
        )
        structured["teaching_loop"] = teaching_loop
        answer_parts = []
        if report and report.manual_review_required:
            answer_parts.append("当前推导需要人工复核；下面只提供受控学习线索。")
        answer_parts.extend(
            [
                f"### {hint.hint_level} 提示\n\n{hint.hint_text}",
                f"### 下一步理解检查\n\n{next_check.question_text}",
            ]
        )
        answer = "\n\n".join(answer_parts)
        result_content["answer"] = answer
        result_content.pop("math_content", None)
        structured["answer_text"] = answer
        structured.pop("math_content", None)
        metrics = dict(result_content.get("metrics") or {})
        metrics.update(
            {
                "hint_level": hint.hint_level,
                "hint_source": hint.source,
                "hint_request_count": count,
                "next_check_generated": True,
                "additional_model_calls": 0,
            }
        )
        result_content["metrics"] = metrics

    @staticmethod
    def _report(structured: dict[str, Any]) -> VerificationReportV1 | None:
        raw = structured.get("verification_report_v1")
        return (
            VerificationReportV1.model_validate(raw)
            if isinstance(raw, dict)
            else None
        )

    @staticmethod
    async def _update_assistant_message(
        session: AsyncSession,
        task: TaskModel,
        result_content: dict[str, Any],
    ) -> None:
        if not task.assistant_message_id:
            return
        message = await session.get(ConversationMessageModel, task.assistant_message_id)
        if message is None:
            return
        structured = result_content.get("structured_result") or {}
        message.content_text = str(result_content.get("answer", ""))
        content_data = dict(message.content_data or {})
        for key in (
            "teaching",
            "teaching_loop",
            "verification_report_v1",
            "solution_packet",
        ):
            if structured.get(key) is not None:
                content_data[key] = deepcopy(structured[key])
        message.content_data = content_data
