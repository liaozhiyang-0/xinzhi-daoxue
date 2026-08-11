from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

from app.api.v1.tasks import event_stream
from app.contracts import AgentEventType
from app.main import create_app
from app.models import TaskModel, TaskStatus
from app.repositories import (
    AgentRunRepository,
    RuntimePlanProposalRepository,
    TaskRepository,
)
from app.runtime import AgentRun, AgentRunPlan, RuntimeNode
from app.services.event_service import append_task_event
from app.services.runtime_plan_proposals import RuntimePlanProposalService
from fastapi.testclient import TestClient


def _parse_sse(content: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for block in content.split("\n\n"):
        lines = [line for line in block.splitlines() if line]
        event_id = next((line[4:] for line in lines if line.startswith("id: ")), None)
        event_type = next(
            (line[7:] for line in lines if line.startswith("event: ")), None
        )
        data_line = next(
            (line[6:] for line in lines if line.startswith("data: ")), None
        )
        if event_id is None or event_type is None or data_line is None:
            continue
        decoded = json.loads(data_line)
        event_data = (
            decoded.get("data", decoded)
            if isinstance(decoded, dict)
            else decoded
        )
        records.append(
            {
                "id": int(event_id),
                "event": event_type,
                "data": event_data,
            }
        )
    return records


def test_sse_ids_follow_database_sequence(api, client) -> None:
    session = api.create_session()
    task = api.create_task(session["id"])
    api.wait_for_task(task["id"])
    content = client.get(f"/api/v1/tasks/{task['id']}/stream").text
    ids = [
        int(line.removeprefix("id: "))
        for line in content.splitlines()
        if line.startswith("id: ")
    ]
    assert ids == sorted(ids)
    assert ids == list(range(1, len(ids) + 1))


def test_terminal_sse_replay_does_not_wait_for_disconnect_probe(api, app) -> None:
    """A terminal replay must complete even when no disconnect is observable."""

    session = api.create_session()
    task_id = "task-terminal-sse-replay"

    async def seed_terminal_event() -> None:
        async with app.state.session_factory() as db:
            db.add(
                TaskModel(
                    id=task_id,
                    session_id=session["id"],
                    user_id="user-test",
                    course_id="CT",
                    intent="general_qa",
                    agent_id="GENERAL_QUESTION_V1",
                    status=TaskStatus.COMPLETED,
                    input_content={"text": "terminal replay"},
                )
            )
            await db.flush()
            await append_task_event(
                db,
                task_id,
                AgentEventType.TASK_QUEUED,
                agent_id="GENERAL_QUESTION_V1",
            )
            await append_task_event(
                db,
                task_id,
                AgentEventType.TASK_COMPLETED,
                agent_id="GENERAL_QUESTION_V1",
            )
            await db.commit()

    class TerminalReplayRequest:
        def __init__(self, state: object) -> None:
            self.app = SimpleNamespace(state=state)

        async def is_disconnected(self) -> bool:
            raise AssertionError("terminal replay must not await disconnect")

    async def collect(cursor: int) -> list[str]:
        return [
            chunk
            async for chunk in event_stream(
                TerminalReplayRequest(app.state), task_id, cursor=cursor
            )
        ]

    asyncio.run(seed_terminal_event())
    full_chunks = asyncio.run(collect(0))
    reconnect_chunks = asyncio.run(collect(1))

    full_records = _parse_sse("".join(full_chunks))
    reconnect_records = _parse_sse("".join(reconnect_chunks))
    assert [record["id"] for record in full_records] == [1, 2]
    assert [record["event"] for record in full_records] == [
        "task.queued",
        "task.completed",
    ]
    assert [record["id"] for record in reconnect_records] == [2]


def test_sse_reconnect_survives_api_lifespan_restart(settings) -> None:
    """A reconnect cursor must be sufficient after the first API exits."""

    task_id = f"task-sse-restart-{uuid4().hex}"
    first_app = create_app(settings)

    with TestClient(first_app) as first_client:
        session = first_client.post(
            "/api/v1/sessions",
            json={"user_id": "user-test", "course_id": "CT", "title": "sse"},
        ).json()

        async def seed() -> None:
            async with first_app.state.session_factory() as db:
                db.add(
                    TaskModel(
                        id=task_id,
                        session_id=session["id"],
                        user_id="user-test",
                        course_id="CT",
                        intent="general_qa",
                        agent_id="GENERAL_QUESTION_V1",
                        status=TaskStatus.COMPLETED,
                        input_content={"text": "restart replay"},
                    )
                )
                await db.flush()
                await append_task_event(
                    db,
                    task_id,
                    AgentEventType.TASK_QUEUED,
                    agent_id="GENERAL_QUESTION_V1",
                )
                await append_task_event(
                    db,
                    task_id,
                    AgentEventType.TASK_COMPLETED,
                    agent_id="GENERAL_QUESTION_V1",
                )
                await db.commit()

        asyncio.run(seed())
        full_records = _parse_sse(
            first_client.get(f"/api/v1/tasks/{task_id}/stream").text
        )
        assert [record["id"] for record in full_records] == [1, 2]

    second_app = create_app(settings)
    with TestClient(second_app) as second_client:
        reconnect_records = _parse_sse(
            second_client.get(
                f"/api/v1/tasks/{task_id}/stream",
                headers={"Last-Event-ID": "1"},
            ).text
        )

    assert [record["id"] for record in reconnect_records] == [2]
    assert reconnect_records[0]["event"] == "task.completed"


def test_concurrent_event_appends_keep_unique_contiguous_sequences(
    api, app, client
) -> None:
    session = api.create_session()
    task = api.create_task(session["id"])
    api.wait_for_task(task["id"])

    async def append_concurrently() -> list[int]:
        async def append_one(worker_id: int) -> None:
            async with app.state.session_factory() as db:
                await append_task_event(
                    db,
                    task["id"],
                    AgentEventType.AGENT_PROGRESS,
                    data={"worker_id": worker_id},
                )
                await db.commit()

        await asyncio.gather(*(append_one(worker_id) for worker_id in range(8)))
        async with app.state.session_factory() as db:
            events = await TaskRepository(db).list_events(task["id"])
            return [event.sequence for event in events]

    sequences = asyncio.run(append_concurrently())
    assert sequences == list(range(1, len(sequences) + 1))
    assert len(sequences) == len(set(sequences))

    full_records = _parse_sse(client.get(f"/api/v1/tasks/{task['id']}/stream").text)
    full_ids = [record["id"] for record in full_records]
    assert full_ids == sequences

    cutoff = full_ids[-4]
    reconnect_records = _parse_sse(
        client.get(
            f"/api/v1/tasks/{task['id']}/stream",
            headers={"Last-Event-ID": str(cutoff)},
        ).text
    )
    reconnect_ids = [record["id"] for record in reconnect_records]
    assert reconnect_ids == [event_id for event_id in full_ids if event_id > cutoff]
    assert len(reconnect_ids) == len(set(reconnect_ids))


def test_general_runtime_sse_reconnect_preserves_node_order(api, app, client) -> None:
    app.state.task_runner.runtime_lifecycle.enabled = True
    assert app.state.task_runner.general_question_runtime is not None
    app.state.task_runner.general_question_runtime.enabled = True
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        options={"general_question_runtime": {"execute": True}},
        intent="unknown",
    )
    payload.update(
        {
            "scene": "dispatch",
            "course_id": "UNKNOWN",
            "canonical_input": {"text": "Explain what an agent is."},
        }
    )
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    task_id = response.json()["id"]
    assert api.wait_for_task(task_id, timeout=15)["status"] == "completed"

    full_records = _parse_sse(client.get(f"/api/v1/tasks/{task_id}/stream").text)
    all_runtime_records = [
        record
        for record in full_records
        if isinstance(record["data"], dict)
        and record["data"].get("runtime_run_id")
        and record["event"] in {"plan.node_started", "plan.node_completed"}
    ]
    parent_run_id = next(
        record["data"]["runtime_run_id"]
        for record in all_runtime_records
        if record["data"].get("node_id") == "general.observe"
    )
    runtime_records = [
        record
        for record in all_runtime_records
        if record["data"].get("runtime_run_id") == parent_run_id
    ]
    assert any(
        record["data"].get("node_id") == "subagent.execute"
        and record["data"].get("runtime_run_id") != parent_run_id
        for record in all_runtime_records
    )
    assert [
        (record["event"], record["data"]["node_id"])
        for record in runtime_records
    ] == [
        ("plan.node_started", "general.observe"),
        ("plan.node_completed", "general.observe"),
        ("plan.node_started", "general.execute"),
        ("plan.node_completed", "general.execute"),
        ("plan.node_started", "general.verify"),
        ("plan.node_completed", "general.verify"),
    ]

    cutoff = int(runtime_records[1]["id"])
    reconnect_records = _parse_sse(
        client.get(
            f"/api/v1/tasks/{task_id}/stream?after=0",
            headers={"Last-Event-ID": str(cutoff)},
        ).text
    )
    assert [record["id"] for record in reconnect_records] == [
        record["id"] for record in full_records if record["id"] > cutoff
    ]
    assert all(record["id"] > cutoff for record in reconnect_records)


