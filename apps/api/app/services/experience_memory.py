from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.experience import (
    ExperienceCandidateCreate,
    ExperienceEvaluationReport,
    ExperienceEvidenceLevel,
    ExperienceInfluence,
    ExperienceLifecycle,
    ExperienceMatch,
    ExperiencePrivacyClass,
    ExperiencePromotionDecision,
    ExperienceRecord,
    ExperienceRedactionStatus,
    ExperienceRetrievalQuery,
    ExperienceScope,
    ExperienceType,
)
from app.models import ExperienceRecordModel
from app.repositories.experience_memory import ExperienceRecordRepository
from app.services.runtime_safety import sanitize_runtime_text

_PRIVATE_KEYS = frozenset(
    {
        "answer",
        "answers",
        "attachment",
        "attachments",
        "content",
        "conversation",
        "email",
        "full_text",
        "message",
        "messages",
        "phone",
        "prompt",
        "raw_answer",
        "raw_content",
        "raw_prompt",
        "student_answer",
        "username",
    }
)
_MIN_ACTIVE_EVIDENCE = {
    ExperienceEvidenceLevel.OFFLINE_REAL_CASE,
    ExperienceEvidenceLevel.REAL_PROVIDER_TEST,
    ExperienceEvidenceLevel.CONTROLLED_CANARY,
    ExperienceEvidenceLevel.PRODUCTION,
}


def _redact(value: Any, *, key: str = "", depth: int = 0) -> Any:
    """Keep structured features while dropping raw user material."""

    if depth > 4 or key.casefold() in _PRIVATE_KEYS:
        return "[omitted]"
    if isinstance(value, str):
        return sanitize_runtime_text(value, max_chars=500)
    if isinstance(value, dict):
        return {
            str(item_key): _redact(item_value, key=str(item_key), depth=depth + 1)
            for item_key, item_value in list(value.items())[:32]
            if str(item_key).casefold() not in _PRIVATE_KEYS
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_redact(item, depth=depth + 1) for item in list(value)[:32]]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return sanitize_runtime_text(str(value), max_chars=200)


def _normalized_course(course_id: str | None) -> str | None:
    normalized = course_id.strip().upper() if course_id else ""
    return normalized or None


