"""Provider-free control policy projections for durable Runtime runs.

The policy is intentionally a declaration of the control surface only.  It
does not locate a run, mutate a checkpoint, or invoke a Provider.  Callers
must still enforce ownership, state-version, and persistence rules in their
control service before performing an action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ControlAction = Literal["pause", "resume", "approve", "input"]

_ALL_CONTROL_ACTIONS: tuple[ControlAction, ...] = (
    "pause",
    "resume",
    "approve",
    "input",
)


@dataclass(frozen=True, slots=True)
class RuntimeControlPolicy:
    """The executable control surface that a Runtime projection may expose.

    ``supports_*`` describes the runtime's actual control boundary.  The
    state-aware method below further limits that boundary to actions that are
    meaningful for the current checkpoint.  The object is immutable so a
    readiness or status projection cannot accidentally widen it at runtime.
    """

    runtime_kind: str
    supports_pause: bool = False
    supports_resume: bool = False
    supports_approval: bool = False
    supports_input: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_kind, str) or not self.runtime_kind.strip():
            raise ValueError("runtime_kind must be a non-empty string")
        object.__setattr__(self, "runtime_kind", self.runtime_kind.strip())

    @property
    def declared_controls(self) -> tuple[ControlAction, ...]:
        """Return only controls declared by this policy, in stable order."""

        return tuple(
            action
            for action, supported in zip(
                _ALL_CONTROL_ACTIONS,
                (
                    self.supports_pause,
                    self.supports_resume,
                    self.supports_approval,
                    self.supports_input,
                ),
                strict=True,
            )
            if supported
        )

    def available_controls(self, status: str) -> tuple[ControlAction, ...]:
        """Return controls valid for ``status`` without executing anything.

        A waiting checkpoint exposes exactly the input or approval handoff it
        is waiting for.  A paused checkpoint can resume, and an active
        checkpoint can request a pause.  Terminal and unknown statuses are
        deliberately denied.
        """

        if not isinstance(status, str):
            return ()
        normalized_status = status.strip().lower()
        action_by_status: dict[str, ControlAction] = {
            "created": "pause",
            "queued": "pause",
            "running": "pause",
            "paused": "resume",
            "waiting_input": "input",
            "waiting_approval": "approve",
        }
        action = action_by_status.get(normalized_status)
        if action is None or action not in self.declared_controls:
            return ()
        return (action,)

    def allows(self, action: str, status: str) -> bool:
        """Check one action against the same fail-closed projection."""

        return action in self.available_controls(status)


UNIFIED_RUNTIME_CONTROL_POLICY = RuntimeControlPolicy(
    runtime_kind="runtime",
    supports_pause=True,
    supports_resume=True,
    supports_approval=True,
    supports_input=True,
)

LEARNING_LOOP_CONTROL_POLICY = RuntimeControlPolicy(
    runtime_kind="learning_loop",
    supports_pause=True,
    supports_resume=True,
    supports_approval=True,
    supports_input=True,
)

_KNOWN_POLICIES: dict[str, RuntimeControlPolicy] = {
    "runtime": UNIFIED_RUNTIME_CONTROL_POLICY,
    "task_runtime": UNIFIED_RUNTIME_CONTROL_POLICY,
    "learning_loop": LEARNING_LOOP_CONTROL_POLICY,
    "teaching_interaction": LEARNING_LOOP_CONTROL_POLICY,
    "learning_progress": LEARNING_LOOP_CONTROL_POLICY,
}


def control_policy_for_runtime_kind(runtime_kind: str) -> RuntimeControlPolicy:
    """Resolve a runtime policy, denying all controls for unknown kinds."""

    if not isinstance(runtime_kind, str):
        return RuntimeControlPolicy(runtime_kind="unknown")
    return _KNOWN_POLICIES.get(
        runtime_kind.strip().lower(),
        RuntimeControlPolicy(runtime_kind="unknown"),
    )


__all__ = [
    "ControlAction",
    "LEARNING_LOOP_CONTROL_POLICY",
    "RuntimeControlPolicy",
    "UNIFIED_RUNTIME_CONTROL_POLICY",
    "control_policy_for_runtime_kind",
]
