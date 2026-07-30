from __future__ import annotations

import json
import re
from typing import Any, Literal

from app.contracts import SolutionPacketV1, SolutionStepV1
from app.contracts.solver import SolverResult
from app.services.skill_registry import SkillMappingResult, SkillRegistry

SAFE_STEP_FIELDS = (
    "content",
    "equation",
    "expression",
    "substitution",
    "result",
    "summary",
    "items",
    "tools",
    "status",
)
EXECUTION_STAGES = frozenset(
    {
        "structure",
        "capability_selection",
        "deterministic_validation",
        "model_reasoning",
    }
)
TARGET_UNIT_PATTERNS = (
    (re.compile(r"(?:求|计算|确定)[^。；，]{0,20}电流"), "A"),
    (re.compile(r"(?:求|计算|确定)[^。；，]{0,20}电压"), "V"),
    (re.compile(r"(?:求|计算|确定)[^。；，]{0,20}(?:功率|功耗)"), "W"),
    (re.compile(r"(?:求|计算|确定)[^。；，]{0,20}(?:电阻|阻抗)"), "Ω"),
    (re.compile(r"(?:求|计算|确定)[^。；，]{0,20}频率"), "Hz"),
)


class SolutionPacketAdapterService:
    """Converts SolverResult without changing or re-executing the solver."""

    def __init__(self, skills: SkillRegistry) -> None:
        self.skills = skills

    def from_structured_result(
        self, structured: dict[str, Any], *, course_id: str
    ) -> tuple[SolutionPacketV1 | None, SkillMappingResult]:
        payload = {
            key: value
            for key, value in structured.items()
            if key in SolverResult.model_fields
        }
        payload.setdefault("status", structured.get("status", "partial"))
        payload.setdefault("course", course_id)
        payload.setdefault("problem_summary", "")
        payload.setdefault("final_answer", structured.get("final_answer", ""))
        try:
            solver_result = SolverResult.model_validate(payload)
        except ValueError:
            mapping = self.skills.map_skills(course_id=course_id)
            return None, mapping
        capabilities = self._capability_ids(solver_result.solution_steps)
        mapping = self.skills.map_skills(
            course_id=course_id,
            problem_type=solver_result.problem_type,
            capability_ids=capabilities,
            terms=solver_result.knowledge_points,
        )
        evidence_refs = self._evidence_refs(solver_result.citations)
        steps = [
            self._step(
                item,
                index=index,
                default_skill_ids=mapping.skill_ids,
                evidence_refs=evidence_refs,
                confidence=solver_result.confidence,
            )
            for index, item in enumerate(solver_result.solution_steps, start=1)
        ]
        warnings = list(mapping.warnings)
        if any(item.step_source == "solver_execution" for item in steps):
            warnings.append(
                "solver execution stages are not pedagogical derivation steps"
            )
        reference_directions = [
            str(item)
            for item in structured.get("reference_directions", [])
            if str(item).strip()
        ]
        units = {
            str(item.get("unit"))
            for item in solver_result.target_quantities
            if isinstance(item, dict) and item.get("unit")
        }
        if solver_result.final_answer_detail and solver_result.final_answer_detail.unit:
            units.add(solver_result.final_answer_detail.unit)
        if not units:
            inferred_unit = self._target_unit(solver_result.problem_summary)
            if inferred_unit:
                units.add(inferred_unit)
        model_execution = structured.get("model_execution")
        model_answer_available = (
            isinstance(model_execution, dict)
            and model_execution.get("status") in {"completed", "partial"}
            and bool(solver_result.final_answer.strip())
        )
        final_answer: dict[str, Any] | str | None = solver_result.final_answer
        if (
            solver_result.final_answer_detail is not None
            and not model_answer_available
        ):
            final_answer = solver_result.final_answer_detail.model_dump(mode="json")
        packet = SolutionPacketV1(
            course_id=course_id.upper(),
            problem_type=solver_result.problem_type,
            problem_summary=solver_result.problem_summary,
            givens=solver_result.known_conditions,
            targets=solver_result.target_quantities,
            assumptions=solver_result.assumptions,
            reference_directions=reference_directions,
            skill_ids=mapping.skill_ids,
            plan=(
                [solver_result.solution_method]
                if solver_result.solution_method.strip()
                else []
            ),
            steps=steps,
            final_answer=final_answer,
            units=sorted(units),
            common_errors=solver_result.common_mistakes,
            evidence_refs=evidence_refs,
            tool_outputs=solver_result.tool_verification,
            mapping_status=mapping.status,
            warnings=list(dict.fromkeys(warnings)),
        )
        return packet, mapping

    @staticmethod
    def _target_unit(problem_summary: str) -> str | None:
        for pattern, unit in TARGET_UNIT_PATTERNS:
            if pattern.search(problem_summary):
                return unit
        return None

    @staticmethod
    def _capability_ids(steps: list[dict[str, Any]]) -> list[str]:
        values: list[str] = []
        for step in steps:
            if step.get("stage") != "capability_selection":
                continue
            items = step.get("items", [])
            if isinstance(items, list):
                values.extend(str(item) for item in items if str(item).strip())
        return list(dict.fromkeys(values))

    @staticmethod
    def _evidence_refs(citations: list[dict[str, Any]]) -> list[str]:
        values: list[str] = []
        for citation in citations:
            for key in ("evidence_id", "source_ref", "citation_id"):
                value = citation.get(key)
                if isinstance(value, str) and value.strip():
                    values.append(value.strip())
                    break
        return list(dict.fromkeys(values))

    @staticmethod
    def _step(
        raw: dict[str, Any],
        *,
        index: int,
        default_skill_ids: list[str],
        evidence_refs: list[str],
        confidence: float,
    ) -> SolutionStepV1:
        stage = str(raw.get("stage", "")).strip()
        source = str(raw.get("step_source", "")).strip()
        if stage in EXECUTION_STAGES:
            step_source: Literal[
                "solver_execution", "pedagogical", "tool", "adapted_unknown"
            ] = "solver_execution"
        elif source == "pedagogical":
            step_source = "pedagogical"
        elif source == "tool":
            step_source = "tool"
        elif source == "adapted_unknown":
            step_source = "adapted_unknown"
        elif raw.get("tool_id"):
            step_source = "tool"
        else:
            step_source = "adapted_unknown"
        safe = {key: raw[key] for key in SAFE_STEP_FIELDS if key in raw}
        content_value = raw.get("content")
        content = (
            str(content_value).strip()
            if isinstance(content_value, str) and content_value.strip()
            else json.dumps(safe, ensure_ascii=False, sort_keys=True)[:2_000]
        )
        raw_skills = raw.get("skill_ids", default_skill_ids)
        skill_ids = (
            [str(item) for item in raw_skills]
            if isinstance(raw_skills, list)
            else list(default_skill_ids)
        )
        return SolutionStepV1(
            step_id=str(raw.get("step_id") or f"S{index}"),
            title=str(raw.get("title") or stage or f"步骤 {index}"),
            content=content or "未提供可展示的步骤内容",
            skill_ids=skill_ids,
            expression=(
                str(raw.get("expression") or raw.get("equation"))
                if raw.get("expression") or raw.get("equation")
                else None
            ),
            result=str(raw["result"]) if raw.get("result") is not None else None,
            unit=str(raw["unit"]) if raw.get("unit") else None,
            depends_on=[
                str(item)
                for item in raw.get("depends_on", [])
                if str(item).strip()
            ],
            evidence_refs=[
                str(item)
                for item in raw.get("evidence_refs", evidence_refs)
                if str(item).strip()
            ],
            tool_output_refs=[
                str(item)
                for item in raw.get("tool_output_refs", [])
                if str(item).strip()
            ],
            step_source=step_source,
            confidence=confidence,
        )
