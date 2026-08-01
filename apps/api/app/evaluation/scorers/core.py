from __future__ import annotations

import cmath
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.evaluation.contracts import (
    EvaluationCase,
    EvaluationErrorType,
    EvaluationResult,
    FailureStage,
)
from app.tools import ToolRegistry
from app.tools.calculator import calculate
from app.tools.unit_checker import check_unit_compatibility

_SYMBOLS = str.maketrans({"−": "-", "–": "-", "×": "*", "÷": "/", "ｊ": "j"})
_UNIT_SCALE = {
    "V": 1.0,
    "mV": 1e-3,
    "kV": 1e3,
    "A": 1.0,
    "mA": 1e-3,
    "uA": 1e-6,
    "Ω": 1.0,
    "ohm": 1.0,
    "kΩ": 1e3,
    "F": 1.0,
    "uF": 1e-6,
    "H": 1.0,
    "Hz": 1.0,
    "s": 1.0,
    "W": 1.0,
}
_KEYWORD_EQUIVALENTS = {
    "缺少": ("缺少", "缺失", "未提供", "未给出", "信息不足"),
}
_SOLUTION_CLAIM_FIELDS = (
    "final_answer",
    "final_answer_detail",
    "solution_steps",
    "intermediate_results",
    "verification",
    "verification_report",
    "professional_validation",
    "assumptions",
    "remaining_risks",
)
_NEGATION_MARKERS = (
    "不能",
    "不可",
    "不应",
    "不得",
    "并非",
    "不成立",
    "不能推出",
    "无法保证",
    "错误",
    "矛盾",
    "拒绝",
)
_HINT_LEVELS = {"H0": 0, "H1": 1, "H2": 2}


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value)).translate(_SYMBOLS).casefold()
    return " ".join(text.split())


@dataclass(frozen=True)
class ParsedQuantity:
    value: complex
    unit: str | None


