from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.api import SessionCreate, SessionRead, SessionTaskHistoryItem
from app.dependencies import get_db
from app.models import TaskModel
from app.services.session_service import SessionService
from app.services.task_query_service import TaskQueryService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreate, db: AsyncSession = Depends(get_db)
) -> SessionRead:
    model = await SessionService(db).create(data)
    return SessionRead.model_validate(model)


@router.get("/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: str, db: AsyncSession = Depends(get_db)
) -> SessionRead:
    model = await SessionService(db).get(session_id)
    return SessionRead.model_validate(model)


def _history_item(task: TaskModel) -> SessionTaskHistoryItem:
    canonical = task.input_content.get("canonical_input", {})
    if not isinstance(canonical, dict):
        canonical = {}
    question = next(
        (
            str(canonical[key]).strip()
            for key in ("text", "question", "problem", "query", "prompt")
            if str(canonical.get(key, "")).strip()
        ),
        "已提交材料任务",
    )
    result = task.result_content if isinstance(task.result_content, dict) else {}
    return SessionTaskHistoryItem(
        id=task.id,
        course_id=task.course_id,
        intent=task.intent,
        status=task.status,
        provider=task.provider,
        agent_id=task.agent_id,
        question=question,
        answer=str(result.get("answer", "")),
        error_message=task.error_message,
        fallback_used=bool(result.get("fallback_used", False)),
        fallback_reason=str(result.get("fallback_reason", "")),
        created_at=task.created_at,
        completed_at=task.completed_at,
    )


@router.get("/{session_id}/tasks", response_model=list[SessionTaskHistoryItem])
async def list_session_tasks(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[SessionTaskHistoryItem]:
    await SessionService(db).get(session_id)
    tasks = await TaskQueryService(db).list_for_session(session_id, limit=limit)
    return [_history_item(task) for task in tasks]
