from __future__ import annotations

import re

import pytest
from app.agents import AgentRegistry
from app.runtime import RuntimeHandlerRegistry
from app.services.runtime_agent_readiness import RuntimeAgentReadinessService
from app.services.runtime_business_registry import RuntimeBusinessRegistry
from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry
from app.services.runtime_launch_policy import RuntimeLaunchPolicy

ACTION_ID = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
FORBIDDEN_FRAGMENTS = ("/", "\\", "password", "secret", "token", "credential")


def _service() -> RuntimeAgentReadinessService:
    release_registry = RuntimeCanaryReleaseRegistry()
    return RuntimeAgentReadinessService(
        AgentRegistry(),
        RuntimeBusinessRegistry([]),  # type: ignore[arg-type]
        RuntimeLaunchPolicy(
            "",
            release_registry=release_registry,
            release_gate_required=True,
        ),
        lifecycle_enabled=True,
        release_registry=release_registry,
        handler_registry=RuntimeHandlerRegistry(),
    )


def _assert_safe_action_ids(actions: tuple[str, ...]) -> None:
    assert all(ACTION_ID.fullmatch(action) for action in actions)
    lowered = " ".join(actions).lower()
    assert not any(fragment in lowered for fragment in FORBIDDEN_FRAGMENTS)


def test_runtime_service_missing_has_stable_registration_action() -> None:
    item = _service().inspect("GENERAL_QUESTION_V1")

    assert item.status == "legacy_only"
    assert item.blockers == ("runtime_service_missing",)
    assert item.recommended_actions == ("register_runtime_business_service",)
    _assert_safe_action_ids(item.recommended_actions)


@pytest.mark.parametrize(
    ("blocker", "expected"),
    [
        (
            "canary_release_evidence_missing",
            (
                "run_provider_free_release_preflight",
                "collect_authorized_paired_trace",
            ),
        ),
        (
            "canary_provenance_incomplete",
            (
                "run_provider_free_release_preflight",
                "collect_authorized_paired_trace",
            ),
        ),
        (
            "semantic_evidence_missing",
            (
                "run_provider_free_release_preflight",
                "collect_semantic_evidence_for_authorized_trace",
            ),
        ),
        (
            "semantic_decision_not_pass",
            (
                "run_provider_free_release_preflight",
                "collect_semantic_evidence_for_authorized_trace",
            ),
        ),
    ],
)
def test_release_and_semantic_blockers_map_to_stable_actions(
    blocker: str, expected: tuple[str, ...]
) -> None:
    actions = RuntimeAgentReadinessService._recommended_actions(
        status="blocked", blockers=(blocker,)
    )

    assert actions == expected
    _assert_safe_action_ids(actions)


def test_default_ready_has_observe_then_approve_actions() -> None:
    actions = RuntimeAgentReadinessService._recommended_actions(
        status="default_ready", blockers=()
    )

    assert actions == (
        "observe_canary_before_default_approval",
        "approve_default_promotion",
    )
    _assert_safe_action_ids(actions)


def test_blocked_unknown_blocker_fails_safe_without_echoing_detail() -> None:
    actions = RuntimeAgentReadinessService._recommended_actions(
        status="blocked",
        blockers=("unknown_blocker:/var/run/agent?token=secret",),
    )

    assert actions == ("review_runtime_readiness",)
    _assert_safe_action_ids(actions)
