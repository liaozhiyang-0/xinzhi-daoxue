from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.contracts import AgentRequest, AgentResult, AgentValidationResult
from app.contracts.reflection import ReflectionDecision

DEFAULT_CAPABILITIES = frozenset(
    {"academic_solver", "knowledge", "research", "teaching"}
)


@dataclass(frozen=True, slots=True)
class ReflectionPolicyConfig:
    """Runtime-safe switches for Reflection.

    Shadow and revision are deliberately opt-in.  A caller may narrow the
    allowlist, but cannot raise the one-revision ceiling.
    """

    shadow_enabled: bool = False
    revision_enabled: bool = False
    allowed_agent_ids: frozenset[str] = field(default_factory=frozenset)
    max_revision_count: int = 1
    critic_budget_tokens: int = 512
    critic_budget_ms: int = 3_000

    def __post_init__(self) -> None:
        if self.max_revision_count not in {0, 1}:
            raise ValueError("Reflection revision count must be 0 or 1")


class ReflectionPolicy:
    """Provider-free trigger policy; it does not choose agents or tools."""

    def __init__(self, config: ReflectionPolicyConfig | None = None) -> None:
        self.config = config or ReflectionPolicyConfig()

    def decide(
        self,
        *,
        agent_id: str,
        request: AgentRequest,
        result: AgentResult,
        validation: AgentValidationResult,
    ) -> ReflectionDecision:
        capability = self.capability_for(agent_id)
        if not self.config.shadow_enabled and not self.config.revision_enabled:
            return self._skip("reflection_disabled", capability)
        if capability not in DEFAULT_CAPABILITIES:
            return self._skip("capability_not_supported", capability)
        if (
            self.config.allowed_agent_ids
            and agent_id not in self.config.allowed_agent_ids
        ):
            return self._skip("agent_not_allowlisted", capability)
        if bool(request.options.get("time_budget_exhausted")):
            return self._review("reflection_budget_exhausted", capability)
        if result.fallback_used or result.cloud_status == "degraded":
            return self._skip("degraded_fallback", capability)
        if not validation.response_usable or result.status.value == "failed":
            return ReflectionDecision(
                action="fail",
                reason_codes=["deterministic_result_unusable"],
                critic_profile=capability,
                required_verifiers=["result_governance", "domain_verification"],
            )

        reasons = self._trigger_reasons(capability, result)
        if not reasons:
            return self._skip("low_risk_no_trigger", capability)
        return ReflectionDecision(
            action="critique",
            reason_codes=reasons,
            max_revision_count=(
                self.config.max_revision_count if self.config.revision_enabled else 0
            ),
            critic_profile=capability,
            budget_tokens=self.config.critic_budget_tokens,
            budget_ms=self.config.critic_budget_ms,
            required_verifiers=self._required_verifiers(capability),
        )

    @staticmethod
    def capability_for(agent_id: str) -> str:
        if agent_id == "ACADEMIC_PROBLEM_SOLVER":
            return "academic_solver"
        if agent_id.startswith("LEARN_"):
            return "knowledge"
        if agent_id.startswith("RESEARCH_"):
            return "research"
        if agent_id.startswith("TEACH_"):
            return "teaching"
        return "unsupported"

    @staticmethod
    def _required_verifiers(capability: str) -> list[str]:
        if capability == "academic_solver":
            return ["solver_quality_gate", "domain_verification"]
        if capability == "knowledge":
            return ["evidence_gate", "citation_traceability"]
        if capability == "research":
            return ["provenance_gate", "unsupported_claim_gate"]
        if capability == "teaching":
            return ["domain_verification", "evidence_gate"]
        return ["result_governance"]

    @classmethod
    def _trigger_reasons(cls, capability: str, result: AgentResult) -> list[str]:
        reasons: list[str] = []
        structured = result.structured_result
        quality = structured.get("quality_gate")
        if isinstance(quality, dict) and quality.get("status") in {"partial", "fail"}:
            reasons.append("deterministic_quality_warning")
        if result.remaining_risks:
            reasons.append("remaining_risks")
        if capability in {"knowledge", "research"} and result.evidence_status in {
            "insufficient",
            "conflict",
            "uncertain",
        }:
            reasons.append("evidence_quality_warning")
        if result.citations and not cls._citation_status_is_clear(structured):
            reasons.append("citation_review_candidate")
        if capability == "academic_solver":
            execution_path = str(structured.get("execution_path", ""))
            complexity = str(result.metrics.complexity or "")
            if execution_path == "HIGH_RISK" or complexity in {"complex", "high_risk"}:
                reasons.append("high_risk_solver")
        elif capability == "research":
            if structured.get("unsupported_claims") or structured.get(
                "evidence_conflicts"
            ):
                reasons.append("research_evidence_conflict")
        elif capability == "knowledge":
            if isinstance(structured.get("knowledge"), dict):
                hits = structured["knowledge"].get("hits", [])
                if not hits or structured.get("mode") == "governance_model_generation":
                    reasons.append("knowledge_synthesis_candidate")
        elif capability == "teaching" and result.metrics.manual_review_required:
            reasons.append("teaching_review_candidate")
        return list(dict.fromkeys(reasons))

    @staticmethod
    def _citation_status_is_clear(structured: dict[str, object]) -> bool:
        evidence = structured.get("knowledge_evidence")
        if isinstance(evidence, dict):
            return evidence.get("citation_status") in {
                "valid",
                "partially_supported",
                "not_applicable",
            }
        return False

    @staticmethod
    def _skip(reason: str, capability: str) -> ReflectionDecision:
        return ReflectionDecision(
            action="skip",
            reason_codes=[reason],
            critic_profile=capability,
        )

    @staticmethod
    def _review(reason: str, capability: str) -> ReflectionDecision:
        return ReflectionDecision(
            action="needs_review",
            reason_codes=[reason],
            critic_profile=capability,
            required_verifiers=["result_governance"],
        )


def parse_agent_allowlist(raw: str | Iterable[str] | None) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if isinstance(raw, str):
        values: Iterable[str] = raw.split(",")
    else:
        values = raw
    return frozenset(str(item).strip() for item in values if str(item).strip())
