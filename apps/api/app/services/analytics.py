from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.analytics import AnalyticsQuery, AnalyticsReportRead
from app.models import (
    AccountModel,
    AgentPlanProposalModel,
    AgentRunModel,
    AgentRunNodeModel,
    ConversationMessageModel,
    SessionModel,
    TaskEventModel,
    TaskFeedbackModel,
    TaskModel,
    TaskStatus,
)

TERMINAL = {
    TaskStatus.COMPLETED.value,
    TaskStatus.FAILED.value,
    TaskStatus.CANCELLED.value,
}


def _value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _nested(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _task_scenario(task: TaskModel) -> str:
    content = _record(task.input_content)
    canonical = _record(content.get("canonical_input"))
    return str(
        canonical.get("scenario_case_id")
        or content.get("scenario_case_id")
        or content.get("scenario_id")
        or ""
    )


def _task_quick_template_used(task: TaskModel) -> bool:
    content = _record(task.input_content)
    canonical = _record(content.get("canonical_input"))
    options = _record(content.get("options"))
    return any(
        source.get("_scenario_catalog_bound") is True
        or source.get("quick_template_used") is True
        or bool(source.get("scenario_id"))
        for source in (content, canonical, options)
    )


def _task_pilot_batch(task: TaskModel) -> str:
    content = _record(task.input_content)
    options = _record(content.get("options"))
    return str(
        content.get("pilot_batch_id")
        or options.get("pilot_batch_id")
        or _nested(content, "canonical_input", "pilot_batch_id")
        or ""
    )


def _task_capability(task: TaskModel) -> str:
    content = _record(task.input_content)
    return str(
        content.get("capability_id") or content.get("agent_id") or task.agent_id or ""
    )


def _task_dimension_values(task: TaskModel, name: str) -> list[str]:
    """Return scalar or list-valued dimensions without exposing raw input."""

    content = _record(task.input_content)
    canonical = _record(content.get("canonical_input"))
    options = _record(content.get("options"))
    aliases = {
        "skill": ("skill", "skill_id", "skill_ids", "selected_skills"),
        "tool": ("tool", "tool_id", "tool_ids", "selected_tools"),
    }
    keys = aliases.get(name, (name,))
    values: list[str] = []
    for source in (content, canonical, options):
        for key in keys:
            candidate = source.get(key)
            if isinstance(candidate, list):
                values.extend(
                    str(item).strip()
                    for item in candidate
                    if str(item).strip()
                )
            elif candidate is not None and str(candidate).strip():
                values.append(str(candidate).strip())
    return list(dict.fromkeys(values))


def _task_input_mode(task: TaskModel) -> str:
    content = _record(task.input_content)
    attachments = content.get("attachments")
    return "multimodal" if isinstance(attachments, list) and attachments else "text"


def _task_dimension(task: TaskModel, name: str) -> str:
    """Read a bounded, non-sensitive analytics dimension from task metadata."""

    return (_task_dimension_values(task, name) or [""])[0]


def _result_flags(task: TaskModel) -> dict[str, bool]:
    result = _record(task.result_content)
    evidence = result.get("evidence_view")
    citations = result.get("citations") or _nested(result, "presentation", "citations")
    review = result.get("review_required") or _nested(
        result, "presentation", "requires_review"
    )
    insufficient = str(result.get("evidence_status") or "") in {"insufficient", "empty"}
    return {
        "evidence": isinstance(evidence, list) and bool(evidence),
        "citation": isinstance(citations, list) and bool(citations),
        "review": bool(review),
        "insufficient_evidence": insufficient,
    }


def _percentile(values: Iterable[float], percentile: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return round(ordered[0], 2)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 2)


def _duration_ms(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    # SQLite may return naive datetimes even for timezone-aware columns.
    # Normalizing both values keeps the read model portable across test and prod DBs.
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    return max(0.0, (end - start).total_seconds() * 1000)


def _event_payload(event: TaskEventModel) -> dict[str, Any]:
    raw = _record(event.event_data)
    nested = _record(raw.get("data"))
    return {**raw, **nested}


def _local_date(value: datetime, timezone: str) -> str:
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("UTC")
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(zone).date().isoformat()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _numeric_metric(value: Any, *keys: str) -> float | None:
    record = _record(value)
    for key in keys:
        candidate = record.get(key)
        if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
            return float(candidate)
    return None


class AnalyticsService:
    """Bounded read-model queries over the existing operational tables."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _load(self, query: AnalyticsQuery) -> dict[str, Any]:
        task_rows = list(
            (
                await self.db.scalars(
                    select(TaskModel)
                    .where(
                        TaskModel.created_at >= query.window_start,
                        TaskModel.created_at <= query.window_end,
                    )
                    .order_by(TaskModel.created_at.desc())
                    .limit(query.row_limit + 1)
                )
            ).all()
        )
        truncated = len(task_rows) > query.row_limit
        tasks = task_rows[: query.row_limit]
        sessions = list(
            (
                await self.db.scalars(
                    select(SessionModel)
                    .where(
                        SessionModel.created_at >= query.window_start,
                        SessionModel.created_at <= query.window_end,
                    )
                    .order_by(SessionModel.created_at.desc())
                    .limit(query.row_limit + 1)
                )
            ).all()
        )
        messages = list(
            (
                await self.db.scalars(
                    select(ConversationMessageModel)
                    .where(
                        ConversationMessageModel.created_at >= query.window_start,
                        ConversationMessageModel.created_at <= query.window_end,
                    )
                    .order_by(ConversationMessageModel.created_at.desc())
                    .limit(query.row_limit + 1)
                )
            ).all()
        )
        all_user_ids = {
            value
            for value in (
                [task.user_id for task in tasks]
                + [session.user_id for session in sessions]
                + [message.user_id for message in messages]
            )
            if value
        }
        account_rows = (
            list(
                (
                    await self.db.scalars(
                        select(AccountModel).where(AccountModel.id.in_(all_user_ids))
                    )
                ).all()
            )
            if all_user_ids
            else []
        )
        roles = {account.id: account.role for account in account_rows}
        if query.role:
            tasks = [
                task for task in tasks if roles.get(task.user_id, "guest") == query.role
            ]
            sessions = [
                session
                for session in sessions
                if roles.get(session.user_id, "guest") == query.role
            ]
        if query.course:
            tasks = [task for task in tasks if task.course_id == query.course]
            sessions = [
                session for session in sessions if session.course_id == query.course
            ]
        if query.intent:
            tasks = [task for task in tasks if task.intent == query.intent]
        if query.provider:
            tasks = [task for task in tasks if task.provider == query.provider]
        if query.task_id:
            tasks = [task for task in tasks if task.id == query.task_id]
        if query.scenario:
            tasks = [task for task in tasks if _task_scenario(task) == query.scenario]
        if query.pilot_batch:
            tasks = [
                task for task in tasks if _task_pilot_batch(task) == query.pilot_batch
            ]
        if query.capability:
            tasks = [
                task for task in tasks if _task_capability(task) == query.capability
            ]
        if query.skill:
            tasks = [
                task
                for task in tasks
                if query.skill in _task_dimension_values(task, "skill")
            ]
        if query.tool:
            tasks = [
                task
                for task in tasks
                if query.tool in _task_dimension_values(task, "tool")
            ]
        if query.model:
            tasks = [
                task for task in tasks if _task_dimension(task, "model") == query.model
            ]
        if query.task_id:
            task_session_ids = {task.session_id for task in tasks}
            sessions = [
                session for session in sessions if session.id in task_session_ids
            ]
        session_ids = {session.id for session in sessions}
        session_ids.update(task.session_id for task in tasks)
        messages = [
            message for message in messages if message.session_id in session_ids
        ]
        task_ids = {task.id for task in tasks}
        feedback = list(
            (
                await self.db.scalars(
                    select(TaskFeedbackModel)
                    .where(
                        TaskFeedbackModel.created_at >= query.window_start,
                        TaskFeedbackModel.created_at <= query.window_end,
                    )
                    .order_by(TaskFeedbackModel.created_at.desc())
                    .limit(query.row_limit + 1)
                )
            ).all()
        )
        feedback = [item for item in feedback if item.task_id in task_ids]
        runs = list(
            (
                await self.db.scalars(
                    select(AgentRunModel)
                    .where(
                        AgentRunModel.created_at >= query.window_start,
                        AgentRunModel.created_at <= query.window_end,
                    )
                    .order_by(AgentRunModel.created_at.desc())
                    .limit(query.row_limit + 1)
                )
            ).all()
        )
        runs = [run for run in runs if run.task_id in task_ids]
        events = list(
            (
                await self.db.scalars(
                    select(TaskEventModel)
                    .where(
                        TaskEventModel.created_at >= query.window_start,
                        TaskEventModel.created_at <= query.window_end,
                    )
                    .order_by(TaskEventModel.created_at.desc())
                    .limit(query.row_limit + 1)
                )
            ).all()
        )
        events = [event for event in events if event.task_id in task_ids]
        nodes: list[AgentRunNodeModel] = []
        proposals: list[AgentPlanProposalModel] = []
        if task_ids:
            nodes = list(
                (
                    await self.db.scalars(
                        select(AgentRunNodeModel)
                        .where(
                            AgentRunNodeModel.created_at >= query.window_start,
                            AgentRunNodeModel.created_at <= query.window_end,
                            AgentRunNodeModel.run_id.in_(
                                {run.id for run in runs}
                            ),
                        )
                        .order_by(AgentRunNodeModel.created_at.desc())
                        .limit(query.row_limit + 1)
                    )
                ).all()
            )
            proposals = list(
                (
                    await self.db.scalars(
                        select(AgentPlanProposalModel)
                        .where(
                            AgentPlanProposalModel.created_at >= query.window_start,
                            AgentPlanProposalModel.created_at <= query.window_end,
                            AgentPlanProposalModel.task_id.in_(task_ids),
                        )
                        .order_by(AgentPlanProposalModel.created_at.desc())
                        .limit(query.row_limit + 1)
                    )
                ).all()
            )
        warnings = ["analytics_row_limit_reached"] if truncated else []
        try:
            ZoneInfo(query.timezone)
        except ZoneInfoNotFoundError:
            warnings.append("analytics_timezone_invalid_fallback_utc")
        return {
            "tasks": tasks,
            "sessions": sessions,
            "messages": messages,
            "feedback": feedback,
            "runs": runs,
            "nodes": nodes,
            "proposals": proposals,
            "events": events,
            "roles": roles,
            "truncated": truncated,
            "warnings": warnings,
        }

    def _base(
        self,
        query: AnalyticsQuery,
        data: dict[str, Any],
        metrics: dict[str, Any],
        breakdowns: dict[str, Any],
        definitions: dict[str, str],
    ) -> AnalyticsReportRead:
        return AnalyticsReportRead(
            window_start=query.window_start,
            window_end=query.window_end,
            filters={
                "timezone": query.timezone,
                "course": query.course,
                "role": query.role,
                "intent": query.intent,
                "capability": query.capability,
                "skill": query.skill,
                "tool": query.tool,
                "scenario": query.scenario,
                "provider": query.provider,
                "model": query.model,
                "task_id": query.task_id,
                "pilot_batch": query.pilot_batch,
            },
            row_limit=query.row_limit,
            truncated=bool(data["truncated"]),
            metrics=metrics,
            breakdowns=breakdowns,
            definitions=definitions,
            data_quality_warnings=data["warnings"],
        )

    async def report(self, kind: str, query: AnalyticsQuery) -> AnalyticsReportRead:
        data = await self._load(query)
        tasks: list[TaskModel] = data["tasks"]
        sessions: list[SessionModel] = data["sessions"]
        messages: list[ConversationMessageModel] = data["messages"]
        feedback: list[TaskFeedbackModel] = data["feedback"]
        runs: list[AgentRunModel] = data["runs"]
        nodes: list[AgentRunNodeModel] = data["nodes"]
        proposals: list[AgentPlanProposalModel] = data["proposals"]
        events: list[TaskEventModel] = data["events"]
        statuses = Counter(str(_value(task.status)) for task in tasks)
        terminal = [task for task in tasks if str(_value(task.status)) in TERMINAL]
        completed = [
            task
            for task in tasks
            if str(_value(task.status)) == TaskStatus.COMPLETED.value
        ]
        users = {
            value
            for value in (
                [task.user_id for task in tasks]
                + [session.user_id for session in sessions]
                + [message.user_id for message in messages]
            )
            if value
        }
        activity_points: list[tuple[str, datetime]] = []
        for task in tasks:
            activity_points.append((task.user_id, task.created_at))
        for session in sessions:
            activity_points.append((session.user_id, session.created_at))
            if session.last_message_at is not None:
                activity_points.append((session.user_id, session.last_message_at))
        for message in messages:
            activity_points.append((message.user_id, message.created_at))
        end_time = _aware(query.window_end)
        daily_cutoff = end_time - timedelta(days=1)
        weekly_cutoff = end_time - timedelta(days=7)
        monthly_cutoff = end_time - timedelta(days=30)
        active_daily = {
            user_id
            for user_id, timestamp in activity_points
            if daily_cutoff < _aware(timestamp) <= end_time
        }
        active_weekly = {
            user_id
            for user_id, timestamp in activity_points
            if weekly_cutoff < _aware(timestamp) <= end_time
        }
        active_monthly = {
            user_id
            for user_id, timestamp in activity_points
            if monthly_cutoff < _aware(timestamp) <= end_time
        }
        user_activity_days: dict[str, set[str]] = defaultdict(set)
        for user_id, timestamp in activity_points:
            user_activity_days[user_id].add(_local_date(timestamp, query.timezone))
        returning_users = sum(
            len(days) > 1 for days in user_activity_days.values()
        )
        flags = [_result_flags(task) for task in completed]
        completed_task_ids = {task.id for task in completed}
        feedback_task_ids = {item.task_id for item in feedback}
        review_task_ids = {
            task.id
            for task, flag in zip(completed, flags, strict=False)
            if flag["review"]
        }
        review_task_ids.update(
            item.task_id for item in feedback if item.manual_review_required
        )
        skill_breakdown: Counter[str] = Counter()
        tool_breakdown: Counter[str] = Counter()
        for task in tasks:
            skill_breakdown.update(_task_dimension_values(task, "skill"))
            tool_breakdown.update(_task_dimension_values(task, "tool"))
        task_breakdowns = {
            "status": dict(statuses),
            "course": dict(Counter(task.course_id for task in tasks)),
            "intent": dict(Counter(task.intent for task in tasks)),
            "provider": dict(Counter(task.provider for task in tasks)),
            "scenario": dict(
                Counter(_task_scenario(task) or "unspecified" for task in tasks)
            ),
            "capability": dict(
                Counter(_task_capability(task) or "unspecified" for task in tasks)
            ),
            "input_mode": dict(Counter(_task_input_mode(task) for task in tasks)),
            "skill": dict(skill_breakdown),
            "tool": dict(tool_breakdown),
            "pilot_batch": dict(
                Counter(_task_pilot_batch(task) or "unspecified" for task in tasks)
            ),
            "pilot_case_type": dict(
                Counter(
                    _task_dimension(task, "pilot_case_type") or "unspecified"
                    for task in tasks
                )
            ),
            "quick_template_used": dict(
                Counter(str(_task_quick_template_used(task)).lower() for task in tasks)
            ),
        }
        answer_metrics = {
            "questions": sum(1 for message in messages if message.role == "user"),
            "answers_completed": len(completed),
            "answers_with_evidence": sum(item["evidence"] for item in flags),
            "answers_with_citations": sum(item["citation"] for item in flags),
            "feedback_count": len(feedback),
            "feedback_coverage": (
                len(feedback_task_ids & completed_task_ids) / len(completed)
                if completed
                else None
            ),
            "resolved_count": sum(
                item.resolved is True for item in feedback if item.resolved is not None
            ),
            "resolved_rate": (
                sum(
                    item.resolved is True
                    for item in feedback
                    if item.resolved is not None
                )
                / sum(item.resolved is not None for item in feedback)
                if any(item.resolved is not None for item in feedback)
                else None
            ),
            "satisfaction_rate": (
                sum(
                    item.satisfaction == "satisfied"
                    for item in feedback
                    if item.satisfaction
                )
                / sum(item.satisfaction is not None for item in feedback)
                if any(item.satisfaction is not None for item in feedback)
                else None
            ),
            "review_required_count": len(review_task_ids),
            "evidence_coverage": (
                sum(item["evidence"] for item in flags) / len(completed)
                if completed
                else None
            ),
            "citation_coverage": (
                sum(item["citation"] for item in flags) / len(completed)
                if completed
                else None
            ),
            "insufficient_evidence_count": sum(
                item["insufficient_evidence"] for item in flags
            ),
        }
        latency = [
            value
            for value in (
                _duration_ms(task.created_at, task.completed_at) for task in terminal
            )
            if value is not None
        ]
        queue_latency = [
            value
            for value in (
                _duration_ms(task.created_at, task.started_at) for task in tasks
            )
            if value is not None
        ]
        stage_latency_values: dict[str, list[float]] = defaultdict(list)
        stage_keys = {
            "planner": ("planner_latency_ms", "planning_latency_ms"),
            "retrieval": ("retrieval_latency_ms", "rag_latency_ms"),
            "tool": ("tool_latency_ms",),
            "provider": ("provider_latency_ms", "model_latency_ms"),
            "verification": ("verification_latency_ms",),
            "presentation": ("presentation_latency_ms",),
        }
        for run in runs:
            metrics_data = _record(run.metrics_data)
            nested_stage_data = _record(
                metrics_data.get("stage_latency_ms")
                or metrics_data.get("stage_latencies")
            )
            for stage, keys in stage_keys.items():
                value = _numeric_metric(metrics_data, *keys)
                if value is None:
                    value = _numeric_metric(nested_stage_data, *keys, stage)
                if value is not None:
                    stage_latency_values[stage].append(value)
        performance = {
            "task_latency_p50": _percentile(latency, 0.50),
            "task_latency_p95": _percentile(latency, 0.95),
            "task_latency_p99": _percentile(latency, 0.99),
            "queue_latency_p50": _percentile(queue_latency, 0.50),
            "queue_latency_p95": _percentile(queue_latency, 0.95),
            "queue_latency_p99": _percentile(queue_latency, 0.99),
            "measured_task_latency_count": len(latency),
            "measured_queue_latency_count": len(queue_latency),
            "agent_run_latency_p50": _percentile(
                [float(run.latency_ms) for run in runs if run.latency_ms is not None],
                0.50,
            ),
            "agent_run_latency_p95": _percentile(
                [float(run.latency_ms) for run in runs if run.latency_ms is not None],
                0.95,
            ),
            "agent_run_latency_p99": _percentile(
                [float(run.latency_ms) for run in runs if run.latency_ms is not None],
                0.99,
            ),
        }
        for stage, stage_values in stage_latency_values.items():
            performance[f"{stage}_latency_p50"] = _percentile(stage_values, 0.50)
            performance[f"{stage}_latency_p95"] = _percentile(stage_values, 0.95)
            performance[f"{stage}_latency_p99"] = _percentile(stage_values, 0.99)
            performance[f"measured_{stage}_latency_count"] = len(stage_values)
        event_types = [event.event_type for event in events]
        plan_ids = {run.plan_id for run in runs if run.plan_id}
        planned_task_ids = {run.task_id for run in runs if run.plan_id}
        planned_task_ids.update(
            event.task_id for event in events if event.event_type == "plan.created"
        )
        replan_event_types = {
            "route.reevaluated",
            "plan.replanned",
            "plan.rerouted",
            "runtime.replan",
        }
        replan_task_ids = {
            event.task_id for event in events if event.event_type in replan_event_types
        }
        replan_task_ids.update(proposal.task_id for proposal in proposals)
        tool_nodes = [node for node in nodes if node.node_type == "tool"]
        tool_success_count = sum(
            node.status in {"completed", "succeeded", "success"} for node in tool_nodes
        )
        tool_failure_count = sum(
            node.status in {"failed", "error", "timeout"} for node in tool_nodes
        )
        retrieval_calls = sum(run.retrieval_calls for run in runs) + sum(
            event_type
            in {
                "knowledge.retrieved",
                "knowledge.context_built",
                "external_retrieval.completed",
            }
            for event_type in event_types
        )
        retrieval_empty_count = sum(
            event_type in {"knowledge.insufficient", "external_retrieval.failed"}
            for event_type in event_types
        )
        verification_count = sum(
            "verification" in event_type
            for event_type in event_types
        ) + sum(
            node.node_type in {"verification", "verifier"} for node in nodes
        )
        reflection_count = sum(
            any(token in event_type for token in ("reflection", "critic", "revision"))
            for event_type in event_types
        ) + sum(
            any(
                key in _record(task.result_content)
                for key in ("reflection", "critic", "revision")
            )
            for task in tasks
        )
        fallback_task_ids = {
            task.id
            for task in tasks
            if bool(_record(task.result_content).get("fallback_used"))
            or "fallback" in task.route_status.lower()
        }
        resume_event_types = {"task.resumed", "runtime.resumed", "agent.resumed"}
        resumed_task_ids = {
            event.task_id for event in events if event.event_type in resume_event_types
        }
        agentic = {
            "planner_plan_count": len(plan_ids),
            "planner_task_count": len(planned_task_ids),
            "capability_usage": sum(
                event_type in {"agent.started", "agent.output"}
                for event_type in event_types
            ),
            "capability_task_count": len(
                {task.id for task in tasks if _task_capability(task)}
            ),
            "skill_usage": sum(
                event_type == "skill.selected" for event_type in event_types
            ),
            "tool_usage": (
                len(tool_nodes)
                if tool_nodes
                else sum(event_type == "tool.selected" for event_type in event_types)
                + sum(run.tool_calls for run in runs)
            ),
            "tool_success_count": tool_success_count,
            "tool_failure_count": tool_failure_count,
            "tool_success_rate": (
                tool_success_count / (tool_success_count + tool_failure_count)
                if tool_success_count + tool_failure_count
                else None
            ),
            "rag_usage": retrieval_calls,
            "retrieval_empty_count": retrieval_empty_count,
            "rag_empty_rate": (
                retrieval_empty_count / retrieval_calls if retrieval_calls else None
            ),
            "verification_usage": verification_count,
            "reflection_usage": reflection_count,
            "replan_count": len(replan_task_ids),
            "replan_rate": (
                len(replan_task_ids) / len(planned_task_ids)
                if planned_task_ids
                else None
            ),
            "fallback_count": len(fallback_task_ids),
            "fallback_rate": len(fallback_task_ids) / len(tasks) if tasks else None,
            "resume_count": len(resumed_task_ids),
            "resume_rate": len(resumed_task_ids) / len(tasks) if tasks else None,
            "runtime_retry_rate": sum(task.attempt > 1 for task in tasks) / len(tasks)
            if tasks
            else None,
        }
        daily: dict[str, dict[str, int]] = defaultdict(
            lambda: {
                "users": 0,
                "sessions": 0,
                "messages": 0,
                "tasks": 0,
                "completed_tasks": 0,
            }
        )
        daily_users: dict[str, set[str]] = defaultdict(set)
        for task in tasks:
            day = _local_date(task.created_at, query.timezone)
            daily[day]["tasks"] += 1
            daily_users[day].add(task.user_id)
            if str(_value(task.status)) == TaskStatus.COMPLETED.value:
                daily[day]["completed_tasks"] += 1
        for session in sessions:
            day = _local_date(session.created_at, query.timezone)
            daily[day]["sessions"] += 1
            daily_users[day].add(session.user_id)
        for message in messages:
            day = _local_date(message.created_at, query.timezone)
            daily[day]["messages"] += 1
            daily_users[day].add(message.user_id)
        for day, user_set in daily_users.items():
            daily[day]["users"] = len(user_set)
        session_user_messages: dict[str, int] = Counter(
            message.session_id for message in messages if message.role == "user"
        )
        session_activity: dict[str, list[datetime]] = defaultdict(list)
        for session in sessions:
            session_activity[session.id].append(session.created_at)
            if session.last_message_at is not None:
                session_activity[session.id].append(session.last_message_at)
        for message in messages:
            session_activity[message.session_id].append(message.created_at)
        session_durations: list[float] = []
        for timestamps in session_activity.values():
            if not timestamps:
                continue
            duration = _duration_ms(min(timestamps), max(timestamps))
            if duration is not None:
                session_durations.append(duration)
        sessions_with_questions = set(session_user_messages)
        followup_session_count = sum(
            count > 1 for count in session_user_messages.values()
        )
        sessions_by_user = Counter(session.user_id for session in sessions)
        returning_user_count = sum(
            count > 1 for count in sessions_by_user.values()
        )
        definitions = {
            "active_users": (
                "窗口内创建 Session、发送 Message 或提交 Task 的去重用户数。"
            ),
            "completion_rate": (
                "completed / terminal_tasks，其中 terminal_tasks 包含 "
                "completed、failed、cancelled。"
            ),
            "feedback_coverage": "有反馈的已完成回答 / 已完成回答。",
            "resolved_rate": "resolved=true / 提供 resolved 判断的反馈。",
            "satisfaction_rate": "satisfied / 提供满意度的反馈。",
            "active_users_daily": (
                "窗口结束前 24 小时内发生有效 Session、Message 或 Task "
                "行为的去重用户数。"
            ),
            "active_users_weekly": "窗口结束前 7 天内发生有效产品行为的去重用户数。",
            "active_users_monthly": "窗口结束前 30 天内发生有效产品行为的去重用户数。",
            "returning_users": "窗口内在至少两个不同本地日期发生有效行为的用户数。",
            "followup_rate": (
                "同一会话中提交超过一次用户问题的会话 / 有用户问题的会话。"
            ),
            "session_duration_p50": (
                "会话内最后一次有效活动时间减首次有效活动时间的中位数（毫秒）。"
            ),
            "task_latency_p95": (
                "从 Task created_at 到 completed_at/terminal 时间的 95 分位毫秒数。"
            ),
            "replan_rate": (
                "发生 bounded replan 事件的任务事件数 / 任务数，"
                "表示运行相关性，不代表因果效果。"
            ),
        }
        common_metrics: dict[str, Any] = {
            "registered_users": 0,
            "new_users": 0,
            "active_users": len(users),
            "active_users_daily": len(active_daily),
            "active_users_weekly": len(active_weekly),
            "active_users_monthly": len(active_monthly),
            "returning_users": returning_users,
            "returning_user_rate": returning_users / len(users) if users else None,
            "sessions_created": len(sessions),
            "session_return_count": returning_user_count,
            "session_return_rate": (
                returning_user_count / len(users) if users else None
            ),
            "session_duration_p50": _percentile(session_durations, 0.50),
            "session_duration_p95": _percentile(session_durations, 0.95),
            "messages": len(messages),
            "tasks_created": len(tasks),
            "tasks_completed": len(completed),
            "tasks_failed": statuses.get(TaskStatus.FAILED.value, 0),
            "tasks_cancelled": statuses.get(TaskStatus.CANCELLED.value, 0),
            "tasks_waiting_review": statuses.get(TaskStatus.WAITING_REVIEW.value, 0),
            "tasks_waiting_user": statuses.get(TaskStatus.WAITING_USER.value, 0),
            "completion_rate": len(completed) / len(terminal) if terminal else None,
            "failure_rate": statuses.get(TaskStatus.FAILED.value, 0) / len(terminal)
            if terminal
            else None,
            "cancellation_rate": statuses.get(TaskStatus.CANCELLED.value, 0)
            / len(terminal)
            if terminal
            else None,
            "retry_rate": sum(task.attempt > 1 for task in tasks) / len(tasks)
            if tasks
            else None,
            "human_review_rate": int(answer_metrics["review_required_count"] or 0)
            / len(tasks)
            if tasks
            else None,
            "followup_rate": (
                followup_session_count / len(sessions_with_questions)
                if sessions_with_questions
                else None
            ),
            **answer_metrics,
            **agentic,
            **performance,
        }
        if kind in {"overview", "users"}:
            common_metrics["registered_users"] = int(
                await self.db.scalar(select(func.count(AccountModel.id))) or 0
            )
            common_metrics["new_users"] = int(
                await self.db.scalar(
                    select(func.count(AccountModel.id)).where(
                        AccountModel.created_at >= query.window_start,
                        AccountModel.created_at <= query.window_end,
                    )
                )
                or 0
            )
        if kind == "sessions":
            session_messages = Counter(message.session_id for message in messages)
            common_metrics.update(
                {
                    "active_sessions": sum(
                        session.last_message_at is not None
                        and session.archived_at is None
                        for session in sessions
                    ),
                    "sessions_per_user": len(sessions) / len(users) if users else None,
                    "messages_per_session": len(messages) / len(sessions)
                    if sessions
                    else None,
                    "tasks_per_session": len(tasks) / len(sessions)
                    if sessions
                    else None,
                    "followup_rate": sum(
                        count > 1 for count in session_messages.values()
                    )
                    / len(session_messages)
                    if session_messages
                    else None,
                }
            )
        if kind == "answers":
            common_metrics.update(
                {
                    "evidence_coverage": int(
                        answer_metrics["answers_with_evidence"] or 0
                    )
                    / len(completed)
                    if completed
                    else None,
                    "citation_coverage": int(
                        answer_metrics["answers_with_citations"] or 0
                    )
                    / len(completed)
                    if completed
                    else None,
                    "problem_type_count": len(
                        Counter(item.problem_type or "unspecified" for item in feedback)
                    ),
                }
            )
        if kind == "performance":
            common_metrics = performance
        if kind == "agentic":
            common_metrics = agentic
        if kind == "courses":
            common_metrics = {
                "course_count": len(task_breakdowns["course"]),
                "task_count": len(tasks),
                "active_students": len(
                    {
                        task.user_id
                        for task in tasks
                        if data["roles"].get(task.user_id, "guest") == "student"
                    }
                ),
            }
        if kind == "teacher":
            common_metrics = {
                key: common_metrics[key]
                for key in (
                    "active_users",
                    "sessions_created",
                    "messages",
                    "tasks_created",
                    "tasks_completed",
                    "completion_rate",
                    "questions",
                    "feedback_count",
                    "feedback_coverage",
                    "resolved_rate",
                    "satisfaction_rate",
                    "review_required_count",
                    "human_review_rate",
                    "evidence_coverage",
                    "citation_coverage",
                )
                if key in common_metrics
            }
            common_metrics["active_students"] = len(
                {
                    user_id
                    for user_id in users
                    if data["roles"].get(user_id, "guest") == "student"
                }
            )
            common_metrics["course_count"] = len(task_breakdowns["course"])
        return self._base(
            query,
            data,
            common_metrics,
            {
                "daily": [
                    {"date": day, **values} for day, values in sorted(daily.items())
                ],
                "roles": dict(
                    Counter(data["roles"].get(user_id, "guest") for user_id in users)
                ),
                **task_breakdowns,
                "satisfaction": dict(
                    Counter(item.satisfaction or "unspecified" for item in feedback)
                ),
                "problem_type": dict(
                    Counter(item.problem_type or "unspecified" for item in feedback)
                ),
                "agent_status": dict(Counter(run.status for run in runs)),
            },
            definitions,
        )
