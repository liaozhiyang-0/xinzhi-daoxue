from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentRequest, AgentResult, TeachingMode
from app.contracts.conversation import SessionWorkingState, TeachingStateV1
from app.models import SessionWorkingStateModel, TaskModel
from app.models.entities import utc_now
from app.repositories import RuntimeContextRepository
from app.services.conversation_message_service import ConversationMessageService
from app.services.runtime_safety import sanitize_runtime_text


class SessionWorkingStateService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = RuntimeContextRepository(db)

    async def get(self, session_id: str) -> SessionWorkingState:
        model = await self.repository.get_working_state(session_id)
        if model is None:
            return SessionWorkingState()
        payload = dict(model.state_data or {})
        payload.update(version=model.version, updated_at=model.updated_at)
        return SessionWorkingState.model_validate(payload)

    async def update_from_user(
        self, request: AgentRequest, message_id: str
    ) -> SessionWorkingState:
        model = await self.repository.get_working_state(request.session_id)
        current = await self.get(request.session_id)
        question = sanitize_runtime_text(
            ConversationMessageService.question_text(request), max_chars=1000
        )
        corrections = list(current.user_corrections)
        if any(marker in question for marker in ("纠正", "不是", "改为", "应为")):
            corrections.append(question[:300])
            corrections = corrections[-8:]
        mode = TeachingMode(
            str(request.options.get("teaching_mode", TeachingMode.DIRECT_ANSWER))
        )
        teaching_state = TeachingStateV1(
            teaching_mode=mode,
            source_task_id=request.task_id,
            student_attempt_present=request.options.get("student_attempt") is not None,
            updated_at=utc_now(),
        )
        state = current.model_copy(
            update={
                "current_goal": question[:300],
                "current_course": request.course_id.upper(),
                "current_task_family": str(
                    request.options.get("task_family", request.intent.value)
                ),
                "user_corrections": corrections,
                "referenced_message_ids": (
                    list(current.referenced_message_ids) + [message_id]
                )[-20:],
                "teaching_state": teaching_state,
                "updated_at": utc_now(),
                "version": current.version + (1 if model else 0),
            }
        )
        state_data = state.model_dump(mode="json", exclude={"version", "updated_at"})
        if model is None:
            model = SessionWorkingStateModel(
                session_id=request.session_id,
                user_id=request.user_id,
                state_data=state_data,
                version=state.version,
                updated_at=state.updated_at or utc_now(),
            )
            self.db.add(model)
        else:
            model.state_data = state_data
            model.version = state.version
            model.updated_at = state.updated_at or utc_now()
        return state

    async def update_from_result(
        self, request: AgentRequest, result: AgentResult
    ) -> SessionWorkingState:
        model = await self.repository.get_working_state(request.session_id)
        current = await self.get(request.session_id)
        packet = result.structured_result.get("solution_packet", {})
        packet = packet if isinstance(packet, dict) else {}
        teaching_loop = result.structured_result.get("teaching_loop", {})
        teaching_loop = teaching_loop if isinstance(teaching_loop, dict) else {}
        plan = teaching_loop.get("execution_plan", {})
        plan = plan if isinstance(plan, dict) else {}
        hint = teaching_loop.get("hint", {})
        hint = hint if isinstance(hint, dict) else {}
        verification = teaching_loop.get("verification", {})
        verification = verification if isinstance(verification, dict) else {}
        next_check = teaching_loop.get("next_check", {})
        next_check = next_check if isinstance(next_check, dict) else {}
        disclosure = teaching_loop.get("disclosure_policy", {})
        disclosure = disclosure if isinstance(disclosure, dict) else {}
        existing = current.teaching_state or TeachingStateV1()
        teaching_state = existing.model_copy(
            update={
                "teaching_mode": TeachingMode(
                    str(
                        request.options.get("teaching_mode", TeachingMode.DIRECT_ANSWER)
                    )
                ),
                "source_task_id": request.task_id,
                "student_attempt_present": (
                    request.options.get("student_attempt") is not None
                ),
                "current_skill_ids": [
                    str(item) for item in packet.get("skill_ids", [])
                ],
                "current_problem_type": (
                    str(packet["problem_type"]) if packet.get("problem_type") else None
                ),
                "execution_path": (
                    str(plan["path"]) if plan.get("path") else existing.execution_path
                ),
                "current_hint_level": (
                    str(hint["hint_level"])
                    if hint.get("hint_level")
                    else existing.current_hint_level
                ),
                "hint_request_count": int(
                    teaching_loop.get("hint_request_count", existing.hint_request_count)
                ),
                "first_confirmed_error_step": (
                    str(verification["first_confirmed_error_step"])
                    if verification.get("first_confirmed_error_step")
                    else None
                ),
                "pending_check_question": (
                    str(next_check["question_text"])
                    if next_check.get("question_text")
                    else None
                ),
                "pending_check_question_id": (
                    str(next_check["question_id"])
                    if next_check.get("question_id")
                    else None
                ),
                "awaiting_student_response": bool(
                    teaching_loop.get("awaiting_student_response", False)
                ),
                "solution_packet_task_id": (
                    request.task_id if packet else existing.solution_packet_task_id
                ),
                "verification_report_task_id": (
                    request.task_id
                    if verification
                    else existing.verification_report_task_id
                ),
                "full_solution_disclosed": bool(
                    disclosure.get("reveal_final_answer", bool(result.answer.strip()))
                ),
                "updated_at": utc_now(),
            }
        )
        state = current.model_copy(
            update={
                "teaching_state": teaching_state,
                "updated_at": utc_now(),
                "version": current.version + (1 if model else 0),
            }
        )
        state_data = state.model_dump(mode="json", exclude={"version", "updated_at"})
        if model is None:
            model = SessionWorkingStateModel(
                session_id=request.session_id,
                user_id=request.user_id,
                state_data=state_data,
                version=state.version,
                updated_at=state.updated_at or utc_now(),
            )
            self.db.add(model)
        else:
            model.state_data = state_data
            model.version = state.version
            model.updated_at = state.updated_at or utc_now()
        return state

    async def update_from_teaching_interaction(
        self,
        task: TaskModel,
        *,
        teaching_loop: dict[str, object],
    ) -> SessionWorkingState:
        model = await self.repository.get_working_state(task.session_id)
        current = await self.get(task.session_id)
        existing = current.teaching_state or TeachingStateV1()
        hint = teaching_loop.get("hint")
        hint = hint if isinstance(hint, dict) else {}
        verification = teaching_loop.get("verification")
        verification = verification if isinstance(verification, dict) else {}
        next_check = teaching_loop.get("next_check")
        next_check = next_check if isinstance(next_check, dict) else {}
        disclosure = teaching_loop.get("disclosure_policy")
        disclosure = disclosure if isinstance(disclosure, dict) else {}
        plan = teaching_loop.get("execution_plan")
        plan = plan if isinstance(plan, dict) else {}
        state = current.model_copy(
            update={
                "teaching_state": existing.model_copy(
                    update={
                        "source_task_id": task.id,
                        "teaching_mode": (
                            TeachingMode.DIRECT_ANSWER
                            if disclosure.get("reveal_final_answer")
                            else existing.teaching_mode
                        ),
                        "execution_path": str(
                            plan.get("path", existing.execution_path or "")
                        )
                        or None,
                        "current_hint_level": (
                            str(hint["hint_level"])
                            if hint.get("hint_level")
                            else existing.current_hint_level
                        ),
                        "hint_request_count": int(
                            str(
                                teaching_loop.get(
                                    "hint_request_count",
                                    existing.hint_request_count,
                                )
                            )
                        ),
                        "first_confirmed_error_step": (
                            str(verification["first_confirmed_error_step"])
                            if verification.get("first_confirmed_error_step")
                            else None
                        ),
                        "pending_check_question": (
                            str(next_check["question_text"])
                            if next_check.get("question_text")
                            else None
                        ),
                        "pending_check_question_id": (
                            str(next_check["question_id"])
                            if next_check.get("question_id")
                            else None
                        ),
                        "awaiting_student_response": bool(
                            teaching_loop.get("awaiting_student_response", False)
                        ),
                        "solution_packet_task_id": task.id,
                        "verification_report_task_id": (
                            task.id if verification else None
                        ),
                        "full_solution_disclosed": bool(
                            teaching_loop.get(
                                "full_solution_disclosed",
                                disclosure.get("reveal_final_answer", False),
                            )
                        ),
                        "updated_at": utc_now(),
                    }
                ),
                "updated_at": utc_now(),
                "version": current.version + (1 if model else 0),
            }
        )
        state_data = state.model_dump(mode="json", exclude={"version", "updated_at"})
        if model is None:
            model = SessionWorkingStateModel(
                session_id=task.session_id,
                user_id=task.user_id,
                state_data=state_data,
                version=state.version,
                updated_at=state.updated_at or utc_now(),
            )
            self.db.add(model)
        else:
            model.state_data = state_data
            model.version = state.version
            model.updated_at = state.updated_at or utc_now()
        return state

    async def update_phase3(
        self,
        task: TaskModel,
        *,
        current_attempt_id: str,
        previous_attempt_id: str | None,
        attempt_sequence: int,
        feedback_uptake_status: str | None,
        mastery_evidence_type: str | None,
        pending_retest_plan_ids: list[str],
    ) -> SessionWorkingState:
        """Persist only compact IDs/statuses, never Attempt or mastery payloads."""

        model = await self.repository.get_working_state(task.session_id)
        current = await self.get(task.session_id)
        existing = current.teaching_state or TeachingStateV1()
        pending = list(
            dict.fromkeys(
                [
                    *existing.pending_retest_plan_ids,
                    *pending_retest_plan_ids,
                ]
            )
        )[-20:]
        teaching_state = existing.model_copy(
            update={
                "source_task_id": task.id,
                "current_attempt_id": current_attempt_id,
                "previous_attempt_id": previous_attempt_id,
                "attempt_sequence": attempt_sequence,
                "last_feedback_uptake_status": feedback_uptake_status,
                "last_mastery_evidence_type": mastery_evidence_type,
                "pending_retest_plan_ids": pending,
                "updated_at": utc_now(),
            }
        )
        state = current.model_copy(
            update={
                "teaching_state": teaching_state,
                "updated_at": utc_now(),
                "version": current.version + (1 if model else 0),
            }
        )
        state_data = state.model_dump(mode="json", exclude={"version", "updated_at"})
        if model is None:
            model = SessionWorkingStateModel(
                session_id=task.session_id,
                user_id=task.user_id,
                state_data=state_data,
                version=state.version,
                updated_at=state.updated_at or utc_now(),
            )
            self.db.add(model)
        else:
            if model.user_id != task.user_id:
                return current
            model.state_data = state_data
            model.version = state.version
            model.updated_at = state.updated_at or utc_now()
        await self.db.flush()
        return state
