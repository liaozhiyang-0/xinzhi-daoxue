from __future__ import annotations

import re
from time import perf_counter
from typing import Any

from app.contracts import (
    AcademicProblem,
    SolutionPacketV1,
    StepVerificationStatus,
    StepVerificationV1,
    StudentAttempt,
    StudentErrorType,
    VerificationReportV1,
)
from app.services.academic_review import AcademicReviewService

NUMBER_RE = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?")
UNIT_RE = re.compile(
    r"(?<![A-Za-z])(?:V|A|Ω|ohm|W|F|H|Hz|ms|s)(?![A-Za-z])",
    re.IGNORECASE,
)
SUPPORTED_SCOPE = [
    "final_numeric_value",
    "unit_presence",
    "unit_compatibility",
    "explicit_sign_or_direction",
    "limited_course_conditions",
    "xor_xnor_confusion",
    "finite_first_error_rules",
]
MANUAL_WARNING = (
    "当前只确认有限范围内的明确差异；复杂推导、多种合法路径或省略步骤需要人工复核。"
)


class StudentVerificationService:
    """Finite deterministic checks; it never claims universal first-error detection."""

    def verify(
        self,
        attempt: StudentAttempt,
        packet: SolutionPacketV1,
    ) -> tuple[VerificationReportV1, float]:
        started = perf_counter()
        answer = self._attempt_text(attempt)
        reference = self._reference_text(packet)
        student_step_id = self._student_step_id(attempt)
        matched_step_id = packet.steps[0].step_id if packet.steps else None
        skill_ids = list(packet.skill_ids)

        confirmed = self._step_rule(
            attempt,
            packet,
            reference,
            skill_ids=skill_ids,
        )
        if confirmed is None:
            confirmed = self._course_rule(
                answer,
                packet,
                student_step_id=student_step_id,
                matched_step_id=matched_step_id,
                skill_ids=skill_ids,
            )
        if confirmed is None:
            confirmed = self._numeric_or_unit_rule(
                answer,
                reference,
                packet,
                student_step_id=student_step_id,
                matched_step_id=matched_step_id,
                skill_ids=skill_ids,
            )
        if confirmed is not None:
            report = VerificationReportV1(
                overall_status="verified_incorrect",
                supported_scope=SUPPORTED_SCOPE,
                step_results=[confirmed],
                first_confirmed_error_step=confirmed.student_step_id,
                manual_review_required=False,
                verified_final_answer=False,
                warnings=[],
            )
            return report, (perf_counter() - started) * 1000

        correct = self._verified_correct(answer, reference, packet)
        if correct:
            step = StepVerificationV1(
                student_step_id=student_step_id,
                matched_solution_step_id=matched_step_id,
                skill_ids=skill_ids,
                status=StepVerificationStatus.VERIFIED_CORRECT,
                message="当前可验证的最终数值和单位与标准解一致。",
                confidence=0.98,
                verification_method="deterministic_numeric_unit",
            )
            report = VerificationReportV1(
                overall_status="verified_correct",
                supported_scope=SUPPORTED_SCOPE,
                step_results=[step],
                manual_review_required=bool(attempt.steps),
                verified_final_answer=True,
                warnings=([MANUAL_WARNING] if attempt.steps else []),
            )
            return report, (perf_counter() - started) * 1000

        step = StepVerificationV1(
            student_step_id=student_step_id,
            matched_solution_step_id=matched_step_id,
            skill_ids=skill_ids,
            status=StepVerificationStatus.MANUAL_REVIEW,
            error_type=StudentErrorType.UNKNOWN,
            message="现有确定性规则无法可靠判断这段推导。",
            confidence=None,
            verification_method="scope_guard",
        )
        report = VerificationReportV1(
            overall_status="manual_review",
            supported_scope=SUPPORTED_SCOPE,
            step_results=[step],
            manual_review_required=True,
            verified_final_answer=None,
            warnings=[MANUAL_WARNING],
        )
        return report, (perf_counter() - started) * 1000

    def _numeric_or_unit_rule(
        self,
        answer: str,
        reference: str,
        packet: SolutionPacketV1,
        *,
        student_step_id: str,
        matched_step_id: str | None,
        skill_ids: list[str],
    ) -> StepVerificationV1 | None:
        expected_units = {
            item.casefold() for item in packet.units if item.strip()
        }
        actual_units = {item.casefold() for item in UNIT_RE.findall(answer)}
        expected_numbers = NUMBER_RE.findall(reference)
        actual_numbers = NUMBER_RE.findall(answer)
        if not actual_numbers:
            return None
        if expected_units and not actual_units:
            return self._incorrect(
                student_step_id,
                matched_step_id,
                skill_ids,
                StudentErrorType.UNIT_MISSING,
                "最终结果缺少目标物理量单位。",
                "unit_missing",
                "deterministic_unit_presence",
                {"expected_units": sorted(expected_units)},
            )
        if expected_units and not expected_units.intersection(actual_units):
            return self._incorrect(
                student_step_id,
                matched_step_id,
                skill_ids,
                StudentErrorType.UNIT_INCOMPATIBLE,
                "最终结果的单位与目标单位不兼容。",
                "unit_incompatible",
                "deterministic_unit_compatibility",
                {
                    "expected_units": sorted(expected_units),
                    "student_units": sorted(actual_units),
                },
            )
        if expected_numbers and actual_numbers:
            expected = {float(item) for item in expected_numbers}
            actual = {float(item) for item in actual_numbers}
            if expected.intersection(actual):
                return None
            if any(-item in actual for item in expected if item != 0):
                return self._incorrect(
                    student_step_id,
                    matched_step_id,
                    skill_ids,
                    StudentErrorType.SIGN_ERROR,
                    "数值大小一致，但正负号与标准结果相反。",
                    "reference_direction_error",
                    "deterministic_sign_comparison",
                    {
                        "expected_numbers": sorted(expected),
                        "student_numbers": sorted(actual),
                    },
                )
            return self._incorrect(
                student_step_id,
                matched_step_id,
                skill_ids,
                StudentErrorType.NUMERIC_ERROR,
                "最终数值与标准结果不一致。",
                None,
                "deterministic_numeric_comparison",
                {
                    "expected_numbers": sorted(expected),
                    "student_numbers": sorted(actual),
                },
            )
        return None

    def _step_rule(
        self,
        attempt: StudentAttempt,
        packet: SolutionPacketV1,
        reference: str,
        *,
        skill_ids: list[str],
    ) -> StepVerificationV1 | None:
        if not attempt.steps:
            return None
        problem = AcademicProblem(
            course=packet.course_id,
            problem_type=packet.problem_type,
            problem_text=packet.problem_summary,
        )
        error_map = {
            "sign": StudentErrorType.SIGN_ERROR,
            "formula": StudentErrorType.FORMULA_MISMATCH,
            "logic": StudentErrorType.BOOLEAN_INEQUIVALENCE,
            "condition": StudentErrorType.CONDITION_MISSING,
            "calculation": StudentErrorType.NUMERIC_ERROR,
            "unit": StudentErrorType.UNIT_INCOMPATIBLE,
        }
        for index, step in enumerate(attempt.steps):
            content = " ".join(
                item
                for item in (
                    step.content,
                    step.expression or "",
                    step.claimed_result or "",
                )
                if item
            )
            rule = AcademicReviewService.detect_rule(
                problem,
                content,
                reference,
            )
            if rule is None:
                continue
            student_step_id = step.step_id or f"student-S{step.sequence or index + 1}"
            matched_step_id = (
                packet.steps[index].step_id if index < len(packet.steps) else None
            )
            error_type = error_map.get(rule.error_type, StudentErrorType.UNKNOWN)
            repair_key = {
                StudentErrorType.SIGN_ERROR: "reference_direction_error",
                StudentErrorType.BOOLEAN_INEQUIVALENCE: "xnor_xor_confusion",
            }.get(error_type)
            return self._incorrect(
                student_step_id,
                matched_step_id,
                skill_ids,
                error_type,
                rule.reason,
                repair_key,
                "deterministic_first_error_rule",
                {"corrected_step": rule.correction},
            )
        return None

    def _course_rule(
        self,
        answer: str,
        packet: SolutionPacketV1,
        *,
        student_step_id: str,
        matched_step_id: str | None,
        skill_ids: list[str],
    ) -> StepVerificationV1 | None:
        compact = answer.replace(" ", "")
        if (
            packet.course_id == "CT"
            and packet.problem_type == "first_order"
            and any(
                marker in compact
                for marker in ("电容电压可以突变", "电容电压会突变")
            )
        ):
            return self._incorrect(
                student_step_id,
                matched_step_id,
                skill_ids,
                StudentErrorType.CONDITION_MISSING,
                "换路瞬间的电容电压连续性条件使用错误。",
                "capacitor_voltage_continuity",
                "deterministic_phrase_rule",
            )
        if (
            packet.course_id == "AE"
            and packet.problem_type == "op_amp"
            and any(marker in answer for marker in ("虚短", "虚断"))
            and not any(marker in answer for marker in ("负反馈", "线性", "理想运放"))
        ):
            return self._incorrect(
                student_step_id,
                matched_step_id,
                skill_ids,
                StudentErrorType.CONDITION_MISSING,
                "使用虚短或虚断时遗漏了理想运放和线性负反馈条件。",
                "op_amp_assumption_missing",
                "deterministic_condition_rule",
            )
        if packet.course_id == "DE":
            reference = self._reference_text(packet)
            given_text = " ".join(
                str(item.get(key, ""))
                for item in packet.givens
                if isinstance(item, dict)
                for key in ("name", "value", "description")
            )
            expects_xnor = "同或" in reference or "xnor" in given_text.casefold()
            expects_xor = (
                ("异或" in reference or "xor" in given_text.casefold())
                and not expects_xnor
            )
            xor_confused = (
                (expects_xnor and "异或" in answer and "同或" not in answer)
                or (expects_xor and "同或" in answer and "异或" not in answer)
            )
            if xor_confused:
                return self._incorrect(
                    student_step_id,
                    matched_step_id,
                    skill_ids,
                    StudentErrorType.BOOLEAN_INEQUIVALENCE,
                    "同或与异或的输出条件被混淆。",
                    "xnor_xor_confusion",
                    "deterministic_xor_xnor_rule",
                )
        return None

    @staticmethod
    def _incorrect(
        student_step_id: str,
        matched_step_id: str | None,
        skill_ids: list[str],
        error_type: StudentErrorType,
        message: str,
        repair_hint_key: str | None,
        method: str,
        evidence: dict[str, Any] | None = None,
    ) -> StepVerificationV1:
        return StepVerificationV1(
            student_step_id=student_step_id,
            matched_solution_step_id=matched_step_id,
            skill_ids=skill_ids,
            status=StepVerificationStatus.VERIFIED_INCORRECT,
            error_type=error_type,
            message=message,
            repair_hint_key=repair_hint_key,
            confidence=0.98,
            verification_method=method,
            tool_evidence=([evidence] if evidence else []),
        )

    @staticmethod
    def _attempt_text(attempt: StudentAttempt) -> str:
        values = [attempt.raw_text, *(item.content for item in attempt.steps)]
        if attempt.final_answer:
            values.append(attempt.final_answer)
        return "\n".join(item for item in values if item.strip())

    @staticmethod
    def _student_step_id(attempt: StudentAttempt) -> str:
        if attempt.steps:
            sequence = attempt.steps[0].sequence or 1
            return attempt.steps[0].step_id or f"student-S{sequence}"
        return "student-final"

    @staticmethod
    def _reference_text(packet: SolutionPacketV1) -> str:
        value = packet.final_answer
        if isinstance(value, dict):
            parts = [
                str(value.get(key, "")).strip()
                for key in ("value", "unit", "conclusion")
                if str(value.get(key, "")).strip()
            ]
        else:
            parts = [str(value or "").strip()]
        parts.extend(item for item in packet.units if item)
        return " ".join(dict.fromkeys(item for item in parts if item))

    @staticmethod
    def _verified_correct(
        answer: str,
        reference: str,
        packet: SolutionPacketV1,
    ) -> bool:
        expected_numbers = {float(item) for item in NUMBER_RE.findall(reference)}
        actual_numbers = {float(item) for item in NUMBER_RE.findall(answer)}
        if not expected_numbers or not actual_numbers:
            return False
        if not expected_numbers.intersection(actual_numbers):
            return False
        expected_units = {item.casefold() for item in packet.units}
        actual_units = {item.casefold() for item in UNIT_RE.findall(answer)}
        return not expected_units or bool(expected_units.intersection(actual_units))
