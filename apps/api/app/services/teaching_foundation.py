from __future__ import annotations

from time import perf_counter
from typing import Any

from app.contracts import (
    AgentRequest,
    AgentResult,
    RetrievalContextPacket,
    StudentAttempt,
    TeachingMode,
    TeachingStateV1,
    VerificationReportV1,
)
from app.services.answer_disclosure import AnswerDisclosureService
from app.services.error_pool import ErrorPoolRegistry
from app.services.evidence_packet_adapter import EvidencePacketAdapterService
from app.services.hint_policy import HintPolicyService
from app.services.next_check_question import NextCheckQuestionService
from app.services.solution_packet_adapter import SolutionPacketAdapterService
from app.services.student_answer_review import StudentAnswerReviewService
from app.services.student_verification import StudentVerificationService
from app.services.teaching_execution_planner import TeachingExecutionPlanner
from app.services.teaching_input import teaching_mode_status

DIAGNOSTIC_SCOPE_WARNING = (
    "当前检查对明确数值、单位和参考方向较可靠；复杂推导可能需要人工复核。"
)


class TeachingFoundationService:
    """Local-only teaching adapters; never calls a model, solver, or retriever."""

    def __init__(
        self,
        solution_packets: SolutionPacketAdapterService,
        evidence_packets: EvidencePacketAdapterService,
        error_pool: ErrorPoolRegistry,
        planner: TeachingExecutionPlanner,
        verifier: StudentVerificationService,
        hints: HintPolicyService,
        next_checks: NextCheckQuestionService,
        disclosure: AnswerDisclosureService,
    ) -> None:
        self.solution_packets = solution_packets
        self.evidence_packets = evidence_packets
        self.error_pool = error_pool
        self.planner = planner
        self.verifier = verifier
        self.hints = hints
        self.next_checks = next_checks
        self.disclosure = disclosure
        self.answer_review = StudentAnswerReviewService()

    def enrich(
        self,
        result: AgentResult,
        request: AgentRequest,
        retrieval_packet: RetrievalContextPacket | None,
        *,
        query: str,
    ) -> AgentResult:
        mode = TeachingMode(
            str(request.options.get("teaching_mode", TeachingMode.DIRECT_ANSWER))
        )
        attempt = self._attempt(request.options.get("student_attempt"))
        mode_status, mode_warning = teaching_mode_status(mode)
        structured = dict(result.structured_result)
        existing_state = self._teaching_state(request.options.get("working_state"))
        hint_request_count = (
            existing_state.hint_request_count if existing_state is not None else 0
        )
        plan, planning_ms = self.planner.plan(
            mode=mode,
            course_id=request.course_id,
            attempt=attempt,
            reusable_solution_packet=False,
            state=existing_state,
            original_model_call_budget=int(
                request.options.get("model_call_budget", 1)
            ),
        )

        solution_started = perf_counter()
        solution_packet, skill_mapping = (
            self.solution_packets.from_structured_result(
                structured, course_id=request.course_id
            )
        )
        solution_ms = (perf_counter() - solution_started) * 1000
        if solution_packet is not None:
            structured["solution_packet"] = solution_packet.model_dump(mode="json")

        evidence_started = perf_counter()
        evidence_packet = self.evidence_packets.from_context(
            retrieval_packet,
            query=query,
            course_id=request.course_id,
            applicable_skill_ids=(
                solution_packet.skill_ids if solution_packet is not None else []
            ),
        )
        evidence_ms = (perf_counter() - evidence_started) * 1000
        structured["evidence_packet"] = evidence_packet.model_dump(mode="json")

        teaching: dict[str, Any] = {
            "teaching_mode": mode.value,
            "mode_status": mode_status,
            "warning": mode_warning,
            "student_attempt_present": attempt is not None,
            # Business agents may already require review (for example,
            # research analysis or academic writing).  Teaching enrichment is
            # a presentation layer and must not clear that upstream gate.
            "requires_manual_review": result.metrics.manual_review_required,
            "diagnostic_scope": DIAGNOSTIC_SCOPE_WARNING,
        }
        error_lookup_ms = 0.0
        verification: VerificationReportV1 | None = None
        verification_ms = 0.0
        if mode == TeachingMode.CHECK_MY_WORK:
            if attempt is None:
                teaching["warning"] = "检查模式需要提供文字 StudentAttempt。"
                teaching["requires_manual_review"] = True
            elif solution_packet is None:
                teaching["warning"] = "当前结果无法形成可复用标准解包。"
                teaching["requires_manual_review"] = True
            else:
                verification, verification_ms = self.verifier.verify(
                    attempt,
                    solution_packet,
                )
                structured["verification_report_v1"] = verification.model_dump(
                    mode="json"
                )
                review = self.answer_review.review(
                    self._attempt_text(attempt),
                    reference_answer=self._reference_answer(
                        solution_packet.final_answer,
                        solution_packet.units,
                    ),
                    reference_steps=list(structured.get("solution_steps") or []),
                )
                structured["student_attempt_review"] = review.model_dump(mode="json")
                teaching["requires_manual_review"] = bool(
                    teaching["requires_manual_review"]
                    or verification.manual_review_required
                )
                repair_key = next(
                    (
                        item.repair_hint_key
                        for item in verification.step_results
                        if item.repair_hint_key
                    ),
                    None,
                )
                if repair_key:
                    match = self.error_pool.lookup(
                        course_id=request.course_id,
                        problem_type=solution_packet.problem_type or "unknown",
                        skill_ids=solution_packet.skill_ids,
                        error_signature=repair_key,
                    )
                    error_lookup_ms += match.latency_ms
                    if match.status == "matched":
                        structured["error_pool"] = match.model_dump(mode="json")
                if "error_pool" not in structured:
                    structured["error_pool"] = {
                        "status": "no_match",
                        "error_signature": "",
                    }
        hint = None
        hint_ms = 0.0
        next_check = None
        if (
            plan.require_hint
            and solution_packet is not None
            and mode in {TeachingMode.GUIDED_LEARNING, TeachingMode.CHECK_MY_WORK}
        ):
            hint, hint_ms = self.hints.decide(
                mode=mode,
                packet=solution_packet,
                report=verification,
                hint_request_count=hint_request_count,
            )
            next_check = self.next_checks.generate(
                task_id=request.task_id,
                packet=solution_packet,
                hint=hint,
            )
        policy = self.disclosure.policy(mode)
        public_next_check = (
            next_check.model_dump(mode="json", exclude={"answer_key_internal"})
            if next_check is not None
            else None
        )
        teaching_loop = {
            "version": "v1",
            "execution_plan": plan.model_dump(mode="json"),
            "verification": (
                verification.model_dump(mode="json")
                if verification is not None
                else None
            ),
            "hint": hint.model_dump(mode="json") if hint is not None else None,
            "next_check": public_next_check,
            "disclosure_policy": policy.model_dump(mode="json"),
            "hint_request_count": hint_request_count,
            "awaiting_student_response": next_check is not None,
            "solution_packet_reused": False,
        }
        structured["teaching_loop"] = teaching_loop
        structured["teaching"] = teaching
        warnings = list(result.warnings)
        if mode_warning:
            warnings.append(mode_warning)
        if mode == TeachingMode.CHECK_MY_WORK:
            warnings.append(DIAGNOSTIC_SCOPE_WARNING)
        interim = result.model_copy(
            update={
                "structured_result": structured,
                "warnings": list(dict.fromkeys(warnings)),
            }
        )
        filtered, disclosure_ms = self.disclosure.apply(
            interim,
            policy=policy,
            hint=hint,
            next_check=next_check,
            verification=verification,
        )
        metrics = filtered.metrics.model_copy(
            update={
                "solution_packet_build_ms": solution_ms,
                "evidence_packet_build_ms": evidence_ms,
                "skill_mapping_ms": skill_mapping.latency_ms,
                "error_pool_lookup_ms": error_lookup_ms,
                "student_attempt_present": attempt is not None,
                "teaching_mode": mode.value,
                "teaching_execution_path": plan.path.value,
                "solution_packet_reused": False,
                "student_verification_executed": verification is not None,
                "verification_method": self._verification_method(verification),
                "manual_review_required": bool(
                    filtered.metrics.manual_review_required
                    or (verification and verification.manual_review_required)
                ),
                "first_confirmed_error_found": bool(
                    verification and verification.first_confirmed_error_step
                ),
                "hint_level": hint.hint_level if hint else "",
                "hint_source": hint.source if hint else "",
                "hint_request_count": hint_request_count,
                "next_check_generated": next_check is not None,
                "answer_disclosure_mode": policy.mode.value,
                "full_solution_disclosed": policy.reveal_final_answer,
                "teaching_state_restored": existing_state is not None,
                "additional_model_calls": 0,
                "teaching_planning_ms": planning_ms,
                "student_verification_ms": verification_ms,
                "hint_generation_ms": hint_ms,
                "disclosure_filter_ms": disclosure_ms,
            }
        )
        return filtered.model_copy(update={"metrics": metrics})

    @staticmethod
    def _attempt(raw: Any) -> StudentAttempt | None:
        return StudentAttempt.model_validate(raw) if raw is not None else None

    @staticmethod
    def _teaching_state(raw: Any) -> TeachingStateV1 | None:
        if not isinstance(raw, dict):
            return None
        state = raw.get("teaching_state")
        return TeachingStateV1.model_validate(state) if state else None

    @staticmethod
    def _verification_method(report: VerificationReportV1 | None) -> str:
        if report is None or not report.step_results:
            return "not_run"
        return report.step_results[0].verification_method

    @staticmethod
    def _attempt_text(attempt: StudentAttempt) -> str:
        values = [attempt.raw_text, *(item.content for item in attempt.steps)]
        if attempt.final_answer:
            values.append(attempt.final_answer)
        return "\n".join(item for item in values if item.strip())

    @staticmethod
    def _reference_answer(
        value: dict[str, Any] | str | None,
        units: list[str],
    ) -> str:
        if isinstance(value, str):
            parts = [value]
        elif isinstance(value, dict):
            parts = [
                str(value.get(key, "")).strip()
                for key in ("value", "unit", "conclusion")
                if str(value.get(key, "")).strip()
            ]
        else:
            parts = []
        rendered = " ".join(parts)
        rendered_units: list[str] = []
        seen_units: set[str] = set()
        for item in units:
            normalized = item.casefold()
            if (
                not item
                or normalized in rendered.casefold()
                or normalized in seen_units
            ):
                continue
            seen_units.add(normalized)
            rendered_units.append(item)
        return " ".join([rendered, *rendered_units]).strip()