class ExperienceMemoryService:
    """Govern candidate writes and lifecycle transitions.

    This service owns Experience records only.  It never creates Tasks, runs
    Agents, changes Planner policy, or mutates the existing MemoryService.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = ExperienceRecordRepository(db)

    async def create_candidate(
        self, candidate: ExperienceCandidateCreate | ExperienceRecord
    ) -> ExperienceRecord:
        record = self._prepare_candidate(candidate)
        model = ExperienceRecordModel(**record.model_dump(mode="python"))
        await self.repository.add(model)
        return record

    async def get(self, experience_id: str) -> ExperienceRecord | None:
        model = await self.repository.get(experience_id)
        return self._to_record(model) if model is not None else None

    async def validate_candidate(
        self,
        experience_id: str,
        decision: ExperiencePromotionDecision,
    ) -> ExperienceRecord:
        model = await self._required(experience_id, for_update=True)
        if model.lifecycle_status not in {
            ExperienceLifecycle.CANDIDATE.value,
            ExperienceLifecycle.OBSERVED.value,
        }:
            raise ValueError("only observed or candidate experience can be validated")
        record = self._to_record(model)
        eligible = (
            decision.replay_passed
            and decision.no_critical_regression
            and decision.legal_evidence_ok
            and record.redaction_status == ExperienceRedactionStatus.VERIFIED
            and bool(
                record.source_trace_ids
                or record.source_run_ids
                or record.source_eval_ids
            )
        )
        if record.experience_type in {
            ExperienceType.SUCCESS,
            ExperienceType.STRATEGY,
        }:
            eligible = eligible and record.evidence_level in _MIN_ACTIVE_EVIDENCE
        model.lifecycle_status = (
            ExperienceLifecycle.VALIDATED.value
            if eligible
            else ExperienceLifecycle.REJECTED.value
        )
        model.promotion_provenance = {
            **dict(model.promotion_provenance or {}),
            "validation": decision.model_dump(mode="json"),
            "validated_at": datetime.now(UTC).isoformat(),
        }
        model.updated_at = datetime.now(UTC)
        await self.db.flush()
        return self._to_record(model)

    async def approve(
        self,
        experience_id: str,
        *,
        reviewer_id: str,
        policy_reason: str = "",
    ) -> ExperienceRecord:
        model = await self._required(experience_id, for_update=True)
        if model.lifecycle_status != ExperienceLifecycle.VALIDATED.value:
            raise ValueError("only validated experience can be approved")
        if not reviewer_id.strip():
            raise ValueError("independent reviewer is required")
        model.lifecycle_status = ExperienceLifecycle.APPROVED.value
        model.promotion_provenance = {
            **dict(model.promotion_provenance or {}),
            "approved_by": reviewer_id,
            "approval_reason": sanitize_runtime_text(policy_reason, max_chars=500),
            "approved_at": datetime.now(UTC).isoformat(),
        }
        model.updated_at = datetime.now(UTC)
        await self.db.flush()
        return self._to_record(model)

    async def activate(self, experience_id: str) -> ExperienceRecord:
        model = await self._required(experience_id, for_update=True)
        if model.lifecycle_status != ExperienceLifecycle.APPROVED.value:
            raise ValueError("only approved experience can be activated")
        record = self._to_record(model)
        if record.evidence_level == ExperienceEvidenceLevel.SYNTHETIC_PROVIDER_FREE:
            raise ValueError("synthetic/provider-free evidence cannot become active")
        if record.experience_type == ExperienceType.STRATEGY:
            samples = int(record.promotion_provenance.get("supporting_sample_count", 0))
            high_quality = bool(record.promotion_provenance.get("high_quality_eval"))
            if samples < 2 and not high_quality:
                raise ValueError(
                    "strategy activation requires multiple samples or a "
                    "high-quality evaluation"
                )
        model.lifecycle_status = ExperienceLifecycle.ACTIVE.value
        model.updated_at = datetime.now(UTC)
        await self.db.flush()
        return self._to_record(model)

    async def reject(self, experience_id: str, reason: str) -> ExperienceRecord:
        model = await self._required(experience_id, for_update=True)
        model.lifecycle_status = ExperienceLifecycle.REJECTED.value
        model.promotion_provenance = {
            **dict(model.promotion_provenance or {}),
            "rejected_reason": sanitize_runtime_text(reason, max_chars=500),
        }
        model.updated_at = datetime.now(UTC)
        await self.db.flush()
        return self._to_record(model)

    async def deprecate(self, experience_id: str, reason: str) -> ExperienceRecord:
        model = await self._required(experience_id, for_update=True)
        model.lifecycle_status = ExperienceLifecycle.DEPRECATED.value
        model.promotion_provenance = {
            **dict(model.promotion_provenance or {}),
            "deprecated_reason": sanitize_runtime_text(reason, max_chars=500),
        }
        model.updated_at = datetime.now(UTC)
        await self.db.flush()
        return self._to_record(model)

    async def expire(self, *, now: datetime | None = None) -> int:
        current = now or datetime.now(UTC)
        rows = await self.repository.list_for_lifecycle(
            ExperienceLifecycle.ACTIVE.value, limit=10_000
        )
        affected = 0
        for model in rows:
            if model.expires_at is not None and model.expires_at <= current:
                model.lifecycle_status = ExperienceLifecycle.EXPIRED.value
                model.updated_at = current
                affected += 1
        await self.db.flush()
        return affected

    async def forget(
        self,
        *,
        scope: ExperienceScope,
        owner_id: str | None = None,
    ) -> int:
        if scope == ExperienceScope.USER_SCOPED and not owner_id:
            raise ValueError("forgetting user-scoped experience requires owner_id")
        rows = await self.repository.list_for_lifecycle(
            ExperienceLifecycle.ACTIVE.value, limit=10_000
        )
        affected = 0
        for model in rows:
            if model.scope != scope.value:
                continue
            if (
                scope == ExperienceScope.USER_SCOPED
                and model.scope_owner_id != owner_id
            ):
                continue
            model.lifecycle_status = ExperienceLifecycle.FORGOTTEN.value
            model.forgotten_at = datetime.now(UTC)
            model.updated_at = model.forgotten_at
            affected += 1
        await self.db.flush()
        return affected

    async def retrieve(self, query: ExperienceRetrievalQuery) -> list[ExperienceMatch]:
        return await ExperienceRetriever(self.repository).retrieve(query)

    async def _required(
        self, experience_id: str, *, for_update: bool = False
    ) -> ExperienceRecordModel:
        model = await self.repository.get(experience_id, for_update=for_update)
        if model is None:
            raise ValueError(f"experience does not exist: {experience_id}")
        return model

    @staticmethod
    def _prepare_candidate(
        candidate: ExperienceCandidateCreate | ExperienceRecord,
    ) -> ExperienceRecord:
        if candidate.lifecycle_status not in {
            ExperienceLifecycle.OBSERVED,
            ExperienceLifecycle.CANDIDATE,
        }:
            raise ValueError("new experience must start as observed or candidate")
        if not (
            candidate.source_trace_ids
            or candidate.source_run_ids
            or candidate.source_eval_ids
        ):
            raise ValueError("experience candidate requires source trace, run, or eval")
        payload = candidate.model_dump(mode="json")
        payload["lifecycle_status"] = ExperienceLifecycle.CANDIDATE
        payload["redaction_status"] = ExperienceRedactionStatus.VERIFIED
        payload["course_id"] = _normalized_course(candidate.course_id)
        payload["strategy_summary"] = sanitize_runtime_text(
            candidate.strategy_summary, max_chars=4000
        )
        payload["input_feature_summary"] = _redact(candidate.input_feature_summary)
        payload["verification_result"] = _redact(candidate.verification_result)
        payload["reflection_result"] = _redact(candidate.reflection_result)
        payload["outcome_metrics"] = _redact(candidate.outcome_metrics)
        payload["promotion_provenance"] = _redact(candidate.promotion_provenance)
        payload["applicability"] = [
            sanitize_runtime_text(item, max_chars=300)
            for item in candidate.applicability[:32]
        ]
        payload["counterexamples"] = [
            sanitize_runtime_text(item, max_chars=300)
            for item in candidate.counterexamples[:32]
        ]
        return ExperienceRecord.model_validate(payload)

    @staticmethod
    def _to_record(model: ExperienceRecordModel) -> ExperienceRecord:
        return ExperienceRecord.model_validate(
            {
                key: getattr(model, key)
                for key in ExperienceRecord.model_fields
            }
        )


class ExperienceRetriever:
    """Deterministic, bounded, policy-safe active experience retrieval."""

    def __init__(
        self,
        repository: ExperienceRecordRepository | None = None,
        records: Iterable[ExperienceRecord] | None = None,
    ) -> None:
        self.repository = repository
        self.records = list(records or [])
        self.last_conflicts: list[tuple[str, ...]] = []

    async def retrieve(self, query: ExperienceRetrievalQuery) -> list[ExperienceMatch]:
        if self.repository is None:
            records = list(self.records)
        else:
            models = await self.repository.active_candidates(
                owner_id=query.user_id, limit=200
            )
            records = [ExperienceMemoryService._to_record(model) for model in models]
        return self.retrieve_from_records(records, query)

    def retrieve_from_records(
        self,
        records: Sequence[ExperienceRecord],
        query: ExperienceRetrievalQuery,
    ) -> list[ExperienceMatch]:
        now = datetime.now(UTC)
        eligible: list[ExperienceRecord] = []
        self.last_conflicts = []
        for record in records:
            if record.lifecycle_status != ExperienceLifecycle.ACTIVE:
                continue
            if record.expires_at is not None and record.expires_at <= now:
                continue
            if not self._scope_allowed(record, query):
                continue
            if (
                record.planner_version
                and query.planner_version
                and record.planner_version != query.planner_version
            ):
                continue
            eligible.append(record)
        conflict_ids = self._conflict_ids(eligible)
        scored: list[ExperienceMatch] = []
        for record in eligible:
            if record.experience_id in conflict_ids:
                continue
            score, reasons = self._score(record, query)
            if score <= 0:
                continue
            scored.append(
                ExperienceMatch(
                    experience_id=record.experience_id,
                    experience_type=record.experience_type,
                    score=score,
                    match_reasons=reasons,
                    strategy_summary=record.strategy_summary,
                    failure_warning=(
                        ",".join(record.error_codes)
                        if record.experience_type == ExperienceType.FAILURE
                        else ""
                    ),
                    evidence_level=record.evidence_level,
                    confidence=record.confidence,
                    scope=record.scope,
                    planner_version=record.planner_version,
                    experience_version=record.record_version,
                )
            )
        scored.sort(
            key=lambda item: (-item.score, -item.confidence, item.experience_id)
        )
        return scored[: query.top_k]

    @staticmethod
    def _scope_allowed(
        record: ExperienceRecord, query: ExperienceRetrievalQuery
    ) -> bool:
        if record.scope == ExperienceScope.USER_SCOPED:
            return bool(query.user_id and record.scope_owner_id == query.user_id)
        if record.scope == ExperienceScope.COURSE_SCOPED:
            return bool(
                query.course_id
                and record.course_id == _normalized_course(query.course_id)
            )
        if record.scope == ExperienceScope.CAPABILITY_SCOPED:
            return bool(
                query.capability_id and record.capability_id == query.capability_id
            )
        return record.privacy_class == ExperiencePrivacyClass.GLOBAL_DEIDENTIFIED

    @staticmethod
    def _score(
        record: ExperienceRecord, query: ExperienceRetrievalQuery
    ) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []
        if query.capability_id and record.capability_id == query.capability_id:
            score += 4
            reasons.append("capability_match")
        if query.course_id and record.course_id == _normalized_course(query.course_id):
            score += 3
            reasons.append("course_match")
        if query.problem_type and record.problem_type == query.problem_type:
            score += 3
            reasons.append("problem_type_match")
        overlap = set(query.selected_skill_ids) & set(record.skill_ids)
        if overlap:
            score += min(3, len(overlap))
            reasons.append("skill_overlap")
        tool_overlap = set(query.selected_tool_ids) & set(record.tool_ids)
        if tool_overlap:
            score += min(2, len(tool_overlap))
            reasons.append("tool_overlap")
        if query.risk_level and record.risk_level == query.risk_level:
            score += 1
            reasons.append("risk_match")
        if record.experience_type == ExperienceType.FAILURE:
            score += 0.5
            reasons.append("failure_warning")
        return score, reasons

    def _conflict_ids(self, records: Sequence[ExperienceRecord]) -> set[str]:
        by_id = {item.experience_id: item for item in records}
        excluded: set[str] = set()
        for item in records:
            for conflict_id in item.conflicts_with:
                other = by_id.get(conflict_id)
                if other is None:
                    continue
                excluded.update({item.experience_id, conflict_id})
                self.last_conflicts.append(
                    tuple(sorted({item.experience_id, conflict_id}))
                )
        return excluded


class ExperiencePlannerPrior:
    """Bounded optional prior; baseline remains the fail-safe plan."""

    def __init__(
        self,
        retriever: ExperienceRetriever,
        *,
        enabled: bool = False,
        allowed_capabilities: Iterable[str] = (),
        minimum_evidence: ExperienceEvidenceLevel = (
            ExperienceEvidenceLevel.OFFLINE_REAL_CASE
        ),
        max_influence_weight: float = 0.15,
    ) -> None:
        self.retriever = retriever
        self.enabled = enabled
        self.allowed_capabilities = frozenset(allowed_capabilities)
        self.minimum_evidence = minimum_evidence
        self.max_influence_weight = max(0.0, min(max_influence_weight, 1.0))

    @classmethod
    def from_settings(
        cls, retriever: ExperienceRetriever, settings: Any
    ) -> ExperiencePlannerPrior:
        allowlist = {
            item.strip()
            for item in str(
                getattr(settings, "experience_planner_capability_allowlist", "")
            ).split(",")
            if item.strip()
        }
        minimum = ExperienceEvidenceLevel(
            str(
                getattr(
                    settings,
                    "experience_planner_minimum_evidence",
                    ExperienceEvidenceLevel.OFFLINE_REAL_CASE.value,
                )
            )
        )
        return cls(
            retriever,
            enabled=bool(
                getattr(settings, "experience_planner_prior_enabled", False)
            ),
            allowed_capabilities=allowlist,
            minimum_evidence=minimum,
            max_influence_weight=float(
                getattr(settings, "experience_planner_max_influence_weight", 0.15)
            ),
        )

    async def shadow(
        self,
        baseline_plan: dict[str, Any],
        query: ExperienceRetrievalQuery,
        *,
        preflight_result: dict[str, Any] | None = None,
    ) -> ExperienceInfluence:
        baseline = _redact(baseline_plan)
        try:
            matches = await self.retriever.retrieve(query)
        except Exception:
            return ExperienceInfluence(
                baseline_plan=baseline,
                final_candidate_plan=baseline,
                preflight_result=preflight_result or {},
                influence_reason="retrieval_error_baseline_fallback",
            )
        if not self.enabled:
            return ExperienceInfluence(
                baseline_plan=baseline,
                experience_matches=matches,
                final_candidate_plan=baseline,
                preflight_result=preflight_result or {},
                influence_reason="disabled_shadow_only",
            )
        if (
            self.allowed_capabilities
            and query.capability_id not in self.allowed_capabilities
        ):
            return ExperienceInfluence(
                baseline_plan=baseline,
                experience_matches=matches,
                final_candidate_plan=baseline,
                preflight_result=preflight_result or {},
                influence_reason="capability_not_allowlisted",
            )
        eligible = [
            item
            for item in matches
            if _evidence_at_least(item.evidence_level, self.minimum_evidence)
        ]
        if not eligible:
            return ExperienceInfluence(
                baseline_plan=baseline,
                experience_matches=matches,
                final_candidate_plan=baseline,
                preflight_result=preflight_result or {},
                influence_reason="no_eligible_prior_baseline_fallback",
            )
        final_plan = dict(baseline)
        selected_skills = list(final_plan.get("selected_skills", []))
        registered_skills = set(selected_skills)
        preferred = [
            skill
            for item in eligible
            for skill in _record_skill_ids(item, self.retriever.records)
            if skill in registered_skills
        ]
        if preferred:
            final_plan["selected_skills"] = list(
                dict.fromkeys(preferred + selected_skills)
            )
        final_plan["verification_required"] = True
        return ExperienceInfluence(
            baseline_plan=baseline,
            experience_matches=matches,
            influence_applied=bool(preferred) or bool(eligible),
            influence_reason="bounded_registered_prior_with_verification",
            final_candidate_plan=_redact(final_plan),
            preflight_result=preflight_result or {},
        )


def _record_skill_ids(
    match: ExperienceMatch, records: Sequence[ExperienceRecord]
) -> list[str]:
    for record in records:
        if record.experience_id == match.experience_id:
            return record.skill_ids
    return []


def _evidence_at_least(
    actual: ExperienceEvidenceLevel, minimum: ExperienceEvidenceLevel
) -> bool:
    order = {
        ExperienceEvidenceLevel.SYNTHETIC_PROVIDER_FREE: 0,
        ExperienceEvidenceLevel.OFFLINE_REAL_CASE: 1,
        ExperienceEvidenceLevel.REAL_PROVIDER_TEST: 2,
        ExperienceEvidenceLevel.CONTROLLED_CANARY: 3,
        ExperienceEvidenceLevel.PRODUCTION: 4,
    }
    return order[actual] >= order[minimum]


async def evaluate_experience_memory(
    retriever: ExperienceRetriever,
    query: ExperienceRetrievalQuery,
    *,
    expected_ids: set[str] | None = None,
) -> ExperienceEvaluationReport:
    matches = await retriever.retrieve(query)
    matched_ids = {item.experience_id for item in matches}
    valid_rate = (
        len(matched_ids & expected_ids) / len(expected_ids)
        if expected_ids
        else 0.0
    )
    return ExperienceEvaluationReport(
        retrieval_valid_match_rate=valid_rate,
        retrieval_irrelevant_match_rate=(
            len(matched_ids - expected_ids) / len(matched_ids)
            if expected_ids and matched_ids
            else 0.0
        ),
        stale_filtered=0,
        wrong_scope_filtered=0,
        version_mismatch_filtered=0,
        provenance_complete=all(
            item.experience_id and item.evidence_level for item in matches
        ),
        status="conditional_go",
    )
