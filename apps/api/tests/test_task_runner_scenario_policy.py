from app.contracts.agent import AgentRequest
from app.services.task_runner import TaskRunner


def test_task_runner_only_accepts_bound_scenario_evidence_policy() -> None:
    policy = {"citation_required": True, "manual_review_required": True}
    unbound = AgentRequest(
        session_id="session-test",
        user_id="user-test",
        options={"scenario_evidence_policy": policy},
    )
    bound = AgentRequest(
        session_id="session-test",
        user_id="user-test",
        options={
            "scenario_evidence_policy": policy,
            "_scenario_catalog_bound": True,
        },
    )

    assert TaskRunner._scenario_evidence_policy(unbound) is None
    assert TaskRunner._scenario_evidence_policy(bound) == policy
    assert TaskRunner._scenario_citations_required(unbound) is False
    assert TaskRunner._scenario_citations_required(bound) is True
