from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.api.v1.tasks import _require_runtime_approval
from app.services.auth_service import Principal
from fastapi import HTTPException


def _principal(role: str) -> Principal:
    return Principal(
        authenticated=True,
        account_id=f"{role}-account",
        user_id=f"{role}-user",
        role=role,
    )


@pytest.mark.parametrize(
    "agent_id",
    [
        "RESEARCH_01_ACADEMIC_SEARCH_V1",
        "RESEARCH_02_ACADEMIC_WRITING_V1",
    ],
)
def test_researcher_can_approve_research_runtime(agent_id: str) -> None:
    actor = _require_runtime_approval(
        SimpleNamespace(),
        _principal("researcher"),
        SimpleNamespace(agent_id=agent_id),
    )

    assert actor == ("researcher-user", "researcher")


def test_researcher_cannot_approve_teaching_runtime() -> None:
    with pytest.raises(HTTPException, match="not permitted"):
        _require_runtime_approval(
            SimpleNamespace(),
            _principal("researcher"),
            SimpleNamespace(agent_id="TEACH_01_LESSON_PREP_V1"),
        )


def test_student_cannot_approve_research_runtime() -> None:
    with pytest.raises(HTTPException, match="not permitted"):
        _require_runtime_approval(
            SimpleNamespace(),
            _principal("student"),
            SimpleNamespace(agent_id="RESEARCH_02_ACADEMIC_WRITING_V1"),
        )
