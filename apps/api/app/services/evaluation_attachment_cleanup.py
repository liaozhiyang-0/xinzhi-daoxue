from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import FileModel
from app.services.storage import StorageService

EVALUATION_ATTACHMENT_PURPOSE = "evaluation_attachment"


async def cleanup_evaluation_attachments(
    db: AsyncSession,
    settings: Settings,
    *,
    file_ids: Iterable[str] = (),
    task_id: str | None = None,
) -> int:
    """Remove only controlled evaluation attachments from storage and the DB.

    Callers own the transaction and must commit after this function returns.
    Both selectors are intentionally narrow: a caller can provide exact file
    IDs for pre-task upload failures or a task ID after a terminal transition.
    """

    models: dict[str, FileModel] = {}
    for file_id in file_ids:
        normalized = str(file_id).strip()
        if not normalized:
            continue
        model = await db.get(FileModel, normalized)
        if model is not None:
            models[model.id] = model
    if task_id:
        result = await db.scalars(
            select(FileModel).where(
                FileModel.task_id == task_id,
                FileModel.purpose == EVALUATION_ATTACHMENT_PURPOSE,
            )
        )
        for model in result:
            models[model.id] = model

    storage = StorageService(settings)
    removed = 0
    for model in models.values():
        if model.purpose != EVALUATION_ATTACHMENT_PURPOSE:
            continue
        await storage.delete(model.storage_key)
        await db.delete(model)
        removed += 1
    return removed
