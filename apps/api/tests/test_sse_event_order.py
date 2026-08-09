from __future__ import annotations

import asyncio
import json

from app.contracts import AgentEventType
from app.models import TaskModel, TaskStatus
from app.repositories import (
    AgentRunRepository,
    RuntimePlanProposalRepository,
    TaskRepository,
)
from app.runtime import AgentRun, AgentRunPlan, RuntimeNode
from app.services.event_service import append_task_event
from app.services.runtime_plan_proposals import RuntimePlanProposalService


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
