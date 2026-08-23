from app.contracts import AgentRequest, AttachmentRef, Intent, Scene, UserRole
from app.services.unified_request_preparation import (
    UnifiedRequestPreparationService,
)


def test_goal_contract_is_route_free_and_captures_input_constraints() -> None:
    request = AgentRequest(
        task_id="task-goal-contract",
        session_id="session-1",
        user_id="user-1",
        user_role=UserRole.TEACHER,
        scene=Scene.TEACHING,
        course_id="AE",
        intent=Intent.LESSON_PREP,
        scenario_id="faculty_course_copilot_v1",
        canonical_input={"text": "设计一节反馈放大器课程"},
        attachments=[
            AttachmentRef(
                file_id="file-1",
                filename="课程图.png",
                content_type="image/png",
                size_bytes=10,
                storage_key="uploads/file-1",
            )
        ],
        options={
            "desired_output": ["learning_objectives"],
            "evidence_requirements": ["course_materials"],
            "risk_level": "medium",
        },
    )

    goal = UnifiedRequestPreparationService().build_goal(request)

    assert goal.goal_id == request.task_id
    assert goal.normalized_goal == request.input_text()
    assert goal.input_modalities == ["text", "image"]
    assert goal.desired_output == ["learning_objectives"]
    assert goal.evidence_requirements == ["course_materials"]
    assert "agent_id" not in goal.model_dump()


def test_attach_goal_contract_is_deterministic_for_same_semantics() -> None:
    service = UnifiedRequestPreparationService()
    request = AgentRequest(
        task_id="task-goal-contract",
        session_id="session-1",
        user_id="user-1",
        canonical_input={"text": "检查节点电压法的首错"},
        options={"task_family_hint": "assessment"},
    )

    first = service.attach(request).options["_goal_contract"]
    second = service.attach(request).options["_goal_contract"]

    assert first == second
