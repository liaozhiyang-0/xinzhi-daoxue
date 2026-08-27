from dataclasses import replace

from app.agents import AgentRegistry
from app.core.config import Settings


def test_agent_registry_loads_local_learning_agents() -> None:
    registry = AgentRegistry()

    academic = registry.get("ACADEMIC_PROBLEM_SOLVER")
    assert academic.publication_status == "local"
    assert {"solve_problem", "check_user_solution", "verify_answer"}.issubset(
        academic.capabilities.intents
    )
    learner = registry.get("LEARN_01_KNOWLEDGE_QA_V1")
    assert learner.provider == "local"
    assert learner.fallback_agent_id == "LEARN_01_LOCAL_RETRIEVAL_V1"
    local = registry.get("LEARN_01_LOCAL_RETRIEVAL_V1")
    assert local.mode == "retrieval_only"
    assert len(registry.routing_rules) >= 3
    assert {rule.agent_id for rule in registry.routing_rules} >= {
        "ACADEMIC_PROBLEM_SOLVER",
        "LEARN_01_KNOWLEDGE_QA_V1",
    }


def test_registry_lifecycle_blocks_runtime_and_unconfigured_route() -> None:
    registry = AgentRegistry()
    settings = Settings(_env_file=None)
    agent_id = "ACADEMIC_PROBLEM_SOLVER"
    original = registry.get(agent_id)

    registry._agents[agent_id] = replace(original, enabled=False)
    assert registry.is_execution_eligible(agent_id) is False
    assert registry.is_runtime_available(agent_id, settings) is False
    assert registry.allows_unconfigured_route(agent_id) is False

    registry._agents[agent_id] = replace(
        original, publication_status="planned", enabled=True
    )
    assert registry.is_execution_eligible(agent_id) is False
    assert registry.is_runtime_available(agent_id, settings) is False
    assert registry.allows_unconfigured_route(agent_id) is False

    registry._agents[agent_id] = replace(original, route_when_unconfigured=True)
    assert registry.allows_unconfigured_route(agent_id) is True
    registry._agents[agent_id] = replace(original, local_handler="")
    assert registry.allows_unconfigured_route(agent_id) is False


def test_disabled_and_unpublished_agents_are_not_configured_or_runtime_available(
) -> None:
    registry = AgentRegistry()
    settings = Settings(_env_file=None)
    original = registry.get("GENERAL_QUESTION_V1")

    registry._agents[original.agent_id] = replace(
        original, enabled=False, publication_status="planned"
    )

    assert registry.is_execution_eligible(original.agent_id) is False
    assert registry.is_configured(original.agent_id, settings) is False
    assert registry.is_runtime_available(original.agent_id, settings) is False
    assert registry.allows_unconfigured_route(original.agent_id) is False


def test_academic_solver_keeps_local_route_contract() -> None:
    registry = AgentRegistry()

    assert registry.is_execution_eligible("ACADEMIC_PROBLEM_SOLVER") is True
    assert registry.has_local_execution_contract("ACADEMIC_PROBLEM_SOLVER") is True
    assert registry.allows_unconfigured_route("ACADEMIC_PROBLEM_SOLVER") is True


def test_teaching_retrieval_keeps_unclassified_textbook_chunks_available() -> None:
    lesson = AgentRegistry().get("TEACH_01_LESSON_PREP_V1")

    assert {"mixed", "unknown"}.issubset(
        lesson.retrieval_policy.allowed_content_types
    )
