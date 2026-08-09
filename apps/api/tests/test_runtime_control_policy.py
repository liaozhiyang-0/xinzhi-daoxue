from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from app.services.runtime_control_policy import (
    LEARNING_LOOP_CONTROL_POLICY,
    UNIFIED_RUNTIME_CONTROL_POLICY,
    RuntimeControlPolicy,
    control_policy_for_runtime_kind,
)


def test_unified_runtime_exposes_only_state_valid_controls() -> None:
    policy = UNIFIED_RUNTIME_CONTROL_POLICY

    assert policy.declared_controls == ("pause", "resume", "approve", "input")
    assert policy.available_controls("running") == ("pause",)
    assert policy.available_controls("paused") == ("resume",)
    assert policy.available_controls("waiting_approval") == ("approve",)
    assert policy.available_controls("waiting_input") == ("input",)
    assert policy.available_controls("completed") == ()


def test_learning_loop_waiting_approval_only_projects_approve() -> None:
    policy = LEARNING_LOOP_CONTROL_POLICY

    assert policy.declared_controls == ("approve",)
    assert policy.available_controls("waiting_approval") == ("approve",)
    assert policy.available_controls("running") == ()
    assert policy.available_controls("waiting_input") == ()
    assert policy.available_controls("paused") == ()
    assert not policy.allows("pause", "running")


def test_unknown_runtime_kind_is_fail_closed() -> None:
    policy = control_policy_for_runtime_kind("future_runtime")

    assert policy.runtime_kind == "unknown"
    assert policy.declared_controls == ()
    assert policy.available_controls("waiting_approval") == ()
    assert policy.available_controls("running") == ()


def test_unknown_status_and_invalid_policy_inputs_are_fail_closed() -> None:
    assert control_policy_for_runtime_kind(" ").available_controls("running") == ()
    assert (
        control_policy_for_runtime_kind("runtime").available_controls("unknown")
        == ()
    )

    with pytest.raises(ValueError):
        RuntimeControlPolicy(runtime_kind=" ")


def test_policy_is_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        LEARNING_LOOP_CONTROL_POLICY.supports_pause = True  # type: ignore[misc]
