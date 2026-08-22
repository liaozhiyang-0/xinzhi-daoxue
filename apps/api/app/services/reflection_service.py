from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol

from app.agents.internal import InternalAgentHub
from app.contracts import AgentRequest, AgentResult, AgentValidationResult
from app.contracts.reflection import (
    CriticResult,
    ReflectionMetrics,
    ReflectionTrace,
    RevisionProposal,
    RevisionRequest,
)
from app.services.reflection_policy import ReflectionPolicy

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WorkerOutput:
    value: CriticResult | RevisionProposal
    latency_ms: int
    tokens: int


@dataclass(frozen=True, slots=True)
class ReflectionOutcome:
    result: AgentResult
    validation: AgentValidationResult


class CriticWorker(Protocol):
    async def run(
        self, payload: dict[str, Any], *, request_id: str, max_tokens: int
    ) -> WorkerOutput: ...


class RevisionWorker(Protocol):
    async def run(
        self, request: RevisionRequest, *, request_id: str, max_tokens: int
    ) -> WorkerOutput: ...


class InternalCriticWorker:
    """Adapter over the existing InternalAgentHub; no public Agent is added."""

    critic_agent_id = "REFLECTION_CRITIC_LOCAL_V1"
    revision_agent_id = "REFLECTION_REVISION_LOCAL_V1"

    def __init__(self, hub: InternalAgentHub) -> None:
        self.hub = hub

    async def run(
        self, payload: dict[str, Any], *, request_id: str, max_tokens: int
    ) -> WorkerOutput:
        started = perf_counter()
        internal = await self.hub.run_text(
            self.critic_agent_id,
            input_text=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            request_id=request_id,
            max_tokens=max_tokens,
        )
        value = CriticResult.model_validate(internal.structured_result)
        return WorkerOutput(
            value=value,
            latency_ms=max(internal.elapsed_ms, int((perf_counter() - started) * 1000)),
            tokens=internal.total_tokens or 0,
        )


    async def revise(
        self, request: RevisionRequest, *, request_id: str, max_tokens: int
    ) -> WorkerOutput:
        started = perf_counter()
        internal = await self.hub.run_text(
            self.revision_agent_id,
            input_text=request.model_dump_json(),
            request_id=request_id,
            max_tokens=max_tokens,
        )
        value = RevisionProposal.model_validate(internal.structured_result)
        return WorkerOutput(
            value=value,
            latency_ms=max(internal.elapsed_ms, int((perf_counter() - started) * 1000)),
            tokens=internal.total_tokens or 0,
        )


class InternalRevisionWorker:
    """Expose the same InternalAgentHub through the revision worker contract."""

    def __init__(self, worker: InternalCriticWorker) -> None:
        self.worker = worker

    async def run(
        self, request: RevisionRequest, *, request_id: str, max_tokens: int
    ) -> WorkerOutput:
        return await self.worker.revise(
            request,
            request_id=request_id,
            max_tokens=max_tokens,
        )


