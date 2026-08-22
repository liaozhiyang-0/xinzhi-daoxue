from __future__ import annotations

import re
from pathlib import Path
from time import perf_counter
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.capabilities import CapabilityRegistry
from app.courses import CourseRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SKILL_ROOT = PROJECT_ROOT / "config" / "skills"
SUPPORTED_SKILL_COURSES = frozenset({"CT", "AE", "DE"})
PROBLEM_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class SkillDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: str = Field(min_length=3, max_length=128)
    version: str = Field(default="1.0", min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=200)
    name: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=2_000)
    course_id: str = Field(min_length=2, max_length=16)
    domain: str = Field(default="", max_length=128)
    chapter: str = Field(min_length=1, max_length=128)
    prerequisites: list[str] = Field(default_factory=list)
    problem_types: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)
    input_contract: dict[str, object] = Field(default_factory=dict)
    output_contract: dict[str, object] = Field(default_factory=dict)
    eligible_workers: list[str] = Field(default_factory=list)
    eligible_tools: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    risk: Literal["low", "medium", "high", "critical"] = "low"
    budget_hint: dict[str, int | float | str] = Field(default_factory=dict)
    verification_requirements: list[str] = Field(default_factory=list)
    common_error_signatures: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    semantic_description: str = Field(default="", max_length=2_000)
    status: Literal["active", "experimental", "frozen", "deprecated"] = "active"

    @model_validator(mode="after")
    def complete_legacy_metadata(self) -> "SkillDefinition":
        """Keep the existing title/chapter YAML vocabulary source-compatible."""

        if not self.name:
            self.name = self.title
        if not self.description:
            self.description = self.title
        if not self.domain:
            self.domain = self.course_id
        if not self.semantic_description:
            self.semantic_description = "；".join(
                [self.title, *self.keywords]
            )
        return self


class SkillCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    course_id: str
    skills: list[SkillDefinition]


class SkillMappingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str
    skill_ids: list[str] = Field(default_factory=list)
    status: Literal["mapped", "partial", "unavailable"]
    warnings: list[str] = Field(default_factory=list)
    latency_ms: float = Field(default=0, ge=0)


class SkillMatch(BaseModel):
    """A retrieval/policy result; it never represents an executable Agent."""

    model_config = ConfigDict(extra="forbid")

    skill_id: str = Field(min_length=3, max_length=128)
    score: float = Field(default=0, ge=0)
    match_reasons: list[str] = Field(default_factory=list)
    eligibility: Literal["eligible", "ineligible"] = "ineligible"
    prerequisite_status: Literal["satisfied", "missing", "unknown"] = "unknown"
    policy_status: Literal["approved", "rejected", "pending"] = "pending"
    version: str = Field(min_length=1, max_length=32)


