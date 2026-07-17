from app.agents import AgentRegistry


def test_agent_registry_loads_solver_and_local_learner() -> None:
    registry = AgentRegistry()

    assert registry.get("SOLVER_CT_V1").publication_status == "published"
    learner = registry.get("LEARN_01_KNOWLEDGE_QA_V1")
    assert learner.provider == "local"
    assert learner.mode == "retrieval_only"
    assert len(registry.routing_rules) == 2
