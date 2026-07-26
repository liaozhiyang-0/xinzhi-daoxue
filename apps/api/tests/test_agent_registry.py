from app.agents import AgentRegistry


def test_agent_registry_loads_cloud_and_local_learning_agents() -> None:
    registry = AgentRegistry()

    assert registry.get("SOLVER_CT_V1").publication_status == "published"
    learner = registry.get("LEARN_01_KNOWLEDGE_QA_V1")
    assert learner.provider == "xingchen"
    assert learner.fallback_agent_id == "LEARN_01_LOCAL_RETRIEVAL_V1"
    local = registry.get("LEARN_01_LOCAL_RETRIEVAL_V1")
    assert local.mode == "retrieval_only"
    assert len(registry.routing_rules) == 3
