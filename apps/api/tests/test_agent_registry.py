from dataclasses import replace

from app.agents import AgentRegistry
from app.core.config import Settings


def test_agent_registry_loads_cloud_and_local_learning_agents() -> None:
    registry = AgentRegistry()

    assert registry.get("SOLVER_CT_V1").publication_status == "published"
    learner = registry.get("LEARN_01_KNOWLEDGE_QA_V1")
    assert learner.provider == "xingchen"
    assert learner.fallback_agent_id == "LEARN_01_LOCAL_RETRIEVAL_V1"
    local = registry.get("LEARN_01_LOCAL_RETRIEVAL_V1")
    assert local.mode == "retrieval_only"
    assert len(registry.routing_rules) >= 3
    assert {rule.agent_id for rule in registry.routing_rules} >= {
        "ACADEMIC_PROBLEM_SOLVER",
        "LEARN_01_LOCAL_RETRIEVAL_V1",
    }


def test_registry_lifecycle_blocks_runtime_and_unconfigured_route() -> None:
    registry = AgentRegistry()
    settings = Settings(_env_file=None)
    agent_id = "SOLVER_CT_V1"
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


def test_solver_ct_keeps_published_hybrid_unconfigured_route_contract() -> None:
    registry = AgentRegistry()

    assert registry.is_execution_eligible("SOLVER_CT_V1") is True
    assert registry.has_local_execution_contract("SOLVER_CT_V1") is True
    assert registry.allows_unconfigured_route("SOLVER_CT_V1") is True
