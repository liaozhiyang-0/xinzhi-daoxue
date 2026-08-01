from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLogModel


def record_audit(
    db: AsyncSession,
    request: Request | None,
    *,
    action: str,
    actor_account_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLogModel:
    """Add a safe, structured audit event to the current transaction."""

    model = AuditLogModel(
        actor_account_id=actor_account_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
        ip_address=request.client.host if request and request.client else None,
        user_agent=(
            (request.headers.get("user-agent") or "")[:512]
            if request
            else None
        ),
    )
    db.add(model)
    return model
