from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts import AgentRequest
from app.contracts.conversation import SessionWorkingState
from app.models import SessionWorkingStateModel
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
                "updated_at": utc_now(),
                "version": current.version + (1 if model else 0),
            }
        )
        state_data = state.model_dump(
            mode="json", exclude={"version", "updated_at"}
        )
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
