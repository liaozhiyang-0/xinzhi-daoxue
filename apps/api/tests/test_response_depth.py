from __future__ import annotations

import pytest
from app.contracts import AgentRequest, ResponseDepth
from app.services.response_depth import policy_for
from pydantic import ValidationError


def test_agent_request_normalizes_legacy_options_to_typed_depth() -> None:
    request = AgentRequest(
        session_id="session-depth",
        user_id="user-depth",
        options={"response_depth": "deep"},
    )

    assert request.response_depth is ResponseDepth.DEEP
    assert request.options["response_depth"] == "deep"


def test_agent_request_rejects_unknown_depth() -> None:
    with pytest.raises(ValidationError):
        AgentRequest(
            session_id="session-depth",
            user_id="user-depth",
            options={"response_depth": "extreme"},
        )


@pytest.mark.parametrize(
    ("level", "retrieval_limit", "evidence_limit", "verify"),
    [
        ("brief", 3, 2, False),
        ("standard", 6, 4, True),
        ("deep", 10, 8, True),
    ],
)
def test_knowledge_depth_changes_observable_execution_policy(
    level: str, retrieval_limit: int, evidence_limit: int, verify: bool
) -> None:
    policy = policy_for({"response_depth": level}, "knowledge_qa")

    assert policy.level.value == level
    assert policy.retrieval_limit == retrieval_limit
    assert policy.evidence_limit == evidence_limit
    assert policy.verify is verify
