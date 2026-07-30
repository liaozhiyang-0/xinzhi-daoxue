from __future__ import annotations

from time import perf_counter
from typing import Literal

from app.contracts import (
    HintDecisionV1,
    SolutionPacketV1,
    TeachingMode,
    VerificationReportV1,
)
from app.services.error_pool import ErrorPoolRegistry
from app.services.skill_registry import SkillRegistry


class HintPolicyService:
    """Rule/template H0-H2 hints with a hard disclosure ceiling."""

    def __init__(
        self,
        error_pool: ErrorPoolRegistry,
        skills: SkillRegistry,
    ) -> None:
        self.error_pool = error_pool
        self.skills = skills

    def decide(
        self,
        *,
        mode: TeachingMode,
        packet: SolutionPacketV1,
        report: VerificationReportV1 | None,
        hint_request_count: int,
    ) -> tuple[HintDecisionV1, float]:
        started = perf_counter()
        level: Literal["H0", "H1", "H2"] = (
            "H2" if hint_request_count > 0 else "H1"
        )
        target_step = (
            report.first_confirmed_error_step
            if report and report.first_confirmed_error_step
            else packet.steps[0].step_id
            if packet.steps
            else None
        )
        target_skills = (
            report.step_results[0].skill_ids
            if report and report.step_results
            else packet.skill_ids
        )
        hint_text = ""
        source = ""
        repair_key = (
            report.step_results[0].repair_hint_key
            if report and report.step_results
            else None
        )
        if repair_key:
            match = self.error_pool.lookup(
                course_id=packet.course_id,
                problem_type=packet.problem_type or "unknown",
                skill_ids=target_skills,
                error_signature=repair_key,
            )
            if match.status == "matched":
                hint_text = match.hint_templates.get(level, "")
                source = match.hint_template_ids.get(level, "")
        if not hint_text and level == "H1" and target_skills:
            try:
                skill = self.skills.get(target_skills[0])
                hint_text = f"先回到「{skill.title}」检查本步使用的条件和方向。"
                source = f"skill:{skill.skill_id}"
            except KeyError:
                pass
        if not hint_text and level == "H2" and packet.steps:
            step = packet.steps[0]
            hint_text = f"下一步先完成「{step.title}」，并写出所依据的关系。"
            source = f"solution_step:{step.step_id}"
            target_step = step.step_id
        if not hint_text:
            level = "H0"
            hint_text = (
                "你准备先检查哪个已知条件、参考方向或基本关系？"
                if mode == TeachingMode.GUIDED_LEARNING
                else "请指出你最不确定的那一步，以及它使用的条件。"
            )
            source = "controlled_template:H0"
        decision = HintDecisionV1(
            hint_level=level,
            target_skill_ids=target_skills,
            target_step_id=target_step,
            hint_text=hint_text,
            source=source,
            disclosure_checked=True,
            next_action=(
                "submit_check_response"
                if mode == TeachingMode.GUIDED_LEARNING
                else "revise_student_attempt"
            ),
        )
        return decision, (perf_counter() - started) * 1000
