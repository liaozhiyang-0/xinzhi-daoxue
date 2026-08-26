from __future__ import annotations

from app.circuit import CircuitIR
from app.contracts import AgentRequest, AttachmentRef, Intent
from app.contracts.solver import AcademicProblem
from app.observability.architecture_telemetry import architecture_telemetry
from app.services.academic_solver_service import AcademicProblemSolverService
from app.services.circuit_visualization import decide_circuit_visualization
from app.services.multimodal_policy import (
    enrich_multimodal_request,
    get_multimodal_capability_hint,
    requires_circuit_ir,
)
from app.services.solver_boundary_policy import SolverBoundaryPolicy
from app.services.unified_request_preparation import (
    UnifiedRequestPreparationService,
)


def _image(file_id: str, filename: str | None = None) -> AttachmentRef:
    return AttachmentRef(
        file_id=file_id,
        filename=filename or f"{file_id}.png",
        content_type="image/png",
        size_bytes=10,
        storage_key=f"local:{file_id}",
    )


def _request(
    text: str,
    *,
    attachments: list[AttachmentRef] | None = None,
    options: dict[str, object] | None = None,
) -> AgentRequest:
    return AgentRequest(
        session_id="session-multimodal",
        user_id="user-multimodal",
        course_id="CT",
        intent=Intent.SOLVE_PROBLEM,
        canonical_input={"text": text},
        attachments=attachments or [_image("image-1")],
        options=options or {},
    )


def test_mixed_image_roles_preserve_explicit_primary_and_secondary_roles() -> None:
    request = _request(
        "第一张是题目截图，第二张是我的答案，请检查。",
        attachments=[_image("image-1"), _image("image-2")],
    )

    enriched = enrich_multimodal_request(request)

    assert enriched.attachments[0].primary_role == "PROBLEM_STATEMENT"
    assert enriched.attachments[0].secondary_roles == ["TEXT_SCREENSHOT"]
    assert enriched.attachments[1].primary_role == "STUDENT_SOLUTION"
    assert all(item.role_source == "explicit_user" for item in enriched.attachments)
    assert get_multimodal_capability_hint(enriched).intent == "CHECK_MY_WORK"

    explicit = _request(
        "帮我解题。",
        attachments=[_image("image-1"), _image("image-2")],
        options={
            "attachment_roles": {
                "2": {
                    "primary_role": "STUDENT_SOLUTION",
                    "secondary_roles": ["TEXT_SCREENSHOT"],
                }
            }
        },
    )
    explicit_enriched = enrich_multimodal_request(explicit)
    assert explicit_enriched.attachments[1].primary_role == "STUDENT_SOLUTION"
    assert explicit_enriched.attachments[1].secondary_roles == ["TEXT_SCREENSHOT"]


def test_goal_contract_contains_multimodal_hint_without_agent_route() -> None:
    request = _request("请分析这张表格图片。", attachments=[_image("table")])

    prepared = UnifiedRequestPreparationService().attach(request)
    goal = prepared.options["_goal_contract"]

    assert goal["multimodal_intent"] == "TABLE_ANALYSIS"
    assert goal["multimodal_capability_hint"]["possible_capabilities"]
    assert "agent_id" not in goal
    assert prepared.attachments[0].primary_role == "TABLE"


def test_ordinary_image_solve_skips_circuit_ir_even_when_ir_is_available() -> None:
    request = _request(
        "请解答这道题并参考图片。",
        options={"circuit_ir": CircuitIR().model_dump(mode="json")},
    )

    hint = get_multimodal_capability_hint(enrich_multimodal_request(request))
    decision = decide_circuit_visualization(
        request, feature_mode="controlled", course_id="CT"
    )

    assert hint.intent == "SOLVE_PROBLEM"
    assert hint.circuit_ir_requested is False
    assert decision.decision == "SKIP"
    assert decision.blocked is False
    assert decision.circuit_ir_requested is False


def test_topology_and_render_requests_are_the_only_specialized_triggers() -> None:
    topology = _request("请分析图片中的电路节点和支路。")
    render = _request("请生成这个电路的电路图。")
    pattern = _request(
        "按计划完成求解。", options={"plan_pattern": "SOLVE_VERIFY_RENDER"}
    )

    assert requires_circuit_ir(topology) is True
    assert get_multimodal_capability_hint(render).intent == "CIRCUIT_RENDER"
    assert requires_circuit_ir(render) is True
    assert requires_circuit_ir(pattern) is True


def test_unknown_image_role_defaults_to_general_vision_and_does_not_block() -> None:
    request = _request("帮我看看这张图片。", attachments=[_image("unknown")])
    enriched = enrich_multimodal_request(request)
    hint = get_multimodal_capability_hint(enriched)

    problem = AcademicProblem(
        course="CT",
        problem_text=request.input_text(),
        figures_given=[{"file_id": "unknown"}],
    )
    merged, metadata = AcademicProblemSolverService._merge_visual_extraction(
        problem,
        "视觉模型识别到一张清晰的实验装置图片。",
        require_specialized_topology=False,
    )

    assert enriched.attachments[0].primary_role == "UNKNOWN"
    assert hint.intent == "EXPLAIN_IMAGE"
    assert "general_vision" in hint.possible_capabilities
    assert metadata["circuit_ir_requested"] is False
    assert merged.can_continue is True
    assert not SolverBoundaryPolicy().evaluate(
        merged, check_visual_topology=False
    ).intercepted


def test_multimodal_role_metrics_are_bounded_and_named() -> None:
    architecture_telemetry.reset()
    try:
        enrich_multimodal_request(
            _request(
                "第一张是表格，第二张无法判断。",
                attachments=[_image("table"), _image("unknown")],
            )
        )
        snapshot = architecture_telemetry.snapshot()
    finally:
        architecture_telemetry.reset()

    assert snapshot["multimodal_task_count"] == 1
    assert snapshot["image_role_count_table"] == 1
    assert snapshot["image_role_count_unknown"] == 1
    assert snapshot["unknown_image_role_count"] == 1
