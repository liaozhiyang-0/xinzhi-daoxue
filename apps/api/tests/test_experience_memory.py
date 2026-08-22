from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from app.contracts.experience import (
    ExperienceCandidateCreate,
    ExperienceEvidenceLevel,
    ExperienceLifecycle,
    ExperiencePrivacyClass,
    ExperiencePromotionDecision,
    ExperienceRetrievalQuery,
    ExperienceScope,
    ExperienceType,
)
from app.database.base import Base
from app.services.experience_memory import (
    ExperienceMemoryService,
    ExperiencePlannerPrior,
    ExperienceRetriever,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def candidate(**updates: object) -> ExperienceCandidateCreate:
    payload: dict[str, object] = {
        "experience_type": ExperienceType.STRATEGY,
        "scope": ExperienceScope.CAPABILITY_SCOPED,
        "privacy_class": ExperiencePrivacyClass.CAPABILITY_DEIDENTIFIED,
        "capability_id": "academic_problem_solver",
        "course_id": "CT",
        "problem_type": "calculation",
        "skill_ids": ["skill.solve"],
        "planner_version": "planner-v1",
        "strategy_summary": "先检索已发布课程证据，再执行验证。",
        "evidence_level": ExperienceEvidenceLevel.OFFLINE_REAL_CASE,
        "source_eval_ids": ["eval_001"],
        "confidence": 0.9,
        "promotion_provenance": {
            "supporting_sample_count": 2,
            "high_quality_eval": True,
        },
    }
    payload.update(updates)
    return ExperienceCandidateCreate(**payload)


@pytest.mark.asyncio
async def test_candidate_lifecycle_is_governed_and_redacted(db: AsyncSession) -> None:
    service = ExperienceMemoryService(db)
    record = await service.create_candidate(
        candidate(
            input_feature_summary={
                "problem_type": "calculation",
                "prompt": "student raw answer must not persist",
            }
        )
    )
    assert record.lifecycle_status == ExperienceLifecycle.CANDIDATE
    assert record.input_feature_summary == {"problem_type": "calculation"}

    validated = await service.validate_candidate(
        record.experience_id,
        ExperiencePromotionDecision(
            replay_passed=True,
            no_critical_regression=True,
            legal_evidence_ok=True,
        ),
    )
    assert validated.lifecycle_status == ExperienceLifecycle.VALIDATED
    approved = await service.approve(record.experience_id, reviewer_id="reviewer-1")
    assert approved.lifecycle_status == ExperienceLifecycle.APPROVED
    active = await service.activate(record.experience_id)
    assert active.lifecycle_status == ExperienceLifecycle.ACTIVE

    matches = await service.retrieve(
        ExperienceRetrievalQuery(
            course_id="ct",
            capability_id="academic_problem_solver",
            problem_type="calculation",
            selected_skill_ids=["skill.solve"],
            planner_version="planner-v1",
            top_k=1,
        )
    )
    assert [item.experience_id for item in matches] == [record.experience_id]


@pytest.mark.asyncio
async def test_synthetic_strategy_cannot_be_activated(db: AsyncSession) -> None:
    service = ExperienceMemoryService(db)
    record = await service.create_candidate(
        candidate(evidence_level=ExperienceEvidenceLevel.SYNTHETIC_PROVIDER_FREE)
    )
    await service.validate_candidate(
        record.experience_id,
        ExperiencePromotionDecision(
            replay_passed=True,
            no_critical_regression=True,
            legal_evidence_ok=True,
        ),
    )
    rejected = await service.get(record.experience_id)
    assert rejected is not None
    assert rejected.lifecycle_status == ExperienceLifecycle.REJECTED


def test_retriever_isolates_scope_and_conflicts() -> None:
    first = candidate(
        experience_id="exp_user_a",
        scope=ExperienceScope.USER_SCOPED,
        scope_owner_id="user-a",
        privacy_class=ExperiencePrivacyClass.USER_PRIVATE,
        lifecycle_status=ExperienceLifecycle.ACTIVE,
    )
    second = candidate(
        experience_id="exp_user_b",
        scope=ExperienceScope.USER_SCOPED,
        scope_owner_id="user-b",
        privacy_class=ExperiencePrivacyClass.USER_PRIVATE,
        lifecycle_status=ExperienceLifecycle.ACTIVE,
    )
    retriever = ExperienceRetriever(records=[first, second])
    matches = retriever.retrieve_from_records(
        [first, second],
        ExperienceRetrievalQuery(
            capability_id="academic_problem_solver", user_id="user-a"
        ),
    )
    assert [item.experience_id for item in matches] == ["exp_user_a"]


@pytest.mark.asyncio
async def test_planner_prior_defaults_to_baseline() -> None:
    record = candidate(
        experience_id="exp_prior",
        lifecycle_status=ExperienceLifecycle.ACTIVE,
    )
    prior = ExperiencePlannerPrior(
        ExperienceRetriever(records=[record]), enabled=False
    )
    result = await prior.shadow(
        {"selected_skills": ["skill.solve"], "plan_id": "baseline"},
        ExperienceRetrievalQuery(
            capability_id="academic_problem_solver", planner_version="planner-v1"
        ),
    )
    assert result.influence_applied is False
    assert result.final_candidate_plan == result.baseline_plan
    assert result.experience_matches
