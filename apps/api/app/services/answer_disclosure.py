from __future__ import annotations

from copy import deepcopy
from time import perf_counter
from typing import Any

from app.contracts import (
    AgentResult,
    AnswerDisclosureMode,
    AnswerDisclosurePolicyV1,
    HintDecisionV1,
    NextCheckQuestionV1,
    TeachingMode,
    VerificationReportV1,
)

INTERNAL_TEACHING_KEY = "_teaching_internal"
SENSITIVE_STRUCTURED_FIELDS = frozenset(
    {
        "final_answer",
        "final_answer_detail",
        "solution_steps",
        "intermediate_results",
        "key_equations",
        "tool_verification",
        "verification_report",
        "patches",
    }
)


class AnswerDisclosureService:
    """Backend-enforced output filtering for guided/check modes."""

    @staticmethod
    def policy(mode: TeachingMode) -> AnswerDisclosurePolicyV1:
        if mode == TeachingMode.GUIDED_LEARNING:
            return AnswerDisclosurePolicyV1(
                mode=AnswerDisclosureMode.NEXT_STEP_ONLY,
                maximum_hint_level="H2",
                reveal_final_answer=False,
                reveal_intermediate_results=False,
                reveal_complete_solution_packet=False,
                source="phase2_default_policy",
            )
        if mode == TeachingMode.CHECK_MY_WORK:
            return AnswerDisclosurePolicyV1(
                mode=AnswerDisclosureMode.WITHHOLD_FINAL,
                maximum_hint_level="H2",
                reveal_final_answer=False,
                reveal_intermediate_results=False,
                reveal_complete_solution_packet=False,
                source="phase2_default_policy",
            )
        return AnswerDisclosurePolicyV1(
            mode=AnswerDisclosureMode.FULL,
            maximum_hint_level="H5",
            reveal_final_answer=True,
            reveal_intermediate_results=True,
            reveal_complete_solution_packet=True,
            source="direct_answer_compatibility",
        )

    def apply(
        self,
        result: AgentResult,
        *,
        policy: AnswerDisclosurePolicyV1,
        hint: HintDecisionV1 | None,
        next_check: NextCheckQuestionV1 | None,
        verification: VerificationReportV1 | None,
    ) -> tuple[AgentResult, float]:
        started = perf_counter()
        if policy.mode == AnswerDisclosureMode.FULL:
            return result, (perf_counter() - started) * 1000
        structured = deepcopy(result.structured_result)
        full_packet = deepcopy(structured.get("solution_packet"))
        internal = {
            "full_answer": result.answer,
            "full_math_content": (
                result.math_content.model_dump(mode="json")
                if result.math_content is not None
                else None
            ),
            "full_solution_packet": full_packet,
            "full_structured_fields": {
                key: deepcopy(structured[key])
                for key in SENSITIVE_STRUCTURED_FIELDS
                if key in structured
            },
            "next_check_answer_key": (
                next_check.answer_key_internal if next_check else None
            ),
        }
        for key in SENSITIVE_STRUCTURED_FIELDS:
            structured.pop(key, None)
        if isinstance(full_packet, dict):
            public_packet: dict[str, Any] = {
                key: deepcopy(full_packet.get(key))
                for key in (
                    "version",
                    "course_id",
                    "problem_type",
                    "skill_ids",
                    "mapping_status",
                    "warnings",
                )
            }
            public_packet.update(
                {
                    "givens": [],
                    "targets": [],
                    "assumptions": [],
                    "reference_directions": [],
                    "plan": [],
                    "steps": [],
                    "final_answer": None,
                    "units": [],
                    "common_errors": [],
                    "evidence_refs": [],
                    "tool_outputs": [],
                }
            )
            structured["solution_packet"] = public_packet
        structured[INTERNAL_TEACHING_KEY] = internal
        answer_parts = []
        if verification and verification.manual_review_required:
            answer_parts.append("当前推导需要人工复核；下面只提供受控学习线索。")
        if hint:
            answer_parts.append(f"### {hint.hint_level} 提示\n\n{hint.hint_text}")
        if next_check:
            answer_parts.append(
                f"### 下一步理解检查\n\n{next_check.question_text}"
            )
        answer = "\n\n".join(answer_parts) or "当前暂时无法生成可靠提示。"
        artifacts = []
        for artifact in result.artifacts:
            content = dict(artifact.content)
            for key in ("answer", "answer_text", "final_answer"):
                content.pop(key, None)
            artifacts.append(artifact.model_copy(update={"content": content}))
        filtered = result.model_copy(
            update={
                "answer": answer,
                "math_content": None,
                "structured_result": structured,
                "artifacts": artifacts,
            }
        )
        return filtered, (perf_counter() - started) * 1000


def public_teaching_result(
    result_content: dict[str, Any] | None,
    *,
    include_private_teaching: bool = False,
) -> dict[str, Any] | None:
    """Remove protected teaching payloads from ordinary API responses."""

    if result_content is None:
        return None
    output = deepcopy(result_content)
    structured = output.get("structured_result")
    if isinstance(structured, dict):
        structured.pop(INTERNAL_TEACHING_KEY, None)
        if not include_private_teaching:
            structured.pop("verification_report_v1", None)
            structured.pop("student_attempt_review", None)
            loop = structured.get("teaching_loop")
            if isinstance(loop, dict):
                loop.pop("verification", None)
    return output