class EvaluationScorer:
    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools

    def score(
        self,
        case: EvaluationCase,
        actual: dict[str, Any],
        *,
        elapsed_ms: int,
        model_calls: list[dict[str, Any]],
        trace_id: str,
        cache_key: str | None = None,
    ) -> EvaluationResult:
        structured = self._dict(actual.get("structured_result"))
        answer = str(actual.get("answer", ""))
        searchable = normalize_text(
            "\n".join((answer, json.dumps(structured, ensure_ascii=False)))
        )
        safety_searchable = self._safety_searchable(answer, structured)
        task_families = {str(item) for item in actual.get("task_families", [])}
        route_passed = (
            case.task_family in task_families
            and str(actual.get("intent")) == case.intent
        )
        course_passed = str(actual.get("course")) == case.course and (
            case.expected_course_pack is None
            or str(actual.get("course_pack")) == case.expected_course_pack
        )
        agent_passed = str(actual.get("agent_id")) == case.expected_agent
        structure_passed = self._structure_passed(case, actual, structured)
        execution_path = str(actual.get("execution_path", ""))
        execution_path_passed = (
            not case.expected_execution_paths
            or execution_path in case.expected_execution_paths
        )
        missing_keywords = [
            item
            for item in case.required_keywords
            if not self._keyword_present(item, searchable)
        ]
        missing_keywords.extend(
            item
            for item in case.required_equations
            if normalize_text(item) not in searchable
        )
        missing_steps = [
            item
            for item in case.required_steps
            if normalize_text(item) not in searchable
        ]
        forbidden = [
            item
            for item in case.forbidden_claims
            if self._forbidden_claim_present(item, safety_searchable)
        ]
        numeric = self._numeric_comparisons(case, actual, structured)
        numeric_passed = all(item["passed"] for item in numeric)
        status_passed = str(actual.get("status")) in case.expected_statuses
        safety_passed = not forbidden
        tool_calls = self._tool_calls(actual, structured)
        selected_tools = set(actual.get("selected_tools", []))
        tool_mismatches = self._tool_mismatches(case, tool_calls, selected_tools)
        tools_passed = not tool_mismatches
        citations_passed, citation_errors = self._citations_passed(case, actual)
        insufficient_passed = self._insufficient_passed(case, actual, searchable)
        (
            teaching_foundation_passed,
            teaching_advisories,
        ) = self._teaching_foundation_assessment(case, actual)
        answer_passed = (
            status_passed
            and not missing_keywords
            and not missing_steps
            and numeric_passed
            and insufficient_passed
        )
        checks = (
            route_passed,
            course_passed,
            agent_passed,
            structure_passed,
            execution_path_passed,
            tools_passed,
            answer_passed,
            citations_passed,
            safety_passed,
            teaching_foundation_passed,
        )
        dimension_scores = {
            "routing": 100.0
            if route_passed and course_passed and agent_passed
            else 0.0,
            "structure": 100.0 if structure_passed and execution_path_passed else 0.0,
            "reasoning": 100.0 if answer_passed else 0.0,
            "numeric": 100.0 if numeric_passed else 0.0,
            "units": 100.0 if answer_passed else 0.0,
            "citations": 100.0 if citations_passed else 0.0,
            "safety": 100.0 if safety_passed and tools_passed else 0.0,
            "teaching_foundation": (
                100.0 if teaching_foundation_passed else 0.0
            ),
        }
        weights = case.rubric.model_dump()
        weight_total = sum(float(value) for value in weights.values()) or 1.0
        score = round(
            sum(dimension_scores[key] * float(weights[key]) for key in weights)
            / weight_total,
            2,
        )
        error_types = self._errors(
            route_passed=route_passed,
            course_passed=course_passed,
            agent_passed=agent_passed,
            structure_passed=structure_passed,
            execution_path_passed=execution_path_passed,
            status_passed=status_passed,
            missing_keywords=missing_keywords,
            missing_steps=missing_steps,
            forbidden=forbidden,
            numeric=numeric,
            tool_mismatches=tool_mismatches,
            citation_errors=citation_errors,
            insufficient_passed=insufficient_passed,
            teaching_foundation_passed=teaching_foundation_passed,
        )
        failure_stage = self._failure_stage(error_types)
        return EvaluationResult(
            case_id=case.case_id,
            status="passed" if all(checks) else "failed",
            route_passed=route_passed,
            course_passed=course_passed,
            agent_passed=agent_passed,
            structure_passed=structure_passed,
            execution_path_passed=execution_path_passed,
            tools_passed=tools_passed,
            answer_passed=answer_passed,
            citations_passed=citations_passed,
            safety_passed=safety_passed,
            total_score=score,
            expected={
                "task_family": case.task_family,
                "course": case.course,
                "agent_id": case.expected_agent,
                "course_pack": case.expected_course_pack,
                "execution_paths": case.expected_execution_paths,
                "statuses": case.expected_statuses,
                "teaching_foundation": {
                    key: getattr(case, key)
                    for key in (
                        "student_attempt_parsed",
                        "teaching_mode_respected",
                        "solution_packet_valid",
                        "skill_mapping_valid",
                        "evidence_packet_valid",
                        "error_pool_match_valid",
                        "answer_disclosure_compliant",
                        "requires_manual_review",
                        "expected_teaching_execution_path",
                        "verification_report_valid",
                        "expected_verification_status",
                        "expected_error_type",
                        "expected_hint_level",
                        "expected_disclosure_mode",
                        "next_check_valid",
                        "solution_packet_reused",
                        "full_solution_disclosed",
                        "no_additional_model_calls",
                        "first_confirmed_error_found",
                        "cross_user_isolated",
                    )
                    if getattr(case, key) is not None
                },
                "skill_ids": case.expected_skill_ids,
            },
            actual=actual,
            missing_keywords=missing_keywords,
            missing_steps=missing_steps,
            forbidden_claims_found=forbidden,
            numeric_comparisons=numeric,
            tool_mismatches=tool_mismatches,
            failure_stage=failure_stage,
            error_types=error_types,
            warnings=[
                *[str(item) for item in actual.get("warnings", [])],
                *teaching_advisories,
            ],
            elapsed_ms=elapsed_ms,
            model_calls=model_calls,
            tool_calls=tool_calls,
            trace_id=trace_id,
            cache_key=cache_key,
            dimension_scores=dimension_scores,
            judge_type=case.judge_type,
        )

    @staticmethod
    def _structure_passed(
        case: EvaluationCase, actual: dict[str, Any], structured: dict[str, Any]
    ) -> bool:
        if actual.get("task_status") != "completed":
            return False
        if case.task_family == "ACADEMIC_SOLVING":
            return bool(structured.get("problem_summary")) and bool(
                structured.get("course")
            )
        return bool(actual.get("answer") or structured)

    def _tool_mismatches(
        self,
        case: EvaluationCase,
        tool_calls: list[dict[str, Any]],
        selected_tools: set[str],
    ) -> list[dict[str, Any]]:
        called = {str(item.get("tool_id")): item for item in tool_calls}
        mismatches: list[dict[str, Any]] = []
        for tool_id in case.expected_tools:
            definition = self.tools.describe(tool_id)
            if not definition.enabled:
                mismatches.append({"tool_id": tool_id, "reason": "tool_disabled"})
            elif tool_id in called and called[tool_id].get("status") == "failed":
                mismatches.append({"tool_id": tool_id, "reason": "execution_failed"})
            elif tool_id not in called and tool_id not in selected_tools:
                mismatches.append({"tool_id": tool_id, "reason": "not_selected"})
            elif tool_id not in called:
                mismatches.append({"tool_id": tool_id, "reason": "not_executed"})
        for tool_id in case.forbidden_tools:
            if tool_id in called or tool_id in selected_tools:
                mismatches.append({"tool_id": tool_id, "reason": "forbidden_tool"})
        return mismatches

    @staticmethod
    def _tool_calls(
        actual: dict[str, Any], structured: dict[str, Any]
    ) -> list[dict[str, Any]]:
        values = actual.get("tool_calls", structured.get("tool_verification", []))
        return [item for item in values if isinstance(item, dict)]

    @staticmethod
    def _citations_passed(
        case: EvaluationCase, actual: dict[str, Any]
    ) -> tuple[bool, list[EvaluationErrorType]]:
        citations = actual.get("citations", [])
        if case.expected_citations is None:
            return True, []
        if case.expected_citations is False:
            return (
                not citations,
                [] if not citations else [EvaluationErrorType.CITATION_INVALID],
            )
        if not citations:
            return False, [EvaluationErrorType.CITATION_MISSING]
        if (
            case.min_citation_count is not None
            and len(citations) < case.min_citation_count
        ):
            return False, [EvaluationErrorType.CITATION_MISSING]
        invalid = [item for item in citations if not str(item).strip()]
        return (
            not invalid,
            [] if not invalid else [EvaluationErrorType.CITATION_INVALID],
        )

    def _numeric_comparisons(
        self,
        case: EvaluationCase,
        actual: dict[str, Any],
        structured: dict[str, Any],
    ) -> list[dict[str, Any]]:
        comparisons: list[dict[str, Any]] = []
        tolerance = case.numeric_tolerance or 1e-6
        for key, expected_raw in case.reference_values.items():
            actual_raw = self._find_value(structured, key)
            if actual_raw is None:
                actual_raw = self._find_in_answer(str(actual.get("answer", "")), key)
            comparison: dict[str, Any] = {
                "key": key,
                "expected": expected_raw,
                "actual": actual_raw,
                "tolerance": tolerance,
                "passed": False,
            }
            try:
                expected = self._parse_quantity(expected_raw)
                observed = self._parse_quantity(actual_raw)
                compatible = self._units_compatible(expected.unit, observed.unit)
                absolute_error = abs(expected.value - observed.value)
                relative_error = absolute_error / max(abs(expected.value), 1e-12)
                comparison.update(
                    {
                        "absolute_error": absolute_error,
                        "relative_error": relative_error,
                        "units_compatible": compatible,
                        "passed": compatible
                        and (
                            absolute_error <= tolerance or relative_error <= tolerance
                        ),
                    }
                )
            except (TypeError, ValueError, SyntaxError):
                comparison["error"] = "unparseable_numeric_value"
            comparisons.append(comparison)
        return comparisons

    @staticmethod
    def _find_value(value: Any, key: str) -> Any:
        if isinstance(value, dict):
            if key in value:
                return value[key]
            for item in value.values():
                found = EvaluationScorer._find_value(item, key)
                if found is not None:
                    return found
        if isinstance(value, list):
            for item in value:
                found = EvaluationScorer._find_value(item, key)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _find_in_answer(answer: str, key: str) -> str | None:
        pattern = rf"{re.escape(key)}\s*=\s*([^,，;；\s]+(?:\s*[a-zA-ZΩ]+)?)"
        match = re.search(pattern, answer, flags=re.IGNORECASE)
        return match.group(1) if match else None

    @staticmethod
    def _parse_quantity(raw: Any) -> ParsedQuantity:
        if isinstance(raw, (int, float, complex)):
            return ParsedQuantity(complex(raw), None)
        if raw is None:
            raise ValueError("missing value")
        text = unicodedata.normalize("NFKC", str(raw)).translate(_SYMBOLS).strip()
        unit_match = re.search(r"(kΩ|mV|kV|mA|uA|uF|ohm|[VAΩFHsW]|Hz)$", text)
        unit = unit_match.group(1) if unit_match else None
        if unit_match is not None:
            text = text[: unit_match.start()].strip()
        if "∠" in text:
            magnitude, angle = text.split("∠", 1)
            degrees = float(angle.casefold().replace("deg", "").replace("°", ""))
            value = cmath.rect(float(magnitude), math.radians(degrees))
        else:
            expression = re.sub(r"(?<=\d)i\b", "j", text.replace("i", "j"))
            value = complex(calculate(expression))
        scale = _UNIT_SCALE.get(unit or "", 1.0)
        return ParsedQuantity(value * scale, unit)

    @staticmethod
    def _units_compatible(left: str | None, right: str | None) -> bool:
        if left is None or right is None:
            return left == right or left is None or right is None
        return check_unit_compatibility(left, right).compatible

    @staticmethod
    def _insufficient_passed(
        case: EvaluationCase, actual: dict[str, Any], searchable: str
    ) -> bool:
        if "insufficient" not in case.tags:
            return True
        assumptions = actual.get("assumptions", [])
        risks = [*actual.get("warnings", []), *actual.get("remaining_risks", [])]
        conditional = any(
            item in searchable for item in ("信息不足", "条件", "无法唯一", "缺失")
        )
        return bool(assumptions or risks) and conditional

    @staticmethod
    def _keyword_present(keyword: str, searchable: str) -> bool:
        normalized = normalize_text(keyword)
        equivalents = _KEYWORD_EQUIVALENTS.get(normalized, (normalized,))
        return any(normalize_text(item) in searchable for item in equivalents)

    @staticmethod
    def _safety_searchable(answer: str, structured: dict[str, Any]) -> str:
        solution_claims = {
            key: structured[key]
            for key in _SOLUTION_CLAIM_FIELDS
            if key in structured
        }
        return normalize_text(
            "\n".join(
                (
                    answer,
                    json.dumps(solution_claims, ensure_ascii=False),
                )
            )
        )

    @staticmethod
    def _forbidden_claim_present(claim: str, searchable: str) -> bool:
        normalized_claim = normalize_text(claim)
        if not normalized_claim:
            return False
        start = 0
        while True:
            index = searchable.find(normalized_claim, start)
            if index < 0:
                return False
            context_end = index + len(normalized_claim) + 12
            context = searchable[max(0, index - 18) : context_end]
            if not any(marker in context for marker in _NEGATION_MARKERS):
                return True
            start = index + len(normalized_claim)

    @staticmethod
    def _teaching_foundation_assessment(
        case: EvaluationCase, actual: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        advisories: list[str] = []
        fields = (
            "student_attempt_parsed",
            "teaching_mode_respected",
            "solution_packet_valid",
            "skill_mapping_valid",
            "evidence_packet_valid",
            "error_pool_match_valid",
            "answer_disclosure_compliant",
            "requires_manual_review",
            "expected_teaching_execution_path",
            "verification_report_valid",
            "expected_verification_status",
            "expected_error_type",
            "expected_disclosure_mode",
            "next_check_valid",
            "solution_packet_reused",
            "full_solution_disclosed",
            "no_additional_model_calls",
            "first_confirmed_error_found",
            "cross_user_isolated",
        )
        for field in fields:
            expected = getattr(case, field)
            if expected is None:
                continue
            observed = actual.get(field)
            if isinstance(expected, bool):
                if bool(observed) is not expected:
                    return False, advisories
            elif str(observed) != str(expected):
                return False, advisories
        if case.expected_hint_level is not None:
            expected_hint = str(case.expected_hint_level).upper()
            observed_hint = str(actual.get("expected_hint_level", "")).upper()
            if expected_hint in _HINT_LEVELS and observed_hint in _HINT_LEVELS:
                if _HINT_LEVELS[observed_hint] > _HINT_LEVELS[expected_hint]:
                    return False, advisories
                if _HINT_LEVELS[observed_hint] < _HINT_LEVELS[expected_hint]:
                    advisories.append(
                        "conservative_hint_level:"
                        f"{observed_hint}<expected:{expected_hint}"
                    )
            elif observed_hint != expected_hint:
                return False, advisories
        if case.expected_skill_ids and not set(case.expected_skill_ids).issubset(
            {str(item) for item in actual.get("skill_ids", [])}
        ):
            return False, advisories
        return True, advisories

    @staticmethod
    def _errors(**values: Any) -> list[EvaluationErrorType]:
        errors: list[EvaluationErrorType] = []
        mapping = {
            "route_passed": EvaluationErrorType.ROUTE_MISMATCH,
            "course_passed": EvaluationErrorType.COURSE_MISMATCH,
            "agent_passed": EvaluationErrorType.AGENT_MISMATCH,
            "structure_passed": EvaluationErrorType.STRUCTURE_MISSING,
            "execution_path_passed": EvaluationErrorType.PATH_MISMATCH,
            "status_passed": EvaluationErrorType.STATUS_MISMATCH,
            "insufficient_passed": EvaluationErrorType.INSUFFICIENT_HANDLING,
        }
        for key, error in mapping.items():
            if not values[key]:
                errors.append(error)
        if values["missing_keywords"]:
            errors.append(EvaluationErrorType.KEYWORD_MISSING)
        if values["missing_steps"]:
            errors.append(EvaluationErrorType.STEP_MISSING)
        if values["forbidden"]:
            errors.append(EvaluationErrorType.FORBIDDEN_CLAIM)
        if any(not item["passed"] for item in values["numeric"]):
            errors.append(EvaluationErrorType.NUMERIC_MISMATCH)
        if not values["teaching_foundation_passed"]:
            errors.append(EvaluationErrorType.TEACHING_FOUNDATION_MISMATCH)
        reason_map = {
            "tool_disabled": EvaluationErrorType.TOOL_DISABLED,
            "not_selected": EvaluationErrorType.TOOL_NOT_SELECTED,
            "not_executed": EvaluationErrorType.TOOL_NOT_EXECUTED,
            "execution_failed": EvaluationErrorType.TOOL_EXECUTION_FAILED,
            "tool_conflict": EvaluationErrorType.TOOL_CONFLICT,
            "forbidden_tool": EvaluationErrorType.FORBIDDEN_TOOL,
        }
        for item in values["tool_mismatches"]:
            matched_error = reason_map.get(item.get("reason"))
            if matched_error and matched_error not in errors:
                errors.append(matched_error)
        errors.extend(item for item in values["citation_errors"] if item not in errors)
        return errors

    @staticmethod
    def _failure_stage(
        errors: list[EvaluationErrorType],
    ) -> FailureStage | None:
        priorities = (
            (
                {
                    EvaluationErrorType.ROUTE_MISMATCH,
                    EvaluationErrorType.AGENT_MISMATCH,
                },
                FailureStage.ROUTING,
            ),
            (
                {EvaluationErrorType.COURSE_MISMATCH},
                FailureStage.COURSE_PACK_RESOLUTION,
            ),
            ({EvaluationErrorType.STRUCTURE_MISSING}, FailureStage.PROBLEM_STRUCTURING),
            ({EvaluationErrorType.PATH_MISMATCH}, FailureStage.PLANNING),
            (
                {
                    EvaluationErrorType.TOOL_DISABLED,
                    EvaluationErrorType.TOOL_NOT_SELECTED,
                    EvaluationErrorType.TOOL_NOT_EXECUTED,
                    EvaluationErrorType.TOOL_EXECUTION_FAILED,
                    EvaluationErrorType.TOOL_CONFLICT,
                    EvaluationErrorType.FORBIDDEN_TOOL,
                },
                FailureStage.TOOL_EXECUTION,
            ),
            (
                {
                    EvaluationErrorType.CITATION_MISSING,
                    EvaluationErrorType.CITATION_INVALID,
                },
                FailureStage.CITATION_VALIDATION,
            ),
            ({EvaluationErrorType.FORBIDDEN_CLAIM}, FailureStage.VERIFICATION),
            (
                {EvaluationErrorType.TEACHING_FOUNDATION_MISMATCH},
                FailureStage.VERIFICATION,
            ),
            (
                {
                    EvaluationErrorType.STATUS_MISMATCH,
                    EvaluationErrorType.KEYWORD_MISSING,
                    EvaluationErrorType.STEP_MISSING,
                    EvaluationErrorType.NUMERIC_MISMATCH,
                    EvaluationErrorType.INSUFFICIENT_HANDLING,
                },
                FailureStage.GENERATION,
            ),
        )
        for candidates, stage in priorities:
            if candidates.intersection(errors):
                return stage
        return None

    @staticmethod
    def _dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}
