from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.agents.registry import AgentRegistry
from app.contracts import AgentRequest, AgentResult, AgentValidationResult, RunMetrics
from app.contracts.reflection import (
    CriticResult,
    ReflectionTrace,
    RevisionProposal,
)
from app.services.reflection_policy import ReflectionPolicy, ReflectionPolicyConfig
from app.services.reflection_service import ReflectionService, WorkerOutput


def _request(**options: Any) -> AgentRequest:
    return AgentRequest(
        session_id="session-reflection",
        user_id="user-reflection",
        course_id="CT",
        canonical_input={"text": "请检查这个复杂电路推导"},
        options=options,
    )


def _result(**kwargs: Any) -> AgentResult:
    return AgentResult(
        agent_id="ACADEMIC_PROBLEM_SOLVER",
        provider="local_agent",
        answer="原始答案",
        structured_result={
            "execution_path": "HIGH_RISK",
            **kwargs.pop("structured", {}),
        },
        metrics=RunMetrics(complexity="high_risk"),
        **kwargs,
    )


def _validation(usable: bool = True) -> AgentValidationResult:
    return AgentValidationResult(
        validation_status="passed" if usable else "failed",
        response_usable=usable,
        result_status="accepted" if usable else "failed",
    )


def _critic(
    *,
    status: str = "revise",
    evidence_refs: list[str] | None = None,
    revision_allowed: bool = True,
) -> CriticResult:
    return CriticResult(
        status=status,  # type: ignore[arg-type]
        issue_types=["reasoning"],
        severity="medium",
        issue_summary="推导中间步骤需要补充",
        evidence_refs=evidence_refs or ["E1"],
        required_changes=["answer"],
        confidence=0.9,
        critic_version="critic-test-v1",
        revision_allowed=revision_allowed,
    )


class FakeCritic:
    def __init__(self, value: CriticResult | Exception) -> None:
        self.value = value
        self.calls = 0

    async def run(
        self, payload: dict[str, Any], *, request_id: str, max_tokens: int
    ) -> WorkerOutput:
        del payload, request_id, max_tokens
        self.calls += 1
        if isinstance(self.value, Exception):
            raise self.value
        return WorkerOutput(value=self.value, latency_ms=7, tokens=42)


class FakeRevision:
    def __init__(self, value: RevisionProposal) -> None:
        self.value = value
        self.calls = 0

    async def run(
        self, request: Any, *, request_id: str, max_tokens: int
    ) -> WorkerOutput:
        del request, request_id, max_tokens
        self.calls += 1
        return WorkerOutput(value=self.value, latency_ms=9, tokens=55)


def _service(
    critic: FakeCritic | None = None,
    reviser: FakeRevision | None = None,
    *,
    revision: bool = False,
) -> ReflectionService:
    return ReflectionService(
        ReflectionPolicy(
            ReflectionPolicyConfig(
                shadow_enabled=True,
                revision_enabled=revision,
                critic_budget_tokens=128,
            )
        ),
        critic=critic,
        reviser=reviser,
    )


def test_critic_is_internal_and_does_not_expand_public_agents() -> None:
    public_ids = {item.agent_id for item in AgentRegistry().list_agents()}
    assert "REFLECTION_CRITIC_LOCAL_V1" not in public_ids
    assert "REFLECTION_REVISION_LOCAL_V1" not in public_ids


def test_policy_is_default_off_and_skips_low_risk() -> None:
    result = _result(structured={"execution_path": "FAST"})
    result.metrics.complexity = "simple"
    disabled = ReflectionPolicy().decide(
        agent_id=result.agent_id,
        request=_request(),
        result=result,
        validation=_validation(),
    )
    assert disabled.action == "skip"
    assert "reflection_disabled" in disabled.reason_codes

    enabled = ReflectionPolicy(ReflectionPolicyConfig(shadow_enabled=True)).decide(
        agent_id=result.agent_id,
        request=_request(),
        result=result,
        validation=_validation(),
    )
    assert enabled.action == "skip"
    assert "low_risk_no_trigger" in enabled.reason_codes


