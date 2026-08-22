from __future__ import annotations

import pytest
from app.capabilities import default_capability_registry
from app.contracts.planner import (
    CanonicalGoal,
    CanonicalPlan,
    CanonicalPlanNode,
    PlannerSkillSelection,
)
from app.courses import default_course_registry
from app.runtime import (
    AgentRun,
    PlanExecutor,
    RuntimeHandlerDescriptor,
    RuntimeHandlerRegistry,
    RuntimeNodeStatus,
    RuntimeObservation,
)
from app.services.canonical_plan_adapter import CanonicalPlanAdapter
from app.services.skill_binding import SkillBindingService
from app.services.skill_registry import SkillRegistry
from app.tools.registry import default_tool_registry


def _registry() -> SkillRegistry:
    return SkillRegistry(
        default_course_registry(),
        default_capability_registry(),
    )


def _plan(skill_id: str = "CT.KCL") -> CanonicalPlan:
    return CanonicalPlan(
        plan_id=f"canonical:{skill_id.casefold()}",
        goal=CanonicalGoal(
            objective="用 KCL 建立节点方程",
            course="CT",
            intent="solve_problem",
        ),
        nodes=[
            CanonicalPlanNode(
                node_id="skill.execute",
                node_type="skill",
                target_id=skill_id,
            )
        ],
        capabilities=["equation_system"],
        selected_skills=[skill_id],
        skill_selection=[
            PlannerSkillSelection(
                skill_id=skill_id,
                version="1.0",
                status="selected",
            )
        ],
    )


def test_approved_skill_binds_to_existing_tool_and_runtime_plan() -> None:
    handlers = RuntimeHandlerRegistry()
    from app.runtime.adapters import register_tool_handlers

    register_tool_handlers(handlers, default_tool_registry())
    bound = SkillBindingService(_registry(), handlers).bind_plan(_plan())

    assert len(bound.skill_bindings) == 1
    binding = bound.skill_bindings[0]
    assert binding.skill_id == "CT.KCL"
    assert binding.handler_id == "tool.linear_equation_solver"
    assert binding.operation == "linear_equation_solver.execute"

    runtime_plan = CanonicalPlanAdapter.to_runtime_plan(bound)
    node = runtime_plan.nodes[0]
    assert node.handler_id == "tool.linear_equation_solver"
    assert node.node_type == "tool"
    assert node.skill_id == "CT.KCL"
    assert node.skill_binding_id == binding.binding_id
    restored = CanonicalPlanAdapter.from_agent_run_plan(runtime_plan)
    assert restored.skill_bindings[0].binding_id == binding.binding_id


def test_same_registered_skill_is_reusable_across_two_plan_contexts() -> None:
    handlers = RuntimeHandlerRegistry()
    from app.runtime.adapters import register_tool_handlers

    register_tool_handlers(handlers, default_tool_registry())
    service = SkillBindingService(_registry(), handlers)

    first = service.bind_plan(_plan())
    second = service.bind_plan(
        _plan().model_copy(
            update={
                "plan_id": "canonical:ct-kcl-follow-up",
                "goal": CanonicalGoal(
                    objective="复核 KCL 符号方向",
                    course="CT",
                    intent="follow_up_question",
                ),
            }
        )
    )

    assert first.skill_bindings[0].binding_id == second.skill_bindings[0].binding_id
    assert first.skill_bindings[0].handler_id == second.skill_bindings[0].handler_id


def test_binding_fails_closed_for_unknown_or_missing_prerequisite() -> None:
    handlers = RuntimeHandlerRegistry()
    from app.runtime.adapters import register_tool_handlers

    register_tool_handlers(handlers, default_tool_registry())
    service = SkillBindingService(_registry(), handlers)

    unknown = service.resolve_plan(_plan("CT.UNKNOWN"))
    assert unknown.status == "rejected"
    assert unknown.rejected[0].reason_codes == ["unregistered_skill"]

    missing = service.resolve_plan(_plan("CT.NODAL"))
    assert missing.status == "rejected"
    assert "prerequisite_missing" in missing.rejected[0].reason_codes


@pytest.mark.asyncio
async def test_runtime_executes_binding_through_existing_plan_executor() -> None:
    handlers = RuntimeHandlerRegistry()
    handlers.register(
        RuntimeHandlerDescriptor(
            handler_id="tool.linear_equation_solver",
            kind="tool",
            max_timeout_ms=30_000,
        ),
        lambda run, node: RuntimeObservation(node_id=node.node_id),
    )
    bound = SkillBindingService(_registry(), handlers).bind_plan(_plan())
    runtime_plan = CanonicalPlanAdapter.to_runtime_plan(bound)
    run = AgentRun(
        run_id="run-skill-binding",
        task_id="task-skill-binding",
        goal=runtime_plan.goal,
        plan=runtime_plan,
    )

    completed = await PlanExecutor(handlers).execute(run)

    assert completed.nodes["skill.execute"].status == RuntimeNodeStatus.SUCCEEDED
    assert completed.nodes["skill.execute"].observation is not None
    assert completed.nodes["skill.execute"].observation.skill_id == "CT.KCL"
    assert completed.nodes["skill.execute"].skill_binding_id
