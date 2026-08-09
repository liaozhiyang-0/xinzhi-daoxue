from __future__ import annotations

from typing import Any

from app.contracts import AgentEventType
from app.runtime.contracts import AgentRun

RUNTIME_EVENT_TYPES: dict[str, AgentEventType] = {
    "node_started": AgentEventType.PLAN_NODE_STARTED,
    "node_completed": AgentEventType.PLAN_NODE_COMPLETED,
    "node_retrying": AgentEventType.AGENT_PROGRESS,
    "node_failed": AgentEventType.AGENT_PROGRESS,
    "node_blocked": AgentEventType.AGENT_PROGRESS,
    "approval_required": AgentEventType.AGENT_PROGRESS,
    "node_recovered": AgentEventType.AGENT_PROGRESS,
    "node_recovery_required": AgentEventType.AGENT_PROGRESS,
    "node_suspended": AgentEventType.AGENT_PROGRESS,
}


def to_task_event(
    event: str, run: AgentRun, node_id: str
) -> tuple[AgentEventType, dict[str, Any]]:
    """Translate an internal Runtime event into the stable Task/SSE shape."""

    try:
        event_type = RUNTIME_EVENT_TYPES[event]
    except KeyError as exc:
        raise ValueError(f"unknown runtime event: {event}") from exc
    node = next(
        (item for item in run.plan.nodes if item.node_id == node_id),
        None,
    )
    if node is None:
        raise ValueError(f"runtime node missing from plan: {node_id}")
    state = run.nodes[node_id]
    return event_type, {
        "runtime_run_id": run.run_id,
        "plan_id": run.plan.plan_id,
        "plan_version": run.plan.version,
        "node_id": node.node_id,
        "node_type": node.node_type,
        "handler_id": node.handler_id,
        "execution_key": state.execution_key,
        "effect_status": state.effect_status.value,
        "status": state.status.value,
        "attempt": state.attempt,
        "error_code": state.error_code,
    }


def build_runtime_observability(run: AgentRun) -> dict[str, Any]:
    """Build a bounded, redaction-ready observe/decide/verify projection.

    Node observations are attached to their node state, while controller
    decisions and verifier results are durable Run-level histories.  Keeping
    this projection pure makes it usable by Debug/API adapters without
    coupling Runtime execution to HTTP or persistence.
    """

    decisions = [
        decision.model_dump(mode="json") for decision in run.decision_history
    ]
    if not decisions and run.last_decision is not None:
        # Older checkpoints only carried the latest decision.
        decisions = [run.last_decision.model_dump(mode="json")]
    verifications = [
        observation.model_dump(mode="json")
        for observation in run.verification_history
    ]
    observations: list[dict[str, Any]] = []
    node_projections: list[dict[str, Any]] = []
    for node in run.plan.nodes:
        state = run.nodes[node.node_id]
        node_observation = (
            state.observation.model_dump(mode="json")
            if state.observation is not None
            else None
        )
        if node_observation is not None:
            observations.append(node_observation)
            if (
                node.node_type.casefold() == "verification"
                or node_observation.get("facts", {}).get("phase") == "verify"
            ) and node_observation not in verifications:
                verifications.append(node_observation)
        node_decisions = [
            {
                "index": index,
                **decision,
            }
            for index, decision in enumerate(decisions)
            if node.node_id in decision.get("node_ids", [])
        ]
        node_verifications = [
            observation
            for observation in verifications
            if observation.get("node_id") == node.node_id
        ]
        node_projections.append(
            {
                "node_id": node.node_id,
                "observation": node_observation,
                "decisions": node_decisions,
                "verifications": node_verifications,
            }
        )
    return {
        "schema_version": "1",
        "observations": observations,
        "decisions": decisions,
        "verifications": verifications,
        "nodes": node_projections,
    }