def test_academic_solver_runtime_sse_reconnect_preserves_node_order(
    api, app, client
) -> None:
    app.state.task_runner.runtime_lifecycle.enabled = True
    assert app.state.task_runner.academic_solver_runtime is not None
    app.state.task_runner.academic_solver_runtime.enabled = True
    session = api.create_session()
    payload = api.task_payload(
        session["id"],
        options={"academic_solver_runtime": {"execute": True}},
        intent="solve_problem",
    )
    payload.update(
        {
            "scene": "solving",
            "course_id": "CT",
            "canonical_input": {"text": "Find the equivalent resistance."},
        }
    )
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    task_id = response.json()["id"]
    assert api.wait_for_task(task_id, timeout=15)["status"] == "completed"

    full_records = _parse_sse(client.get(f"/api/v1/tasks/{task_id}/stream").text)
    runtime_records = [
        record
        for record in full_records
        if isinstance(record["data"], dict)
        and record["data"].get("runtime_run_id")
        and record["event"] in {"plan.node_started", "plan.node_completed"}
    ]
    assert [
        (record["event"], record["data"]["node_id"])
        for record in runtime_records
    ] == [
        ("plan.node_started", "solver.observe"),
        ("plan.node_completed", "solver.observe"),
        ("plan.node_started", "solver.retrieve"),
        ("plan.node_completed", "solver.retrieve"),
        ("plan.node_started", "solver.execute"),
        ("plan.node_completed", "solver.execute"),
        ("plan.node_started", "solver.verify"),
        ("plan.node_completed", "solver.verify"),
    ]

    cutoff = int(runtime_records[1]["id"])
    reconnect_records = _parse_sse(
        client.get(
            f"/api/v1/tasks/{task_id}/stream?after=0",
            headers={"Last-Event-ID": str(cutoff)},
        ).text
    )
    assert [record["id"] for record in reconnect_records] == [
        record["id"] for record in full_records if record["id"] > cutoff
    ]
    assert all(record["id"] > cutoff for record in reconnect_records)


