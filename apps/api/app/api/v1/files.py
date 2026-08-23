from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.api import FileChunkRead, FileRead
from app.core.config import Settings
from app.core.errors import NotFoundError
from app.dependencies import (
    effective_user_id,
    get_current_principal,
    get_db,
    get_settings_from_app,
)
from app.models import DocumentChunkModel, FileIngestionStatus, FileModel
from app.repositories import FileRepository, TaskRepository
from app.services.auth_service import Principal
from app.services.document_ingestion import DocumentIngestionService
from app.services.storage import StorageService

router = APIRouter(prefix="/files", tags=["files"])


def _material_field(value: str | None, name: str, maximum: int) -> str | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if len(cleaned) > maximum or any(character not in allowed for character in cleaned):
        raise HTTPException(status_code=422, detail=f"{name}格式无效")
    return cleaned


@router.post("", response_model=FileRead, status_code=status.HTTP_201_CREATED)
async def upload_file(
    upload: UploadFile = File(...),
    task_id: str | None = Form(default=None),
    purpose: str = Form(default="generic"),
    course_id: str | None = Form(default=None),
    material_key: str | None = Form(default=None),
    material_version: str | None = Form(default=None),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_from_app),
) -> FileRead:
    normalized_course_id = _material_field(course_id, "course_id", 32)
    normalized_material_key = _material_field(material_key, "material_key", 128)
    normalized_material_version = _material_field(
        material_version, "material_version", 64
    )
    if purpose == "course_material":
        if settings.auth_required and (
            not principal.authenticated or principal.role not in {"teacher", "admin"}
        ):
            raise HTTPException(status_code=403, detail="需要教师或管理员权限")
        if not all(
            (
                normalized_course_id,
                normalized_material_key,
                normalized_material_version,
            )
        ):
            raise HTTPException(
                status_code=422,
                detail="course_material必须提供course_id、material_key和material_version",
            )
    elif any(
        (normalized_course_id, normalized_material_key, normalized_material_version)
    ):
        raise HTTPException(
            status_code=422,
            detail="只有course_material允许提供课程资料版本字段",
        )
    task = await TaskRepository(db).get(task_id) if task_id else None
    if task_id and task is None:
        raise NotFoundError("关联任务不存在", details={"task_id": task_id})
    if (
        principal.has_identity
        and task is not None
        and task.user_id != principal.user_id
    ):
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
        content_type = service.infer_binary_image_content_type(
            upload.filename or "upload", content_type, data
        )
        safe_name = service.validate(
            upload.filename or "upload", len(data), content_type
        )
    storage_key = await service.save(safe_name, content_type, data)
    model = FileModel(
        id=f"file_{uuid4().hex}",
        owner_user_id=(
            principal.user_id
            if principal.has_identity
            else task.user_id if task is not None else None
        ),
        task_id=task_id,
        filename=safe_name,
        content_type=content_type,
        size_bytes=len(data),
        storage_key=storage_key,
        checksum_sha256=sha256(data).hexdigest(),
        purpose=purpose,
        course_id=normalized_course_id,
        material_key=normalized_material_key,
        material_version=normalized_material_version,
        detected_content_type=content_type,
        ingestion_status=(
            FileIngestionStatus.PENDING
            if Path(safe_name).suffix.lower()
            in {".txt", ".md", ".csv", ".json", ".pdf", ".doc", ".docx"}
            else FileIngestionStatus.READY
        ),
        expires_at=(
            datetime.now(UTC) + timedelta(seconds=settings.student_upload_ttl_seconds)
            if purpose == "student_solver_image" and task_id is None
            else None
        ),
    )
    try:
        await repository.add(model)
        if Path(safe_name).suffix.lower() in {
            ".txt",
            ".md",
            ".csv",
            ".json",
            ".pdf",
            ".doc",
            ".docx",
        }:
            await DocumentIngestionService(settings).ingest(model, data, db)
            model.knowledge_index_status = (
                "not_indexed"
                if model.ingestion_status
                in {FileIngestionStatus.READY, FileIngestionStatus.PARTIAL}
                else "failed"
            )
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
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> FileRead:
    model = await FileRepository(db).get(file_id)
    if model is None:
        raise NotFoundError("文件不存在", details={"file_id": file_id})
    if principal.has_identity and model.owner_user_id != principal.user_id:
        raise NotFoundError("文件不存在", details={"file_id": file_id})
    return FileRead.model_validate(model)


@router.get("/{file_id}/chunks", response_model=list[FileChunkRead])
async def get_file_chunks(
    file_id: str,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[FileChunkRead]:
    model = await FileRepository(db).get(file_id)
    if model is None or (
        principal.has_identity and model.owner_user_id != principal.user_id
    ):
        raise NotFoundError("文件不存在", details={"file_id": file_id})
    chunks = list(
        (
            await db.scalars(
                select(DocumentChunkModel)
                .where(DocumentChunkModel.file_id == file_id)
                .order_by(DocumentChunkModel.ordinal)
            )
        ).all()
    )
    return [FileChunkRead.model_validate(item) for item in chunks]


@router.get("/{file_id}/content")
async def get_file_content(
    file_id: str,
    user_id: str = Query(min_length=1, max_length=128),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_from_app),
) -> Response:
    """Return an attached student image only to the task owner."""

    model = await FileRepository(db).get(file_id)
    if model is None or model.task_id is None:
        raise NotFoundError("图片附件不存在", details={"file_id": file_id})
    user_id = effective_user_id(principal, user_id)
    task = await TaskRepository(db).get(model.task_id)
    if (
        task is None
        or (principal.has_identity and model.owner_user_id != principal.user_id)
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
