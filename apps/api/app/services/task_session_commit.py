from __future__ import annotations

import logging
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentRequest, AgentResult
from app.contracts.conversation import (
    ConversationContextBundle,
    MessageRole,
    MessageStatus,
)
from app.contracts.learning import StudentAttempt, TeachingMode
from app.core.config import Settings
from app.core.errors import AppError
from app.models import TaskModel
from app.repositories import ConversationRepository, SessionRepository
from app.services.conversation_message_service import ConversationMessageService
from app.services.learning_outcome import LearningOutcomeService
from app.services.memory_service import MemoryService
from app.services.session_context import SessionContextService
from app.services.session_working_state import SessionWorkingStateService
from app.services.student_attempts import StudentAttemptService

logger = logging.getLogger(__name__)


class TaskSessionCommitService:
    """Commit session-facing effects of a completed task exactly once.

    Conversation messages already have a database uniqueness boundary on
    ``(source_task_id, role)``. We use the assistant message as the durable
    completion marker: if it exists, the rest of this terminal side-effect
    group was committed in the same transaction and must not be replayed.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        learning_outcome: LearningOutcomeService | None,
        student_attempts: StudentAttemptService,
        compaction_enabled: bool,
    ) -> None:
        self.settings = settings
        self.learning_outcome = learning_outcome
        self.student_attempts = student_attempts
        self.compaction_enabled = compaction_enabled

    async def commit(
        self,
        db: AsyncSession,
        *,
        task: TaskModel,
        request: AgentRequest,
        result: AgentResult,
        conversation_bundle: ConversationContextBundle | None,
    ) -> dict[str, object]:
        existing = await ConversationRepository(db).get_for_task_role(
            task.id, MessageRole.ASSISTANT.value
        )
        if existing is not None:
            task.assistant_message_id = existing.id
            payload = dict(task.result_content or {})
            usage = payload.get("context_usage")
            return dict(usage) if isinstance(usage, dict) else {}

        session = await SessionRepository(db).get_for_user(
            task.session_id, task.user_id, for_update=True
        )
        if session is None:
            return {}

        SessionContextService(self.settings).update(session, request, result)
        await SessionWorkingStateService(db).update_from_result(request, result)
        await self._record_initial_attempt(
            db,
            task=task,
            request=request,
            result=result,
        )
        assistant_message = await ConversationMessageService(
            db
        ).append_assistant_for_task(task, result, session=session)
        task.assistant_message_id = assistant_message.id

        memory_started = perf_counter()
        memory_writes = 0
        memory_action = "none"
        try:
            memory_writes, memory_action = await MemoryService(
                db
            ).process_explicit_intent(
                user_id=task.user_id,
                session_id=task.session_id,
                message_id=task.user_message_id or "",
                text=ConversationMessageService.question_text(request),
                course_id=task.course_id,
                memory_enabled=session.memory_enabled,
                auto_memory_enabled=session.auto_memory_enabled,
            )
            if memory_action in {"remembered", "forgotten"}:
                confirmation = (
                    "宸叉寜浣犵殑瑕佹眰淇濆瓨杩欓」鍋忓ソ銆?"
                    if memory_action == "remembered"
                    else (
                        f"宸插繕璁?{memory_writes} 椤圭浉鍏宠蹇嗐€?"
                        if memory_writes
                        else "娌℃湁鎵惧埌闇€瑕佸繕璁扮殑鍖归厤璁板繂銆?"
                    )
                )
                await ConversationMessageService(db).append(
                    session=session,
                    user_id=task.user_id,
                    role=MessageRole.SYSTEM_EVENT,
                    status=MessageStatus.COMPLETED,
                    content_text=confirmation,
                    source_task_id=task.id,
                    reply_to_message_id=task.user_message_id,
                    metadata={
                        "course_id": task.course_id,
                        "memory_action": memory_action,
                    },
                )
        except AppError:
            logger.info(
                "memory_write_rejected task_id=%s reason=policy",
                task.id,
            )
        memory_latency_ms = (perf_counter() - memory_started) * 1000

        compaction_count = 0
        compaction_latency_ms = 0.0
        context_usage: dict[str, object] = {}
        if conversation_bundle is not None:
            result.metrics = result.metrics.model_copy(
                update={
                    "message_count": session.message_count,
                    "recent_message_count": len(conversation_bundle.recent_messages),
                    "older_message_count": len(
                        conversation_bundle.relevant_earlier_messages
                    ),
                    "session_summary_used": bool(conversation_bundle.session_summary),
                    "summary_version": conversation_bundle.summary_version,
                    "context_estimated_tokens": conversation_bundle.token_estimate,
                    "context_budget_tokens": conversation_bundle.budget,
                    "context_budget_ratio": conversation_bundle.token_estimate
                    / max(1, conversation_bundle.budget),
                    "context_trimmed": conversation_bundle.context_trimmed,
                    "compaction_count": compaction_count,
                    "memory_enabled": session.memory_enabled,
                    "memory_retrieval_count": len(
                        conversation_bundle.active_memories
                    ),
                    "memory_write_count": memory_writes,
                    "context_cache_hit": conversation_bundle.cache_status == "hit",
                    "context_cache_backend": conversation_bundle.cache_backend,
                    "context_build_latency_ms": conversation_bundle.build_latency_ms,
                    "compaction_latency_ms": compaction_latency_ms,
                    "memory_latency_ms": memory_latency_ms,
                }
            )
            context_usage = {
                "memory_enabled": session.memory_enabled,
                "auto_memory_enabled": session.auto_memory_enabled,
                "active_memory_count": len(conversation_bundle.active_memories),
                "active_memory_ids": list(conversation_bundle.source_memory_ids),
                "memory_write_count": memory_writes,
                "memory_action": memory_action,
                "recent_message_count": len(conversation_bundle.recent_messages),
                "older_message_count": len(
                    conversation_bundle.relevant_earlier_messages
                ),
                "summary_used": bool(conversation_bundle.session_summary),
                "summary_version": conversation_bundle.summary_version,
                "estimated_tokens": conversation_bundle.token_estimate,
                "budget_tokens": conversation_bundle.budget,
                "budget_ratio": conversation_bundle.token_estimate
                / max(1, conversation_bundle.budget),
                "trimmed": conversation_bundle.context_trimmed,
                "compaction_count": compaction_count,
                "summary_refresh_status": (
                    "queued"
                    if self.compaction_enabled and session.memory_enabled
                    else "disabled"
                ),
                "cache_status": conversation_bundle.cache_status,
                "build_latency_ms": conversation_bundle.build_latency_ms,
            }
        return context_usage

    async def _record_initial_attempt(
        self,
        db: AsyncSession,
        *,
        task: TaskModel,
        request: AgentRequest,
        result: AgentResult,
    ) -> None:
        """Persist explicit student work without copying it into session state."""
        raw_attempt = request.options.get("student_attempt")
        if self.learning_outcome is None or not isinstance(raw_attempt, dict):
            return
        attempt = StudentAttempt.model_validate(raw_attempt)
        structured = result.structured_result
        raw_report = structured.get("verification_report_v1")
        teaching_loop = structured.get("teaching_loop")
        if not isinstance(raw_report, dict) and isinstance(teaching_loop, dict):
            raw_report = teaching_loop.get("verification")
        verification_report = dict(raw_report) if isinstance(raw_report, dict) else {}
        model = await self.student_attempts.create(
            db,
            task=task,
            user_id=task.user_id,
            idempotency_key=f"{task.id}:initial-attempt",
            attempt=attempt,
            teaching_mode=TeachingMode(
                str(request.options.get("teaching_mode", TeachingMode.DIRECT_ANSWER))
            ),
            hint_level_used=None,
            full_solution_seen=False,
            verification_report=verification_report,
        )
        packet = structured.get("solution_packet")
        skill_ids = (
            [str(item) for item in packet.get("skill_ids", [])]
            if isinstance(packet, dict)
            else []
        )
        outcome = await self.learning_outcome.process_attempt(
            db,
            task=task,
            attempt=model,
            skill_ids=skill_ids,
        )
        due_retests = await self.learning_outcome.retests.list(
            db, user_id=task.user_id, status="due", offset=0, limit=100
        )
        result.metrics = result.metrics.model_copy(
            update={
                "attempt_sequence": int(model.attempt_sequence or 0),
                "attempt_revision_created": False,
                "due_retest_count": len(due_retests),
                **outcome.metrics,
            }
        )
        result.structured_result["learning_outcome"] = {
            "attempt_id": model.id,
            "attempt_sequence": model.attempt_sequence,
            "mastery_evidence_types": [
                item.evidence_type.value for item in outcome.evidence
            ],
            "retest_plan_ids": [item.retest_plan_id for item in outcome.retest_plans],
        }
        await SessionWorkingStateService(db).update_phase3(
            task,
            current_attempt_id=model.id,
            previous_attempt_id=None,
            attempt_sequence=int(model.attempt_sequence or 0),
            feedback_uptake_status=None,
            mastery_evidence_type=(
                outcome.evidence[0].evidence_type.value if outcome.evidence else None
            ),
            pending_retest_plan_ids=[
                item.retest_plan_id for item in outcome.retest_plans
            ],
        )
