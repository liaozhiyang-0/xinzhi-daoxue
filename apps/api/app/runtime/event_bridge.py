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
