from __future__ import annotations

import re
from typing import Any, Literal

from app.contracts.learning import AnswerReviewResult

NUMBER_RE = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?")
UNIT_RE = re.compile(r"\b(?:V|A|Ω|ohm|W|F|H|Hz|s|ms)\b", re.IGNORECASE)
EQUATION_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*|[-+*/=]|\d+(?:\.\d+)?")


def _tokens(value: str) -> set[str]:
    return {item.casefold() for item in EQUATION_TOKEN_RE.findall(value)}


class StudentAnswerReviewService:
    """Step-aware review that does not reduce to whole-string equality."""

    def review(
        self,
        student_answer: str,
        *,
        reference_answer: str,
        reference_steps: list[dict[str, Any]] | None = None,
    ) -> AnswerReviewResult:
        answer = student_answer.strip()
        if not answer:
            return AnswerReviewResult(
                status="insufficient",
                first_error={"type": "missing_answer", "location": "student_answer"},
                error_types=["missing_answer"],
                feedback=["请先写出你的推导或最终答案。"],
                mastery_delta=-0.02,
            )

        aligned: list[dict[str, Any]] = []
        answer_tokens = _tokens(answer)
        for index, step in enumerate(reference_steps or [], start=1):
            content = " ".join(str(value) for value in step.values())
            expected = _tokens(content)
            overlap = len(answer_tokens & expected) / max(1, len(expected))
            aligned.append(
                {
                    "reference_step": index,
                    "overlap": round(overlap, 3),
                    "matched": overlap >= 0.35,
                }
            )

        errors: list[str] = []
        feedback: list[str] = []
        first_error: dict[str, Any] | None = None
        reference_numbers = NUMBER_RE.findall(reference_answer)
        student_numbers = NUMBER_RE.findall(answer)
        if reference_numbers and not set(reference_numbers).intersection(
            student_numbers
        ):
            errors.append("calculation")
            first_error = {
                "type": "calculation",
                "location": "first_unmatched_numeric_result",
                "expected_candidates": reference_numbers,
            }
            feedback.append("数值结果与参考推导不一致，请从第一个代入步骤开始复核。")
        reference_units = {
            item.casefold() for item in UNIT_RE.findall(reference_answer)
        }
        student_units = {item.casefold() for item in UNIT_RE.findall(answer)}
        if reference_units and not reference_units.issubset(student_units):
            errors.append("unit")
            first_error = first_error or {
                "type": "unit",
                "location": "final_quantity",
                "expected_units": sorted(reference_units),
            }
            feedback.append("最终量缺少或使用了不一致的单位。")
        if ("方向" in reference_answer or "正" in reference_answer) and not any(
            marker in answer for marker in ("方向", "正", "负", "流向")
        ):
            errors.append("direction")
            first_error = first_error or {
                "type": "direction",
                "location": "reference_convention",
            }
            feedback.append("请明确参考方向或正负号的物理含义。")

        matched_steps = sum(bool(item["matched"]) for item in aligned)
        if not errors and (not aligned or matched_steps == len(aligned)):
            status: Literal[
                "correct", "partially_correct", "incorrect", "insufficient"
            ] = "correct"
            delta = 0.12
            feedback.append("关键步骤、数值和单位与参考结果一致。")
        elif matched_steps or (
            reference_numbers and set(reference_numbers) & set(student_numbers)
        ):
            status = "partially_correct"
            delta = 0.04
        else:
            status = "incorrect"
            delta = -0.10
        return AnswerReviewResult(
            status=status,
            aligned_steps=aligned,
            first_error=first_error,
            error_types=list(dict.fromkeys(errors)),
            feedback=feedback,
            mastery_delta=delta,
        )