def test_policy_triggers_academic_knowledge_and_research_cases() -> None:
    solver = ReflectionPolicy(ReflectionPolicyConfig(shadow_enabled=True)).decide(
        agent_id="ACADEMIC_PROBLEM_SOLVER",
        request=_request(),
        result=_result(),
        validation=_validation(),
    )
    assert solver.action == "critique"
    assert "high_risk_solver" in solver.reason_codes

    knowledge = _result()
    knowledge.agent_id = "LEARN_01_KNOWLEDGE_QA_V1"
    knowledge.evidence_status = "insufficient"
    knowledge.structured_result = {"knowledge": {"hits": []}}
    decision = ReflectionPolicy(ReflectionPolicyConfig(shadow_enabled=True)).decide(
        agent_id=knowledge.agent_id,
        request=_request(),
        result=knowledge,
        validation=_validation(),
    )
    assert decision.action == "critique"
    assert "evidence_quality_warning" in decision.reason_codes

    research = _result()
    research.agent_id = "RESEARCH_02_ACADEMIC_WRITING_V1"
    research.structured_result = {"unsupported_claims": ["C1"]}
    decision = ReflectionPolicy(ReflectionPolicyConfig(shadow_enabled=True)).decide(
        agent_id=research.agent_id,
        request=_request(),
        result=research,
        validation=_validation(),
    )
    assert decision.action == "critique"
    assert "research_evidence_conflict" in decision.reason_codes


def test_shadow_critic_is_observable_and_does_not_change_answer() -> None:
    critic = FakeCritic(_critic())
    result = _result(structured={"evidence_refs": ["E1"]})
    outcome = asyncio_run(
        _service(critic).apply(
            agent_id=result.agent_id,
            request=_request(request_id="reflection-shadow"),
            result=result,
            validation=_validation(),
        )
    )
    assert outcome.result.answer == "原始答案"
    trace = ReflectionTrace.model_validate(
        outcome.result.structured_result["reflection"]
    )
    assert trace.final_status == "shadow_observed"
    assert trace.critic and trace.critic.status == "revise"
    assert trace.metrics.critic_tokens == 42
    assert critic.calls == 1


def asyncio_run(awaitable: Any) -> Any:
    """Keep these unit tests independent of the application's event loop fixtures."""
    import asyncio

    return asyncio.run(awaitable)


def test_invalid_critic_evidence_is_fail_closed_without_revision() -> None:
    critic = FakeCritic(_critic(evidence_refs=["not-in-packet"]))
    result = _result(structured={"evidence_refs": ["E1"]})
    outcome = asyncio_run(
        _service(critic).apply(
            agent_id=result.agent_id,
            request=_request(),
            result=result,
            validation=_validation(),
        )
    )
    trace = ReflectionTrace.model_validate(
        outcome.result.structured_result["reflection"]
    )
    assert trace.critic and trace.critic.status == "needs_review"
    assert trace.critic.revision_allowed is False
    assert trace.metrics.unsupported_critique_count == 1
    assert outcome.result.answer == result.answer


def test_critic_failure_keeps_existing_result_usable() -> None:
    result = _result()
    outcome = asyncio_run(
        _service(FakeCritic(RuntimeError("provider timeout"))).apply(
            agent_id=result.agent_id,
            request=_request(),
            result=result,
            validation=_validation(),
        )
    )
    trace = ReflectionTrace.model_validate(
        outcome.result.structured_result["reflection"]
    )
    assert trace.final_status == "critic_failed"
    assert outcome.validation.response_usable is True
    assert outcome.result.answer == result.answer


def test_revision_is_limited_to_one_change_and_reverified() -> None:
    critic = FakeCritic(_critic())
    revision = FakeRevision(
        RevisionProposal(
            status="revised",
            revised_answer="修订后的答案",
            changed_fields=["answer"],
            change_summary="补充确定性证据支持的中间步骤",
            evidence_refs=["E1"],
            revision_count=1,
        )
    )
    result = _result(
        structured={
            "evidence_refs": ["E1"],
            "tool_verification": [{"id": "T1"}],
        }
    )
    calls = 0

    def reverify(revised: AgentResult) -> Any:
        nonlocal calls
        calls += 1
        return SimpleNamespace(result=revised, validation=_validation())

    outcome = asyncio_run(
        _service(critic, revision, revision=True).apply(
            agent_id=result.agent_id,
            request=_request(),
            result=result,
            validation=_validation(),
            reverify=reverify,
        )
    )
    trace = ReflectionTrace.model_validate(
        outcome.result.structured_result["reflection"]
    )
    assert outcome.result.answer == "修订后的答案"
    assert outcome.result.structured_result["tool_verification"] == [{"id": "T1"}]
    assert trace.final_status == "revision_verified"
    assert trace.metrics.revision_count == 1
    assert calls == 1
    assert revision.calls == 1