class ReflectionService:
    """Run bounded reflection beside the existing Result Pipeline."""

    _IMMUTABLE_STRUCTURED_KEYS = frozenset(
        {
            "citations",
            "knowledge",
            "evidence_packet",
            "tool_verification",
            "verification",
            "verification_report",
            "quality_gate",
            "validation",
            "evidence_refs",
            "retrieval_trace_id",
        }
    )
    _IMMUTABLE_BUSINESS_KEYS = frozenset(
        {"citations", "evidence_refs", "sources", "knowledge", "tool_outputs"}
    )

    def __init__(
        self,
        policy: ReflectionPolicy,
        *,
        critic: CriticWorker | None = None,
        reviser: RevisionWorker | None = None,
    ) -> None:
        self.policy = policy
        self.critic = critic
        self.reviser = reviser

    async def apply(
        self,
        *,
        agent_id: str,
        request: AgentRequest,
        result: AgentResult,
        validation: AgentValidationResult,
        reverify: Any = None,
    ) -> ReflectionOutcome:
        decision = self.policy.decide(
            agent_id=agent_id,
            request=request,
            result=result,
            validation=validation,
        )
        capability = self.policy.capability_for(agent_id)
        available_refs = self._available_evidence_refs(result)
        trace = ReflectionTrace(
            mode=(
                "bounded_revision"
                if decision.max_revision_count
                else "shadow"
                if decision.action == "critique"
                else "off"
            ),
            capability=capability,
            available_evidence_refs=sorted(available_refs),
            decision=decision,
            deterministic_status=self._deterministic_status(result, validation),
        )

        if decision.action != "critique":
            trace.final_status = decision.action
            return ReflectionOutcome(self._attach(result, trace), validation)
        if self.critic is None:
            trace.metrics = ReflectionMetrics(
                critic_status="unavailable",
                error="critic_worker_unavailable",
            )
            trace.final_status = "critic_unavailable"
            return ReflectionOutcome(self._attach(result, trace), validation)

        metrics = ReflectionMetrics(critic_attempted=True)
        try:
            worker_output = await self.critic.run(
                self._critic_payload(request, agent_id, result, available_refs),
                request_id=self._request_id(request),
                max_tokens=decision.budget_tokens,
            )
            if not isinstance(worker_output.value, CriticResult):
                raise TypeError("critic worker returned a revision proposal")
            critic = self._ground_critic(worker_output.value, available_refs)
            trace.critic = critic
            metrics = metrics.model_copy(
                update={
                    "critic_status": critic.status,
                    "critic_latency_ms": worker_output.latency_ms,
                    "critic_tokens": worker_output.tokens,
                    "unsupported_critique_count": len(
                        [
                            ref
                            for ref in worker_output.value.evidence_refs
                            if ref not in available_refs
                        ]
                    ),
                    "verifier_critic_disagreement": self._disagreement(
                        result, critic
                    ),
                }
            )
        except Exception as exc:  # Critic failure must not affect the task result.
            logger.warning(
                "reflection_critic_failed task_id=%s agent_id=%s",
                request.task_id,
                agent_id,
                exc_info=True,
            )
            trace.metrics = metrics.model_copy(
                update={"critic_status": "failed", "error": type(exc).__name__}
            )
            trace.final_status = "critic_failed"
            return ReflectionOutcome(self._attach(result, trace), validation)

        trace.metrics = metrics
        if (
            decision.max_revision_count != 1
            or trace.critic is None
            or trace.critic.status != "revise"
            or not trace.critic.revision_allowed
            or self.reviser is None
            or reverify is None
        ):
            trace.final_status = "shadow_observed"
            return ReflectionOutcome(self._attach(result, trace), validation)

        revision_request = RevisionRequest(
            original_result=self._revision_input(result),
            critic_result=trace.critic,
            allowed_changes=trace.critic.required_changes,
            evidence_refs=trace.critic.evidence_refs,
            revision_count=0,
            revision_budget=1,
        )
        try:
            revision_output = await self.reviser.run(
                revision_request,
                request_id=self._request_id(request),
                max_tokens=decision.budget_tokens,
            )
            proposal = revision_output.value
            if not isinstance(proposal, RevisionProposal):
                raise TypeError("revision worker returned a critic result")
            trace.revision = proposal
            metrics = metrics.model_copy(
                update={
                    "revision_attempted": True,
                    "revision_status": proposal.status,
                    "revision_latency_ms": revision_output.latency_ms,
                    "revision_tokens": revision_output.tokens,
                    "revision_count": proposal.revision_count,
                }
            )
            if not self._revision_is_grounded(proposal, available_refs):
                trace.metrics = metrics.model_copy(
                    update={
                        "revision_status": "failed",
                        "error": "revision_evidence_not_grounded",
                    }
                )
                trace.final_status = "revision_failed_closed"
                return ReflectionOutcome(self._attach(result, trace), validation)
            revised = self._apply_revision(result, proposal)
            if revised is result:
                trace.metrics = metrics.model_copy(
                    update={"revision_status": "no_change"}
                )
                trace.final_status = "revision_no_change"
                return ReflectionOutcome(self._attach(result, trace), validation)
            reverified = reverify(revised)
            trace.metrics = metrics
            final_result = getattr(reverified, "result", revised)
            final_validation = getattr(reverified, "validation", None)
            trace.final_status = (
                "revision_verified"
                if final_validation is not None and final_validation.response_usable
                else "revision_failed_closed"
            )
            return ReflectionOutcome(
                self._attach(final_result, trace),
                final_validation or validation,
            )
        except Exception as exc:
            logger.warning(
                "reflection_revision_failed task_id=%s agent_id=%s",
                request.task_id,
                agent_id,
                exc_info=True,
            )
            trace.metrics = metrics.model_copy(
                update={
                    "revision_attempted": True,
                    "revision_status": "failed",
                    "error": type(exc).__name__,
                }
            )
            trace.final_status = "revision_failed_closed"
            return ReflectionOutcome(self._attach(result, trace), validation)

    @staticmethod
    def _request_id(request: AgentRequest) -> str:
        return str(request.options.get("request_id", request.task_id))

    @classmethod
    def _critic_payload(
        cls,
        request: AgentRequest,
        agent_id: str,
        result: AgentResult,
        available_refs: set[str],
    ) -> dict[str, Any]:
        structured = result.structured_result
        return {
            "goal": request.input_text(),
            "agent_id": agent_id,
            "course_id": request.course_id,
            "draft": {
                "answer": result.answer,
                "business_data": result.business_data,
                "structured_result": structured,
                "warnings": result.warnings,
                "remaining_risks": result.remaining_risks,
            },
            "evidence_refs": sorted(available_refs),
            "tool_observations": structured.get("tool_verification", []),
            "deterministic_verification": structured.get("verification_report"),
            "instruction": (
                "只能引用输入中的 evidence_refs；无法由证据支持的内容必须标记为"
                " unsupported_claims。"
            ),
        }

    @classmethod
    def _revision_input(cls, result: AgentResult) -> dict[str, Any]:
        return {
            "answer": result.answer,
            "business_data": result.business_data,
            "structured_result": result.structured_result,
            "citations": result.citations,
            "remaining_risks": result.remaining_risks,
        }

    @classmethod
    def _apply_revision(
        cls, result: AgentResult, proposal: RevisionProposal
    ) -> AgentResult:
        if proposal.status != "revised":
            return result
        answer = proposal.revised_answer.strip() or result.answer
        business_data = dict(result.business_data)
        business_data.update(
            {
                key: value
                for key, value in proposal.revised_business_data.items()
                if key not in cls._IMMUTABLE_BUSINESS_KEYS
            }
        )
        structured = dict(result.structured_result)
        structured.update(
            {
                key: value
                for key, value in proposal.revised_structured_result.items()
                if key not in cls._IMMUTABLE_STRUCTURED_KEYS
            }
        )
        if (
            answer == result.answer
            and business_data == result.business_data
            and structured == result.structured_result
        ):
            return result
        return result.model_copy(
            update={
                "answer": answer,
                "business_data": business_data,
                "structured_result": structured,
            }
        )

    @staticmethod
    def _ground_critic(critic: CriticResult, available_refs: set[str]) -> CriticResult:
        invalid = [ref for ref in critic.evidence_refs if ref not in available_refs]
        if not invalid:
            return critic
        return critic.model_copy(
            update={
                "status": "needs_review",
                "evidence_refs": [
                    ref for ref in critic.evidence_refs if ref in available_refs
                ],
                "unsupported_claims": [*critic.unsupported_claims, *invalid],
                "required_changes": [],
                "revision_allowed": False,
            }
        )

    @classmethod
    def _revision_is_grounded(
        cls, proposal: RevisionProposal, available_refs: set[str]
    ) -> bool:
        return all(ref in available_refs for ref in proposal.evidence_refs)

    @staticmethod
    def _deterministic_status(
        result: AgentResult, validation: AgentValidationResult
    ) -> str:
        quality = result.structured_result.get("quality_gate")
        if isinstance(quality, dict) and quality.get("status"):
            return str(quality["status"])
        return "pass" if validation.response_usable else "fail"

    @staticmethod
    def _disagreement(result: AgentResult, critic: CriticResult) -> str:
        quality = result.structured_result.get("quality_gate")
        deterministic_failed = (
            isinstance(quality, dict) and quality.get("status") == "fail"
        )
        if deterministic_failed and critic.status == "pass":
            return "verifier_fail_critic_pass"
        if not deterministic_failed and critic.status in {"revise", "fail"}:
            return "verifier_pass_critic_nonpass"
        return "none"

    @classmethod
    def _available_evidence_refs(cls, result: AgentResult) -> set[str]:
        refs = {str(item).strip() for item in result.citations if str(item).strip()}
        structured = result.structured_result
        for key in ("evidence_refs", "verified_evidence_ids", "tool_output_refs"):
            values = structured.get(key, [])
            if isinstance(values, list):
                refs.update(str(item).strip() for item in values if str(item).strip())
        knowledge = structured.get("knowledge")
        if isinstance(knowledge, dict):
            hits = knowledge.get("hits", [])
            if isinstance(hits, list):
                for hit in hits:
                    if isinstance(hit, dict):
                        for key in ("evidence_id", "source_ref"):
                            value = str(hit.get(key, "")).strip()
                            if value:
                                refs.add(value)
        for artifact in result.artifacts:
            refs.update(
                str(item).strip()
                for item in artifact.source_refs
                if str(item).strip()
            )
        return refs

    @staticmethod
    def _attach(result: AgentResult, trace: ReflectionTrace) -> AgentResult:
        structured = dict(result.structured_result)
        structured["reflection"] = trace.model_dump(mode="json")
        return result.model_copy(update={"structured_result": structured})
