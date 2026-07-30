from __future__ import annotations

from pathlib import Path
from time import perf_counter

import yaml
from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_ERROR_POOL_ROOT = PROJECT_ROOT / "config" / "error_pool"
SUPPORTED_ERROR_POOL_COURSES = frozenset({"CT", "AE", "DE"})


class ErrorTemplateDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_signature: str
    problem_types: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)
    error_type: str
    match_mode: str
    description: str
    hint_templates: dict[str, str] = Field(default_factory=dict)
    teacher_reviewed: bool = False
    enabled: bool = False


class ErrorPoolCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    course_id: str
    errors: list[ErrorTemplateDefinition]


class ErrorPoolLookupResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    error_signature: str = ""
    error_type: str = ""
    description: str = ""
    hint_templates: dict[str, str] = Field(default_factory=dict)
    hint_template_ids: dict[str, str] = Field(default_factory=dict)
    latency_ms: float = Field(default=0, ge=0)


class ErrorPoolRegistry:
    """Exact-only, reviewed deterministic feedback templates."""

    def __init__(self, config_root: Path = DEFAULT_ERROR_POOL_ROOT) -> None:
        self.config_root = config_root
        self._items: dict[str, list[ErrorTemplateDefinition]] = {}
        self._load()

    def list_for_course(self, course_id: str) -> list[ErrorTemplateDefinition]:
        return list(self._items.get(course_id.upper(), []))

    def lookup(
        self,
        *,
        course_id: str,
        problem_type: str,
        skill_ids: list[str] | tuple[str, ...],
        error_signature: str,
    ) -> ErrorPoolLookupResult:
        started = perf_counter()
        course = course_id.upper()
        requested_skills = set(skill_ids)
        for item in self._items.get(course, []):
            if (
                item.error_signature != error_signature
                or item.match_mode != "exact_rule"
                or not item.teacher_reviewed
                or not item.enabled
            ):
                continue
            if "*" not in item.problem_types and problem_type not in item.problem_types:
                continue
            if item.skill_ids and not requested_skills.intersection(item.skill_ids):
                continue
            return ErrorPoolLookupResult(
                status="matched",
                error_signature=item.error_signature,
                error_type=item.error_type,
                description=item.description,
                hint_templates=item.hint_templates,
                hint_template_ids={
                    level: f"{course}.{item.error_signature}.{level}"
                    for level in item.hint_templates
                },
                latency_ms=(perf_counter() - started) * 1000,
            )
        return ErrorPoolLookupResult(
            status="no_match",
            error_signature=error_signature,
            latency_ms=(perf_counter() - started) * 1000,
        )

    def _load(self) -> None:
        for course_id in sorted(SUPPORTED_ERROR_POOL_COURSES):
            path = self.config_root / f"{course_id}.yaml"
            if not path.is_file():
                raise ValueError(f"缺少错因池配置: {path}")
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            catalog = ErrorPoolCatalog.model_validate(raw)
            if catalog.course_id.upper() != course_id:
                raise ValueError(f"{path}: course_id 必须为 {course_id}")
            seen: set[str] = set()
            for item in catalog.errors:
                if item.error_signature in seen:
                    raise ValueError(
                        f"{path}: 重复 error_signature {item.error_signature}"
                    )
                if item.match_mode != "exact_rule":
                    raise ValueError(
                        f"{path}: 第一阶段只允许 exact_rule 匹配"
                    )
                if item.enabled and not item.teacher_reviewed:
                    raise ValueError(
                        f"{path}: 未审核模板不得启用 {item.error_signature}"
                    )
                seen.add(item.error_signature)
            self._items[course_id] = list(catalog.errors)
