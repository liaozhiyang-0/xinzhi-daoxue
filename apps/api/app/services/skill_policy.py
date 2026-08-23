from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.skill_registry import SkillMatch, SkillRegistry
from app.services.skill_retriever import SkillRetrievalRequest

RISK_LEVELS = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class SkillPolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: str
    version: str = ""
    status: Literal["approved", "rejected"]
    reason_codes: list[str] = Field(default_factory=list)


class SkillPolicyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: list[SkillMatch] = Field(default_factory=list)
    rejected: list[SkillPolicyDecision] = Field(default_factory=list)


class SkillPolicy:
    """Fail-closed eligibility checks for metadata-only Skill candidates."""

    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    def evaluate(
        self,
        matches: list[SkillMatch],
        request: SkillRetrievalRequest,
    ) -> SkillPolicyResult:
        approved: list[SkillMatch] = []
        rejected: list[SkillPolicyDecision] = []
        for match in matches:
            reasons = self._rejection_reasons(match, request)
            if reasons:
                rejected.append(
                    SkillPolicyDecision(
                        skill_id=match.skill_id,
                        version=match.version,
                        status="rejected",
                        reason_codes=reasons,
                    )
                )
                continue
            approved.append(
                match.model_copy(
                    update={
                        "eligibility": "eligible",
                        "policy_status": "approved",
                    }
                )
            )
        return SkillPolicyResult(approved=approved, rejected=rejected)

    def validate_requested(
        self,
        skill_ids: list[str],
        request: SkillRetrievalRequest,
        *,
        versions: dict[str, str] | None = None,
    ) -> SkillPolicyResult:
        """Validate explicit IDs so injection cannot create a Skill."""

        matches: list[SkillMatch] = []
        rejected: list[SkillPolicyDecision] = []
        versions = versions or {}
        for skill_id in skill_ids:
            try:
                skill = self.registry.resolve(skill_id)
            except KeyError:
                rejected.append(
                    SkillPolicyDecision(
                        skill_id=skill_id,
                        status="rejected",
                        reason_codes=["unregistered_skill"],
                    )
                )
                continue
            matches.append(
                SkillMatch(
                    skill_id=skill.skill_id,
                    score=0,
                    match_reasons=["explicit_skill_request"],
                    eligibility="eligible",
                    prerequisite_status="satisfied",
                    policy_status="pending",
                    version=versions.get(skill.skill_id, skill.version),
                )
            )
        result = self.evaluate(matches, request)
        return SkillPolicyResult(
            approved=result.approved,
            rejected=[*rejected, *result.rejected],
        )

    def _rejection_reasons(
        self,
        match: SkillMatch,
        request: SkillRetrievalRequest,
    ) -> list[str]:
        reasons: list[str] = []
        try:
            skill = self.registry.resolve(match.skill_id, version=match.version)
        except KeyError:
            return ["unregistered_skill"]
        except ValueError:
            return ["version_mismatch"]
        if skill.status in {"frozen", "deprecated"}:
            reasons.append(f"status_{skill.status}")
        if (
            skill.scope == "course"
            and request.normalized_course
            and skill.course_id.upper() != request.normalized_course
        ):
            reasons.append("course_mismatch")
        if skill.capability_ids and request.capabilities and not set(
            skill.capability_ids
        ).intersection(request.capabilities):
            reasons.append("capability_mismatch")
        if match.prerequisite_status != "satisfied":
            reasons.append("prerequisite_missing")
        if skill.eligible_workers and not set(skill.eligible_workers).intersection(
            request.available_workers
        ):
            reasons.append("worker_dependency_unavailable")
        if skill.eligible_tools and not set(skill.eligible_tools).intersection(
            request.available_tools
        ):
            reasons.append("tool_dependency_unavailable")
        missing_evidence = [
            item
            for item in skill.required_evidence
            if not request.evidence_state.get(item)
        ]
        if missing_evidence:
            reasons.append("evidence_missing:" + ",".join(missing_evidence))
        if RISK_LEVELS.get(skill.risk, 99) > RISK_LEVELS.get(request.max_risk, -1):
            reasons.append("risk_exceeds_policy")
        if skill.allowed_roles and request.role not in skill.allowed_roles:
            reasons.append("role_not_allowed")
        for key in ("max_model_calls", "max_tool_calls", "max_subagent_runs"):
            hint = skill.budget_hint.get(key)
            limit = getattr(request.budget, key)
            if isinstance(hint, (int, float)) and hint > limit:
                reasons.append(f"budget_exceeds:{key}")
        return list(dict.fromkeys(reasons))