class SkillRegistry:
    """Versioned CT/AE/DE skill metadata; it is not a knowledge graph."""

    def __init__(
        self,
        course_registry: CourseRegistry,
        capability_registry: CapabilityRegistry,
        config_root: Path = DEFAULT_SKILL_ROOT,
    ) -> None:
        self.course_registry = course_registry
        self.capability_registry = capability_registry
        self.config_root = config_root
        self._skills: dict[str, SkillDefinition] = {}
        self._by_course: dict[str, list[SkillDefinition]] = {}
        self._load()

    def get(self, skill_id: str) -> SkillDefinition:
        try:
            return self._skills[skill_id]
        except KeyError as exc:
            raise KeyError(f"未注册教学技能: {skill_id}") from exc

    def list_for_course(self, course_id: str) -> list[SkillDefinition]:
        return list(self._by_course.get(course_id.upper(), []))

    def map_skills(
        self,
        *,
        course_id: str,
        problem_type: str | None = None,
        capability_ids: list[str] | tuple[str, ...] = (),
        terms: list[str] | tuple[str, ...] = (),
    ) -> SkillMappingResult:
        started = perf_counter()
        course = course_id.upper()
        if course not in SUPPORTED_SKILL_COURSES:
            return SkillMappingResult(
                course_id=course,
                status="unavailable",
                warnings=[f"skill mapping unavailable for course {course}"],
                latency_ms=(perf_counter() - started) * 1000,
            )
        normalized_terms = {
            item.strip().casefold() for item in terms if item and item.strip()
        }
        requested_capabilities = set(capability_ids)
        scored: list[tuple[int, str]] = []
        for skill in self._by_course.get(course, []):
            score = 0
            if requested_capabilities.intersection(skill.capability_ids):
                score += 100
            if problem_type and problem_type in skill.problem_types:
                score += 50
            labels = {
                skill.skill_id.casefold(),
                skill.title.casefold(),
                *(item.casefold() for item in skill.keywords),
            }
            if normalized_terms.intersection(labels):
                score += 20
            if score:
                scored.append((score, skill.skill_id))
        best_score = max((score for score, _ in scored), default=0)
        selected = [
            skill_id
            for score, skill_id in sorted(
                scored, key=lambda item: (-item[0], item[1])
            )
            if score == best_score
        ][:5]
        warnings = [] if selected else ["skill mapping unavailable"]
        return SkillMappingResult(
            course_id=course,
            skill_ids=selected,
            status="mapped" if selected else "partial",
            warnings=warnings,
            latency_ms=(perf_counter() - started) * 1000,
        )

    def _load(self) -> None:
        seen: set[str] = set()
        capability_ids = {
            item.capability_id
            for item in self.capability_registry.list_capabilities()
        }
        for course_id in sorted(SUPPORTED_SKILL_COURSES):
            path = self.config_root / f"{course_id}.yaml"
            if not path.is_file():
                raise ValueError(f"缺少教学技能配置: {path}")
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            catalog = SkillCatalog.model_validate(raw)
            if catalog.course_id.upper() != course_id:
                raise ValueError(f"{path}: course_id 必须为 {course_id}")
            course_pack = self.course_registry.get(course_id)
            for skill in catalog.skills:
                if skill.course_id.upper() != course_id:
                    raise ValueError(
                        f"{path}: {skill.skill_id} course_id 与目录不一致"
                    )
                if skill.skill_id in seen:
                    raise ValueError(f"重复 skill_id: {skill.skill_id}")
                if not skill.skill_id.startswith(f"{course_id}."):
                    raise ValueError(
                        f"{path}: skill_id 必须使用 {course_id}. 前缀"
                    )
                invalid_problem_types = [
                    item
                    for item in skill.problem_types
                    if not PROBLEM_TYPE_PATTERN.fullmatch(item)
                    or item not in course_pack.supported_problem_types
                ]
                if invalid_problem_types:
                    raise ValueError(
                        f"{skill.skill_id}: 无效 problem_type "
                        + ", ".join(invalid_problem_types)
                    )
                invalid_capabilities = set(skill.capability_ids) - capability_ids
                if invalid_capabilities:
                    raise ValueError(
                        f"{skill.skill_id}: 未注册 capability_id "
                        + ", ".join(sorted(invalid_capabilities))
                    )
                seen.add(skill.skill_id)
                self._skills[skill.skill_id] = skill
                self._by_course.setdefault(course_id, []).append(skill)
        for skill in self._skills.values():
            missing = set(skill.prerequisites) - set(self._skills)
            if missing:
                raise ValueError(
                    f"{skill.skill_id}: 前置 skill 不存在 "
                    + ", ".join(sorted(missing))
                )
            cross_course = [
                item
                for item in skill.prerequisites
                if self._skills[item].course_id != skill.course_id
            ]
            if cross_course:
                raise ValueError(
                    f"{skill.skill_id}: 第一阶段不允许跨课程前置关系 "
                    + ", ".join(cross_course)
                )
        self._validate_acyclic()

    def _validate_acyclic(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(skill_id: str) -> None:
            if skill_id in visiting:
                raise ValueError(f"教学技能先修关系存在循环: {skill_id}")
            if skill_id in visited:
                return
            visiting.add(skill_id)
            for prerequisite in self._skills[skill_id].prerequisites:
                visit(prerequisite)
            visiting.remove(skill_id)
            visited.add(skill_id)

        for skill_id in sorted(self._skills):
            visit(skill_id)
