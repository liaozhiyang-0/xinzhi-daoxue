from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.learning import (
    FeedbackUptakeStatus,
    FeedbackUptakeV1,
    LearnerKnowledgeState,
    MasteryEvidenceType,
    MasteryEvidenceV1,
    RetestPlanV1,
)
from app.core.errors import ConfigurationError
from app.models.entities import (
    LearnerKnowledgeStateModel,
    PracticeAttemptModel,
    TaskModel,
    TaskStatus,
    utc_now,
)
from app.services.retest_plans import RetestPlanService

DEFAULT_CONFIG = (
    Path(__file__).resolve().parents[4] / "config" / "learning_mastery.yaml"
)


@dataclass
class LearningOutcomeResult:
    evidence: list[MasteryEvidenceV1] = field(default_factory=list)
    mastery: list[LearnerKnowledgeState] = field(default_factory=list)
    retest_plans: list[RetestPlanV1] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


class LearningOutcomeService:
    """Maps observable local evidence to the existing mastery state."""

    def __init__(self, config_path: Path = DEFAULT_CONFIG) -> None:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ConfigurationError("learning_mastery.yaml必须为对象")
        self.config = raw
        self._validate_config()
        self.retests = RetestPlanService(
            {
                str(key): [int(item) for item in value]
                for key, value in dict(raw["retest_intervals"]).items()
            }
        )

    def _validate_config(self) -> None:
        if str(self.config.get("version")) != "2.0":
            raise ConfigurationError("learning_mastery.yaml版本必须为2.0")
        if self.config.get("calibration_status") != "uncalibrated_heuristic":
            raise ConfigurationError("mastery配置必须声明未经统计校准")
        updates = self.config.get("evidence_updates")
        if not isinstance(updates, dict):
            raise ConfigurationError("缺少evidence_updates")
        required = {item.value for item in MasteryEvidenceType}
        missing = required - set(updates)
        if missing:
            raise ConfigurationError(f"mastery配置缺少证据规则: {sorted(missing)}")
        for key, value in updates.items():
            if not isinstance(value, dict):
                raise ConfigurationError(f"{key}证据规则必须为对象")
            delta = float(value.get("delta", 2))
            confidence_delta = float(value.get("confidence_delta", 2))
            if not -1 <= delta <= 1 or not -1 <= confidence_delta <= 1:
                raise ConfigurationError(f"{key}证据规则超出[-1, 1]")
        for field_name in ("score_bounds", "confidence_bounds"):
            bounds = self.config.get(field_name)
            if not isinstance(bounds, dict):
                raise ConfigurationError(f"缺少{field_name}")
            minimum = float(bounds.get("minimum", 1))
            maximum = float(bounds.get("maximum", 0))
            if minimum < 0 or maximum > 1 or minimum >= maximum:
                raise ConfigurationError(f"{field_name}无效")

    async def process_attempt(
        self,
        session: AsyncSession,
        *,
        task: TaskModel,
        attempt: PracticeAttemptModel,
        skill_ids: list[str],
        uptake: FeedbackUptakeV1 | None = None,
        retest_result: str | None = None,
        retest_plan_source_task_id: str | None = None,
    ) -> LearningOutcomeResult:
        started = perf_counter()
        if (
            task.status != TaskStatus.COMPLETED
            or task.cancellation_requested
            or task.user_id != attempt.user_id
            or task.id != attempt.source_task_id
        ):
            return LearningOutcomeResult(
                metrics={
                    "mastery_update_ms": (perf_counter() - started) * 1000,
                    "retest_plans_created": 0,
                }
            )
        stable_skills = list(
            dict.fromkeys(item.strip()[:255] for item in skill_ids if item.strip())
        )
        if not stable_skills:
            return LearningOutcomeResult(
                metrics={
                    "mastery_update_ms": (perf_counter() - started) * 1000,
                    "retest_plans_created": 0,
                }
            )

        evidence_type = self._evidence_type(
            attempt, uptake=uptake, retest_result=retest_result
        )
        rule = dict(self.config["evidence_updates"][evidence_type.value])
        delta = float(rule["delta"])
        confidence_delta = float(rule["confidence_delta"])
        verified = evidence_type not in {
            MasteryEvidenceType.MANUAL_REVIEW,
            MasteryEvidenceType.FULL_SOLUTION_SEEN,
        }
        now = utc_now()
        evidence: list[MasteryEvidenceV1] = []
        mastery: list[LearnerKnowledgeState] = []
        plans: list[RetestPlanV1] = []
        for skill_id in stable_skills:
            item = MasteryEvidenceV1(
                evidence_id=uuid4().hex,
                user_id=attempt.user_id,
                skill_id=skill_id,
                source_task_id=task.id,
                attempt_id=attempt.id,
                evidence_type=evidence_type,
                verified=verified,
                evidence_strength=self._strength(evidence_type),
                mastery_delta=delta,
                reason_code=evidence_type.value,
                created_at=now,
            )
            evidence.append(item)
            state = await self._apply_evidence(
                session,
                task=task,
                evidence=item,
                confidence_delta=confidence_delta,
            )
            mastery.append(self._state_contract(state))
            rows = await self.retests.create_for_evidence(
                session,
                user_id=attempt.user_id,
                skill_id=skill_id,
                source_task_id=retest_plan_source_task_id or task.id,
                source_attempt_id=attempt.id,
                evidence_type=evidence_type,
                now=now,
            )
            plans.extend(self.retests.to_contract(row, now=now) for row in rows)
        attempt.mastery_evidence = [item.model_dump(mode="json") for item in evidence]
        await session.flush()
        return LearningOutcomeResult(
            evidence=evidence,
            mastery=mastery,
            retest_plans=plans,
            metrics={
                "mastery_evidence_type": evidence_type.value,
                "mastery_delta": delta,
                "mastery_update_ms": (perf_counter() - started) * 1000,
                "retest_plans_created": len(plans),
                "full_solution_seen": attempt.full_solution_seen,
            },
        )

    @staticmethod
    def _evidence_type(
        attempt: PracticeAttemptModel,
        *,
        uptake: FeedbackUptakeV1 | None,
        retest_result: str | None,
    ) -> MasteryEvidenceType:
        if retest_result == "correct":
            return MasteryEvidenceType.DELAYED_RETEST_CORRECT
        if retest_result == "incorrect":
            return MasteryEvidenceType.DELAYED_RETEST_INCORRECT
        if attempt.full_solution_seen:
            return MasteryEvidenceType.FULL_SOLUTION_SEEN
        if attempt.verification_status == "manual_review":
            return MasteryEvidenceType.MANUAL_REVIEW
        if uptake is not None:
            if uptake.status == FeedbackUptakeStatus.APPLIED_CORRECTLY:
                return MasteryEvidenceType.FEEDBACK_APPLIED_CORRECTLY
            if uptake.status == FeedbackUptakeStatus.NOT_APPLIED:
                return MasteryEvidenceType.FEEDBACK_NOT_APPLIED
            if uptake.status in {
                FeedbackUptakeStatus.INDETERMINATE,
                FeedbackUptakeStatus.NOT_APPLICABLE,
                FeedbackUptakeStatus.PARTIALLY_APPLIED,
            }:
                return MasteryEvidenceType.MANUAL_REVIEW
        if attempt.verification_status == "verified_incorrect":
            return MasteryEvidenceType.VERIFIED_ERROR
        if attempt.verification_status == "verified_correct":
            if attempt.hint_level_used == "H2":
                return MasteryEvidenceType.H2_CORRECT
            if attempt.hint_level_used in {"H0", "H1"}:
                return MasteryEvidenceType.H0_H1_CORRECT
            return MasteryEvidenceType.INDEPENDENT_CORRECT
        return MasteryEvidenceType.MANUAL_REVIEW

    async def _apply_evidence(
        self,
        session: AsyncSession,
        *,
        task: TaskModel,
        evidence: MasteryEvidenceV1,
        confidence_delta: float,
    ) -> LearnerKnowledgeStateModel:
        state = await session.scalar(
            select(LearnerKnowledgeStateModel).where(
                LearnerKnowledgeStateModel.user_id == evidence.user_id,
                LearnerKnowledgeStateModel.course_id == task.course_id,
                LearnerKnowledgeStateModel.knowledge_point == evidence.skill_id,
            )
        )
        if state is None:
            state = LearnerKnowledgeStateModel(
                user_id=evidence.user_id,
                course_id=task.course_id,
                knowledge_point=evidence.skill_id,
                mastery_score=float(self.config["initial_score"]),
                confidence=float(self.config["initial_confidence"]),
                correct_count=0,
                incorrect_count=0,
                hint_count=0,
                evidence={},
            )
            session.add(state)
        score_bounds = dict(self.config["score_bounds"])
        confidence_bounds = dict(self.config["confidence_bounds"])
        state.mastery_score = max(
            float(score_bounds["minimum"]),
            min(
                float(score_bounds["maximum"]),
                state.mastery_score + evidence.mastery_delta,
            ),
        )
        state.confidence = max(
            float(confidence_bounds["minimum"]),
            min(
                float(confidence_bounds["maximum"]),
                state.confidence + confidence_delta,
            ),
        )
        if evidence.mastery_delta > 0:
            state.correct_count += 1
        elif evidence.mastery_delta < 0:
            state.incorrect_count += 1
        if evidence.evidence_type in {
            MasteryEvidenceType.H0_H1_CORRECT,
            MasteryEvidenceType.H2_CORRECT,
            MasteryEvidenceType.FEEDBACK_APPLIED_CORRECTLY,
            MasteryEvidenceType.FEEDBACK_NOT_APPLIED,
        }:
            state.hint_count += 1
        history = list(state.evidence.get("history", []))
        history.append(evidence.model_dump(mode="json"))
        state.evidence = {
            "policy_version": str(self.config["version"]),
            "calibration_status": self.config["calibration_status"],
            "last_outcome": evidence.evidence_type.value,
            "history": history[-50:],
        }
        state.updated_at = utc_now()
        await session.flush()
        return state

    @staticmethod
    def _strength(evidence_type: MasteryEvidenceType) -> float:
        if evidence_type in {
            MasteryEvidenceType.INDEPENDENT_CORRECT,
            MasteryEvidenceType.VERIFIED_ERROR,
            MasteryEvidenceType.DELAYED_RETEST_CORRECT,
            MasteryEvidenceType.DELAYED_RETEST_INCORRECT,
        }:
            return 1.0
        if evidence_type == MasteryEvidenceType.MANUAL_REVIEW:
            return 0.0
        return 0.7

    @staticmethod
    def _state_contract(
        item: LearnerKnowledgeStateModel,
    ) -> LearnerKnowledgeState:
        return LearnerKnowledgeState(
            course_id=item.course_id,
            knowledge_point=item.knowledge_point,
            mastery_score=item.mastery_score,
            confidence=item.confidence,
            correct_count=item.correct_count,
            incorrect_count=item.incorrect_count,
            hint_count=item.hint_count,
        )