def test_plan_proposal_events_are_ordered_and_reconnectable(api, app, client) -> None:
    session = api.create_session()
    task_id = "task-plan-proposal-sse"
    run_id = "run-plan-proposal-sse"

    async def seed_and_apply() -> None:
        async with app.state.session_factory() as db:
            db.add(
                TaskModel(
                    id=task_id,
                    session_id=session["id"],
                    user_id="user-test",
                    course_id="CT",
                    intent="general_qa",
                    agent_id="GENERAL_QUESTION_V1",
                    status=TaskStatus.RUNNING,
                    input_content={"text": "proposal"},
                )
            )
            run = AgentRun(
                run_id=run_id,
                task_id=task_id,
                goal="test plan proposal events",
                plan=AgentRunPlan(
                    plan_id="proposal-sse-plan",
                    version="1",
                    goal="test plan proposal events",
                    nodes=[
                        RuntimeNode(
                            node_id="observe",
                            node_type="control",
                            handler_id="runtime.observe",
                        )
                    ],
                ),
            )
            await db.flush()
            await AgentRunRepository(db).create(
                run,
                agent_id="GENERAL_QUESTION_V1",
                provider="mock",
            )
            await db.commit()

        async with app.state.session_factory() as db:
            proposed = run.plan.model_copy(update={"version": "2"})
            proposal_service = RuntimePlanProposalService(db)
            proposal = await proposal_service.create(
                task_id,
                run_id,
                proposed,
                reason_codes=["sse_reconnect_check"],
                rationale="Verify proposal events are durable.",
            )
            stored = await RuntimePlanProposalRepository(db).get(
                proposal.proposal_id
            )
            assert stored is not None
            await proposal_service.decide(
                task_id,
                proposal.proposal_id,
                approved=True,
                expected_state_version=stored.state_version,
            )
            task = await db.get(TaskModel, task_id)
            assert task is not None
            task.status = TaskStatus.COMPLETED
            await db.commit()

    asyncio.run(seed_and_apply())
    full_records = _parse_sse(client.get(f"/api/v1/tasks/{task_id}/stream").text)
    assert [record["id"] for record in full_records] == [1, 2]
    assert [record["event"] for record in full_records] == [
        "agent.progress",
        "plan.rerouted",
    ]
    cutoff = 1
    reconnect_records = _parse_sse(
        client.get(
            f"/api/v1/tasks/{task_id}/stream",
            headers={"Last-Event-ID": str(cutoff)},
        ).text
    )
    assert [record["id"] for record in reconnect_records] == [2]
