from __future__ import annotations

import builtins
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
PROBLEM_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+(?:\.\d+)?$")


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
    allowed_roles: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    risk: Literal["low", "medium", "high", "critical"] = "low"
    budget_hint: dict[str, int | float | str] = Field(default_factory=dict)
    verification_requirements: list[str] = Field(default_factory=list)
    common_error_signatures: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    semantic_description: str = Field(default="", max_length=2_000)
    status: Literal["active", "experimental", "frozen", "deprecated"] = "active"

    @model_validator(mode="after")
    def complete_legacy_metadata(self) -> SkillDefinition:
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
        return self.resolve(skill_id)

    def resolve(self, skill_id: str, *, version: str | None = None) -> SkillDefinition:
        """Resolve a legacy or canonical ID without inventing aliases."""

        normalized_id = str(skill_id).strip()
        try:
            skill = self._skills[normalized_id]
        except KeyError as exc:
            raise KeyError(f"未注册教学技能: {normalized_id}") from exc
        if version is not None and skill.version != version:
            raise ValueError(
                "技能版本不匹配: "
                f"{normalized_id} expected={version} actual={skill.version}"
            )
        return skill

    def validate_identity_version(self, skill_id: str, version: str) -> bool:
        self.resolve(skill_id, version=version)
        return True

    def list_for_course(self, course_id: str) -> list[SkillDefinition]:
        return list(self._by_course.get(course_id.upper(), []))

    def list(
        self,
        *,
        course_id: str | None = None,
        status: str | None = None,
        domain: str | None = None,
    ) -> list[SkillDefinition]:
        """List registered metadata with deterministic filters."""

        items = list(self._skills.values())
        if course_id is not None:
            items = [
                item
                for item in items
                if item.course_id.upper() == course_id.upper()
            ]
        if status is not None:
            items = [item for item in items if item.status == status]
        if domain is not None:
            items = [item for item in items if item.domain == domain]
        return sorted(items, key=lambda item: item.skill_id)

    def validate_prerequisites(
        self,
        skill_id: str,
        *,
        available_skill_ids: builtins.list[str] | tuple[str, ...] = (),
    ) -> tuple[bool, builtins.list[str]]:
        """Return whether all direct prerequisites are available and registered."""

        skill = self.resolve(skill_id)
        available = {str(item).strip() for item in available_skill_ids}
        missing = [item for item in skill.prerequisites if item not in available]
        return not missing, missing

    def serialize(self, skill_id: str) -> dict[str, object]:
        return self.resolve(skill_id).model_dump(mode="json")

    def map_skills(
        self,
        *,
        course_id: str,
        problem_type: str | None = None,
        capability_ids: builtins.list[str] | tuple[str, ...] = (),
        terms: builtins.list[str] | tuple[str, ...] = (),
    ) -> SkillMappingResult:
        started = perf_counter()
        course = course_id.upper()
        if course not in self._by_course:
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
        paths = sorted(self.config_root.glob("*.yaml"))
        if not paths:
            raise ValueError(f"缺少教学技能配置: {self.config_root}")
        for path in paths:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            catalog = SkillCatalog.model_validate(raw)
            course_id = catalog.course_id.upper()
            if not VERSION_PATTERN.fullmatch(catalog.version):
                raise ValueError(f"{path}: version 格式无效: {catalog.version}")
            course_pack = self.course_registry.get(course_id)
            is_registered_course = course_pack.course_code.upper() == course_id
            for skill in catalog.skills:
                if skill.version != catalog.version:
                    raise ValueError(
                        f"{skill.skill_id}: skill version 必须与 catalog version 一致"
                    )
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
                    or (
                        is_registered_course
                        and item not in course_pack.supported_problem_types
                    )
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
