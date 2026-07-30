from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.api import FileRead
from app.core.config import Settings
from app.core.errors import NotFoundError
from app.dependencies import get_db, get_settings_from_app
from app.models import FileModel
from app.repositories import FileRepository, TaskRepository
from app.services.storage import StorageService

router = APIRouter(prefix="/files", tags=["files"])


@router.post("", response_model=FileRead, status_code=status.HTTP_201_CREATED)
async def upload_file(
    upload: UploadFile = File(...),
    task_id: str | None = Form(default=None),
    purpose: str = Form(default="generic"),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_from_app),
) -> FileRead:
    if task_id and await TaskRepository(db).get(task_id) is None:
        raise NotFoundError("关联任务不存在", details={"task_id": task_id})
    limit = settings.max_upload_size_mb * 1024 * 1024
    data = await upload.read(limit + 1)
    service = StorageService(settings)
    content_type = upload.content_type or "application/octet-stream"
    repository = FileRepository(db)
    for expired in await repository.list_expired(datetime.now(UTC)):
        await service.delete(expired.storage_key)
        await db.delete(expired)
    if purpose == "student_solver_image":
        safe_name, content_type, data = service.normalize_student_image(
            upload.filename or "upload", content_type, data
        )
    else:
        safe_name = service.validate(
            upload.filename or "upload", len(data), content_type
        )
    storage_key = await service.save(safe_name, content_type, data)
    model = FileModel(
        id=f"file_{uuid4().hex}",
        task_id=task_id,
        filename=safe_name,
        content_type=content_type,
        size_bytes=len(data),
        storage_key=storage_key,
        checksum_sha256=sha256(data).hexdigest(),
        purpose=purpose,
        expires_at=(
            datetime.now(UTC) + timedelta(seconds=settings.student_upload_ttl_seconds)
            if purpose == "student_solver_image" and task_id is None
            else None
        ),
    )
    try:
        await repository.add(model)
        await db.commit()
        await db.refresh(model)
    except Exception:
        await db.rollback()
        await service.delete(storage_key)
        raise
    return FileRead.model_validate(model)


@router.get("/{file_id}", response_model=FileRead)
async def get_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileRead:
    model = await FileRepository(db).get(file_id)
    if model is None:
        raise NotFoundError("文件不存在", details={"file_id": file_id})
    return FileRead.model_validate(model)


@router.get("/{file_id}/content")
async def get_file_content(
    file_id: str,
    user_id: str = Query(min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_from_app),
) -> Response:
    """Return an attached student image only to the task owner."""

    model = await FileRepository(db).get(file_id)
    if model is None or model.task_id is None:
        raise NotFoundError("图片附件不存在", details={"file_id": file_id})
    task = await TaskRepository(db).get(model.task_id)
    if (
        task is None
        or task.user_id != user_id
        or not model.content_type.startswith("image/")
    ):
        raise NotFoundError("图片附件不存在", details={"file_id": file_id})
    data = await StorageService(settings).read(model.storage_key)
    return Response(
        content=data,
        media_type=model.content_type,
        headers={
            "Cache-Control": "private, max-age=300",
            "Content-Disposition": (
                f"inline; filename*=UTF-8''{quote(model.filename, safe='')}"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )
