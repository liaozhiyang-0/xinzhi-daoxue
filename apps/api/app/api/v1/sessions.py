from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.api import SessionCreate, SessionRead
from app.dependencies import get_db
from app.services.session_service import SessionService

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
