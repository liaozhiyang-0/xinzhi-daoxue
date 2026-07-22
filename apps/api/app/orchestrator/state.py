from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from typing_extensions import TypedDict


class XZDGraphState(TypedDict, total=False):
    """The single resumable state shared by Supervisor and task graphs.

    Only references, summaries, and bounded structured values belong here.
    Raw files, base64 payloads, secrets, full corpora, and hidden reasoning do not.
    """

    schema_version: str
    request_id: str
    session_id: str
    user_id: str | None
    trace_id: str
    thread_id: str
    run_id: str
    message: str
    input_type: str
    file_refs: list[dict[str, Any]]
    task_family: str
    course: str
    intent: str
    problem_type: str
    selected_agent: str
    route_status: str
    risk_level: Literal["low", "medium", "high"]
    execution_path: str
    normalized_input: dict[str, Any]
    structured_problem: dict[str, Any]
    previous_context: dict[str, Any]
    selected_course_pack: str
    selected_capabilities: list[str]
    selected_tools: list[str]
    retrieved_chunks: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    model_results: list[dict[str, Any]]
    solution_plan: dict[str, Any]
    draft_solution: dict[str, Any]
    verification_result: dict[str, Any]
    correction_result: dict[str, Any]
    assumptions: list[str]
    warnings: list[str]
    errors: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    final_answer: str
    structured_result: dict[str, Any]
    confidence: float
    fallback_used: bool
    fallback_target: str | None
    current_stage: str
    trace: list[Any]


def new_graph_state(
    *,
    request_id: str,
    message: str,
    session_id: str = "",
    user_id: str | None = None,
    file_refs: list[dict[str, Any]] | None = None,
) -> XZDGraphState:
    return XZDGraphState(
        schema_version="1.0",
        request_id=request_id,
        session_id=session_id,
        user_id=user_id,
        trace_id=f"trace_{uuid4().hex}",
        thread_id=session_id or f"thread_{uuid4().hex}",
        run_id=f"run_{uuid4().hex}",
        message=message,
        input_type="text",
        file_refs=list(file_refs or []),
        task_family="FALLBACK",
        course="UNKNOWN",
        intent="unknown",
        problem_type="",
        selected_agent="",
        route_status="skipped",
        risk_level="low",
        execution_path="",
        normalized_input={},
        structured_problem={},
        previous_context={},
        selected_course_pack="",
        selected_capabilities=[],
        selected_tools=[],
        retrieved_chunks=[],
        tool_results=[],
        model_results=[],
        solution_plan={},
        draft_solution={},
        verification_result={},
        correction_result={},
        assumptions=[],
        warnings=[],
        errors=[],
        citations=[],
        final_answer="",
        structured_result={},
        confidence=0,
        fallback_used=False,
        fallback_target=None,
        current_stage="created",
        trace=[],
    )
