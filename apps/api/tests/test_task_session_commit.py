from __future__ import annotations

import asyncio

from app.contracts import AgentRequest, AgentResult, Intent
from app.models import ConversationMessageModel, SessionModel, SessionWorkingStateModel
from app.repositories import TaskRepository
from sqlalchemy import func, select


def test_terminal_session_effects_are_idempotent_after_assistant_message(
    api, app
) -> None:
    session = api.create_session()
    task = api.wait_for_task(api.create_task(session["id"])["id"])

    async def replay() -> dict[str, int]:
        async with app.state.session_factory() as db:
            model = await TaskRepository(db).get(task["id"], for_update=True)
            assert model is not None
            session_model = await db.get(SessionModel, session["id"])
            working_state = await db.get(SessionWorkingStateModel, session["id"])
            assert session_model is not None

            before_message_count = int(session_model.message_count)
            before_session_revision = int(session_model.session_revision)
            before_working_version = int(working_state.version) if working_state else 0
            before_messages = int(
                await db.scalar(
                    select(func.count(ConversationMessageModel.id)).where(
                        ConversationMessageModel.source_task_id == task["id"]
                    )
                )
            )

            stored_result = dict(model.result_content or {})
            stored_result.pop("context_usage", None)
            request_data = dict(model.input_content or {})
            request = AgentRequest(
                task_id=model.id,
                session_id=model.session_id,
                user_id=model.user_id,
                course_id=model.course_id,
                intent=Intent(model.intent),
                canonical_input=dict(request_data.get("canonical_input", {})),
                options=dict(request_data.get("options", {})),
            )
            result = AgentResult.model_validate(stored_result)
            usage = await app.state.task_runner.session_commit.commit(
                db,
                task=model,
                request=request,
                result=result,
                conversation_bundle=None,
            )
            await db.commit()

            after_session = await db.get(SessionModel, session["id"])
            after_working = await db.get(SessionWorkingStateModel, session["id"])
            after_messages = int(
                await db.scalar(
                    select(func.count(ConversationMessageModel.id)).where(
                        ConversationMessageModel.source_task_id == task["id"]
                    )
                )
            )
            assert after_session is not None
            del usage
            return {
                "before_message_count": before_message_count,
                "after_message_count": int(after_session.message_count),
                "before_session_revision": before_session_revision,
                "after_session_revision": int(after_session.session_revision),
                "before_working_version": before_working_version,
                "after_working_version": int(after_working.version)
                if after_working
                else 0,
                "before_messages": before_messages,
                "after_messages": after_messages,
            }

    details = asyncio.run(replay())
    assert details["after_message_count"] == details["before_message_count"]
    assert details["after_session_revision"] == details["before_session_revision"]
    assert details["after_working_version"] == details["before_working_version"]
    assert details["after_messages"] == details["before_messages"]
