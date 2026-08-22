from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.planner import CanonicalGoal, PlannerBudget
from app.services.skill_registry import SkillDefinition, SkillMatch, SkillRegistry


class SkillRetrievalRequest(BaseModel):
    """Read-only retrieval input; it contains no executable handler object."""

    model_config = ConfigDict(extra="forbid")

    goal: CanonicalGoal = Field(default_factory=CanonicalGoal)
    course: str = ""
    intent: str = ""
    problem_type: str = ""
    capabilities: list[str] = Field(default_factory=list, max_length=32)
    context_summary: str = Field(default="", max_length=8_000)
    evidence_state: dict[str, Any] = Field(default_factory=dict, max_length=32)
    learner_state: dict[str, Any] = Field(default_factory=dict, max_length=32)
    available_workers: list[str] = Field(default_factory=list, max_length=32)
    available_tools: list[str] = Field(default_factory=list, max_length=32)
    available_skill_ids: list[str] = Field(default_factory=list, max_length=64)
    budget: PlannerBudget = Field(default_factory=PlannerBudget)
    max_risk: str = "low"
    role: str = "student"
    requested_skill_ids: list[str] = Field(default_factory=list, max_length=32)

    @property
    def normalized_course(self) -> str:
        return (self.course or self.goal.course).strip().upper()


class SkillRetriever:
    """Deterministic, bounded candidate retrieval over the unique registry."""

    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    def retrieve(
        self, request: SkillRetrievalRequest, *, top_k: int = 5
    ) -> list[SkillMatch]:
        if not 1 <= top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        course = request.normalized_course
        if not course:
            return []
        candidates = self.registry.list(course_id=course)
        requested = set(request.requested_skill_ids)
        text = " ".join(
            [
                request.goal.objective,
                request.context_summary,
                request.intent,
                request.goal.intent,
            ]
        ).casefold()
        matches: list[SkillMatch] = []
        for skill in candidates:
            score, reasons = self._score(skill, request, text)
            if skill.skill_id in requested:
                score += 100
                reasons.append("explicit_skill_request")
            if score <= 0:
                continue
            prerequisite_status = self._prerequisite_status(skill, request)
            matches.append(
                SkillMatch(
                    skill_id=skill.skill_id,
                    score=float(score),
                    match_reasons=list(dict.fromkeys(reasons)),
                    eligibility=(
                        "eligible"
                        if prerequisite_status == "satisfied"
                        else "ineligible"
                    ),
                    prerequisite_status=prerequisite_status,
                    policy_status="pending",
                    version=skill.version,
                )
            )
        return sorted(
            matches,
            key=lambda item: (-item.score, item.skill_id),
        )[:top_k]

    @staticmethod
    def _score(
        skill: SkillDefinition,
        request: SkillRetrievalRequest,
        text: str,
    ) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []
        if request.problem_type and request.problem_type in skill.problem_types:
            score += 50
            reasons.append(f"problem_type:{request.problem_type}")
        capability_hits = sorted(
            set(request.capabilities).intersection(skill.capability_ids)
        )
        if capability_hits:
            score += 25 + 5 * len(capability_hits)
            reasons.extend(f"capability:{item}" for item in capability_hits)
        keyword_hits = [
            keyword
            for keyword in skill.keywords
            if keyword.strip() and keyword.casefold() in text
        ]
        if keyword_hits:
            score += min(20, 5 * len(keyword_hits))
            reasons.extend(f"keyword:{item}" for item in keyword_hits)
        if request.goal.task_family and request.goal.task_family.casefold() in {
            skill.domain.casefold(),
            skill.chapter.casefold(),
        }:
            score += 10
            reasons.append("task_family_metadata")
        return score, reasons

    def _prerequisite_status(
        self,
        skill: SkillDefinition,
        request: SkillRetrievalRequest,
    ) -> str:
        if not skill.prerequisites:
            return "satisfied"
        satisfied, _ = self.registry.validate_prerequisites(
            skill.skill_id,
            available_skill_ids=request.available_skill_ids,
        )
        return "satisfied" if satisfied else "missing"


def normalized_terms(value: str) -> set[str]:
    """Small shared tokenizer for policy/tests; no semantic/vector lookup."""

    return {item for item in re.split(r"[\s,;，；。！？!?]+", value.casefold()) if item}
