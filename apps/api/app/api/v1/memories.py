from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.memory import (
    ForgetRequest,
    MemoryCreate,
    MemoryMutationResult,
    MemoryRead,
    MemoryUpdate,
)
from app.dependencies import effective_user_id, get_current_principal, get_db
from app.repositories import MemoryRepository
from app.services.auth_service import Principal
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("", response_model=list[MemoryRead])
async def list_memories(
    user_id: str,
    principal: Principal = Depends(get_current_principal),
    memory_type: str | None = None,
    course_id: str | None = None,
    include_deleted: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[MemoryRead]:
    user_id = effective_user_id(principal, user_id)
    statuses = (
        ("active", "deleted", "superseded", "candidate")
        if include_deleted
        else ("active",)
    )
    rows = await MemoryRepository(db).list_for_user(
        user_id,
        memory_type=memory_type,
        course_id=course_id,
        statuses=statuses,
        offset=offset,
        limit=limit,
    )
    return [MemoryRead.model_validate(item) for item in rows]


@router.post("", response_model=MemoryRead, status_code=201)
async def create_memory(
    data: MemoryCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MemoryRead:
    data = data.model_copy(
        update={"user_id": effective_user_id(principal, data.user_id)}
    )
    model = await MemoryService(db).create(data)
    await db.commit()
    await db.refresh(model)
    return MemoryRead.model_validate(model)


@router.patch("/{memory_id}", response_model=MemoryRead)
async def update_memory(
    memory_id: str,
    data: MemoryUpdate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MemoryRead:
    data = data.model_copy(
        update={"user_id": effective_user_id(principal, data.user_id)}
    )
    model = await MemoryService(db).update(memory_id, data)
    await db.commit()
    await db.refresh(model)
    return MemoryRead.model_validate(model)


@router.delete("/{memory_id}", response_model=MemoryMutationResult)
async def delete_memory(
    memory_id: str,
    user_id: str,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MemoryMutationResult:
    user_id = effective_user_id(principal, user_id)
    await MemoryService(db).soft_delete(memory_id, user_id)
    await db.commit()
    return MemoryMutationResult(affected=1, message="记忆已删除")


@router.post("/{memory_id}/restore", response_model=MemoryRead)
async def restore_memory(
    memory_id: str,
    user_id: str,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MemoryRead:
    user_id = effective_user_id(principal, user_id)
    model = await MemoryService(db).restore(memory_id, user_id)
    await db.commit()
    await db.refresh(model)
    return MemoryRead.model_validate(model)


@router.post("/forget", response_model=MemoryMutationResult)
async def forget_memories(
    data: ForgetRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> MemoryMutationResult:
    data = data.model_copy(
        update={"user_id": effective_user_id(principal, data.user_id)}
    )
    affected = await MemoryService(db).forget(
        data.user_id, data.query, all_memories=data.all_memories
    )
    await db.commit()
    return MemoryMutationResult(affected=affected, message="已按请求忘记相关记忆")
