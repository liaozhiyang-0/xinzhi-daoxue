from __future__ import annotations

import pytest
from app.runtime import RuntimeCapabilitySelection, RuntimeGoal
from app.services.runtime_goal_intake import (
    RuntimeGoalIntakeError,
    RuntimeGoalIntakePolicy,
)


def _goal() -> RuntimeGoal:
    return RuntimeGoal(
        objective="execute a declared goal",
        required_capabilities=["tool.read"],
    )


def _selection(
    *,
    handler_id: str = "tool.read",
    kind: str = "tool",
    side_effecting: bool = False,
    requires_approval: bool = False,
) -> RuntimeCapabilitySelection:
    return RuntimeCapabilitySelection(
        capability=handler_id,
        handler_id=handler_id,
        kind=kind,
        side_effecting=side_effecting,
        requires_approval=requires_approval,
    )


def test_goal_intake_defaults_to_registered_read_only_tools() -> None:
    evidence = RuntimeGoalIntakePolicy({}).validate(
        "GENERAL_QUESTION_V1", _goal(), [_selection()]
    )

    assert evidence.policy_source == "default_read_only_tools"
    assert evidence.handler_ids == ["tool.read"]


def test_goal_intake_rejects_side_effect_without_agent_allowlist() -> None:
    with pytest.raises(
        RuntimeGoalIntakeError,
        match="goal_capability_requires_agent_allowlist:tool.write",
    ):
        RuntimeGoalIntakePolicy({}).validate(
            "GENERAL_QUESTION_V1",
            _goal(),
            [_selection(handler_id="tool.write", side_effecting=True)],
        )


def test_goal_intake_requires_full_handler_id_in_agent_allowlist() -> None:
    policy = RuntimeGoalIntakePolicy.from_config(
        "GENERAL_QUESTION_V1=tool.write"
    )
    evidence = policy.validate(
        "GENERAL_QUESTION_V1",
        _goal(),
        [
            _selection(
                handler_id="tool.write",
                side_effecting=True,
                requires_approval=True,
            )
        ],
    )

    assert evidence.policy_source == "agent_allowlist"
    assert evidence.requires_approval is True


def test_goal_intake_config_rejects_duplicate_agent_policy() -> None:
    with pytest.raises(ValueError, match="duplicate Runtime goal capability"):
        RuntimeGoalIntakePolicy.from_config(
            "GENERAL_QUESTION_V1=tool.read;GENERAL_QUESTION_V1=tool.write"
        )
