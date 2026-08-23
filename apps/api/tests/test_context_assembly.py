from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

from app.api.v1.sessions import _public_summary
from app.contracts import AgentRequest, AgentResult, Intent
from app.contracts.conversation import (
    MessageRole,
    MessageStatus,
    SessionSummaryRead,
)
from app.models import SessionModel, SessionSummaryModel
from app.models.entities import utc_now
from app.repositories.runtime_context import RuntimeContextRepository
from app.services.context_assembly import ContextAssemblyService
from app.services.conversation_message_service import ConversationMessageService
from app.services.session_compaction import SessionCompactionService
from app.services.session_context import SessionContextService


def _external_payload(*, review_status: str, approved_count: int) -> dict[str, object]:
    return {
        "query": "近期多模态论文",
        "review_status": review_status,
        "approved_count": approved_count,
        "items": [
            {
                "evidence_id": "paper-1",
                "title": "Reviewed paper",
                "content_excerpt": "evidence excerpt",
            }
        ],
    }


def _continuity_request(text: str, intent: Intent = Intent.GENERAL_QA) -> AgentRequest:
    return AgentRequest(
        session_id="session-context",
        user_id="user-context",
        course_id="CT",
        intent=intent,
        canonical_input={"text": text},
    )


def test_session_context_withholds_unreviewed_external_evidence(settings) -> None:
    session = SessionModel(
        id="session-context",
        user_id="user-context",
        course_id="CT",
        context_data={},
    )
    result = AgentResult(
        agent_id="RESEARCH_01_ACADEMIC_SEARCH_V1",
        provider="test",
        answer="候选结果",
        structured_result={
            "external_retrieval": _external_payload(
                review_status="not_run", approved_count=0
            )
        },
    )

    SessionContextService(settings).update(
        session, _continuity_request("检索近期多模态论文"), result
    )

    stored = session.context_data["previous_external_retrieval"]
    assert stored["items"] == []
    assert "previous external evidence withheld pending review" in stored["warnings"]


def test_session_context_reuses_only_approved_evidence_on_research_follow_up(
    settings,
) -> None:
    session = SessionModel(
        id="session-context",
        user_id="user-context",
        course_id="CT",
        context_data={
            "active_course": "CT",
            "previous_agent": "RESEARCH_01_ACADEMIC_SEARCH_V1",
            "previous_answer_summary": "已列出论文证据",
            "previous_external_query": "近期多模态论文",
            "previous_external_retrieval": _external_payload(
                review_status="approved", approved_count=1
            ),
        },
    )

    request = SessionContextService(settings).apply(
        session,
        _continuity_request("继续提供更多论文", Intent.GENERAL_QA),
    )

    payload = request.options["previous_external_retrieval"]
    assert len(payload["items"]) == 1
    assert payload["approved_count"] == 1


def test_session_context_does_not_reuse_research_evidence_for_circuit_diagnosis(
    settings,
) -> None:
    session = SessionModel(
        id="session-context",
        user_id="user-context",
        course_id="CT",
        context_data={
            "active_course": "CT",
            "previous_agent": "RESEARCH_01_ACADEMIC_SEARCH_V1",
            "previous_answer_summary": "已列出论文证据",
            "previous_external_query": "近期多模态论文",
            "previous_external_retrieval": _external_payload(
                review_status="approved", approved_count=1
            ),
        },
    )

    request = SessionContextService(settings).apply(
        session,
        _continuity_request("诊断运放积分器输出漂移", Intent.SOLVE_PROBLEM),
    )

    assert request.options["previous_external_retrieval"] == {}


def test_session_context_does_not_reuse_evidence_for_new_explicit_search(
    settings,
) -> None:
    session = SessionModel(
        id="session-context",
        user_id="user-context",
        course_id="CT",
        context_data={
            "active_course": "AUTO",
            "previous_agent": "RESEARCH_01_ACADEMIC_SEARCH_V1",
            "previous_answer_summary": "已列出多模态论文",
            "previous_external_query": "近期多模态视觉理解论文",
            "previous_external_retrieval": _external_payload(
                review_status="approved", approved_count=1
            ),
        },
    )

    request = SessionContextService(settings).apply(
        session,
        AgentRequest(
            session_id="session-context",
            user_id="user-context",
            course_id="AUTO",
            intent=Intent.ACADEMIC_SEARCH,
            canonical_input={
                "text": "检索近期 RISC-V 侧信道硬件防御论文"
            },
        ),
    )

    assert request.options["previous_external_retrieval"] == {}


def test_recent_context_boundary_uses_oldest_message_in_active_course() -> None:
    messages = [
        SimpleNamespace(
            id="other-course",
            sequence=2,
            metadata_data={"course_id": "AE"},
        ),
        SimpleNamespace(
            id="active-course",
            sequence=5,
            metadata_data={"course_id": "CT"},
        ),
    ]

    filtered = [
        item
        for item in messages
        if item.id != "current"
        and ContextAssemblyService._message_matches_course(item, "CT")
    ]

    assert [item.id for item in filtered] == ["active-course"]
    assert filtered[0].sequence == 5


def test_legacy_message_without_metadata_is_not_a_context_error() -> None:
    message = SimpleNamespace(
        id="legacy",
        sequence=1,
        role="user",
        content_text="旧消息",
        metadata_data=None,
    )

    context = ContextAssemblyService._context_message(message)

    assert context.course_id == ""


def test_unbound_summary_is_not_safe_for_course_context() -> None:
    unbound = SimpleNamespace(structured_state={})
    bound = SimpleNamespace(structured_state={"course_id": "AE"})

    assert ContextAssemblyService._summary_matches_course(unbound, "CT") is False
    assert ContextAssemblyService._summary_matches_course(bound, "AE") is True


def test_context_rejects_withdrawn_material_in_message_or_summary_projection() -> None:
    message = SimpleNamespace(
        metadata_data={
            "course_material_source_refs": [
                "kb-material://CT/file-withdrawn#chunk-0"
            ]
        },
        content_data={},
    )
    summary = SimpleNamespace(
        structured_state={
            "course_material_source_refs": [
                "kb-material://CT/file-withdrawn#chunk-0"
            ]
        }
    )

    assert ContextAssemblyService._contains_revoked_material(
        message, {"file-withdrawn"}
    )
    assert ContextAssemblyService._contains_revoked_material(
        summary, {"file-withdrawn"}
    )


def test_compaction_records_material_refs_from_source_messages(api, app) -> None:
    session = api.create_session()

    async def exercise() -> list[str]:
        async with app.state.session_factory() as db:
            session_model = await db.get(SessionModel, session["id"])
            assert session_model is not None
            messages = ConversationMessageService(db)
            await messages.append(
                session=session_model,
                user_id=session_model.user_id,
                role=MessageRole.USER,
                status=MessageStatus.COMPLETED,
                content_text="请依据课程资料回答",
                metadata={"course_id": "CT"},
            )
            await messages.append(
                session=session_model,
                user_id=session_model.user_id,
                role=MessageRole.ASSISTANT,
                status=MessageStatus.COMPLETED,
                content_text="回答",
                content_data={
                    "evidence_view": [
                        {
                            "source_ref": "kb-material://CT/material-1#chunk-0"
                        }
                    ]
                },
                metadata={
                    "course_id": "CT",
                    "course_material_source_refs": [
                        "kb-material://CT/material-1#chunk-0"
                    ],
                },
            )
            summary, _ = await SessionCompactionService(
                app.state.settings,
                app.state.context_budget,
            ).summarize_completed_turn(
                db,
                session=session_model,
                source_task_id="task-without-persisted-result",
                course_id="CT",
            )
            assert summary is not None
            await db.commit()
            return list(
                summary.structured_state["course_material_source_refs"]
            )

    refs = asyncio.run(exercise())
    assert refs == ["kb-material://CT/material-1#chunk-0"]


def test_context_rejects_legacy_summary_when_source_message_is_withdrawn(
    api, app
) -> None:
    session = api.create_session()
    state_path = app.state.settings.knowledge_index_path / "rag_index_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"revoked_material_ids": ["material-legacy"]}),
        encoding="utf-8",
    )

    async def exercise() -> str:
        async with app.state.session_factory() as db:
            session_model = await db.get(SessionModel, session["id"])
            assert session_model is not None
            messages = ConversationMessageService(db)
            source = await messages.append(
                session=session_model,
                user_id=session_model.user_id,
                role=MessageRole.ASSISTANT,
                status=MessageStatus.COMPLETED,
                content_text="旧资料回答",
                metadata={
                    "course_id": "CT",
                    "course_material_source_refs": [
                        "kb-material://CT/material-legacy#chunk-0"
                    ],
                },
            )
            db.add(
                SessionSummaryModel(
                    id="summary-legacy-without-ref",
                    session_id=session_model.id,
                    version=1,
                    covers_from_sequence=source.sequence,
                    covers_through_sequence=source.sequence,
                    summary_text="旧资料摘要",
                    structured_state={"course_id": "CT"},
                    source_message_ids=[source.id],
                    source_checksum="l" * 64,
                    generation_method="legacy",
                    model_name="",
                    token_estimate=1,
                    status="completed",
                    created_at=utc_now(),
                )
            )
            await db.commit()
            bundle = await app.state.context_assembly.assemble(
                db,
                session_id=session_model.id,
                user_id=session_model.user_id,
                current_message_id=None,
                course_id="CT",
                task_family="solving",
                agent_id="solver_ct",
            )
            return bundle.session_summary

    assert asyncio.run(exercise()) == ""


def test_context_keeps_latest_summary_for_active_course_after_course_switch(
    api, app
) -> None:
    session = api.create_session()

    async def exercise() -> tuple[str, str | None, int]:
        async with app.state.session_factory() as db:
            session_model = await db.get(SessionModel, session["id"])
            assert session_model is not None
            messages = ConversationMessageService(db)
            ct_message = await messages.append(
                session=session_model,
                user_id=session_model.user_id,
                role=MessageRole.ASSISTANT,
                status=MessageStatus.COMPLETED,
                content_text="CT 已确认的积分器约束",
                metadata={"course_id": "CT"},
            )
            ae_message = await messages.append(
                session=session_model,
                user_id=session_model.user_id,
                role=MessageRole.ASSISTANT,
                status=MessageStatus.COMPLETED,
                content_text="AE 当前的滤波器问题",
                metadata={"course_id": "AE"},
            )
            db.add_all(
                [
                    SessionSummaryModel(
                        id="summary-ct-before-switch",
                        session_id=session_model.id,
                        version=1,
                        covers_from_sequence=ct_message.sequence,
                        covers_through_sequence=ct_message.sequence,
                        summary_text="CT 摘要仍可用于 CT 追问",
                        structured_state={"course_id": "CT"},
                        source_message_ids=[ct_message.id],
                        source_checksum="c" * 64,
                        generation_method="test",
                        model_name="",
                        token_estimate=1,
                        status="completed",
                        created_at=utc_now(),
                    ),
                    SessionSummaryModel(
                        id="summary-ae-after-switch",
                        session_id=session_model.id,
                        version=2,
                        covers_from_sequence=ae_message.sequence,
                        covers_through_sequence=ae_message.sequence,
                        summary_text="AE 更新摘要",
                        structured_state={"course_id": "AE"},
                        source_message_ids=[ae_message.id],
                        source_checksum="a" * 64,
                        generation_method="test",
                        model_name="",
                        token_estimate=1,
                        status="completed",
                        created_at=utc_now(),
                    ),
                ]
            )
            await db.commit()
            bundle = await app.state.context_assembly.assemble(
                db,
                session_id=session_model.id,
                user_id=session_model.user_id,
                current_message_id=None,
                course_id="CT",
                task_family="solving",
                agent_id="solver_ct",
            )
            return bundle.session_summary, bundle.summary_id, bundle.summary_version

    summary_text, summary_id, summary_version = asyncio.run(exercise())
    assert summary_text == "CT 摘要仍可用于 CT 追问"
    assert summary_id == "summary-ct-before-switch"
    assert summary_version == 1


def test_public_summary_filters_material_ref_recovered_from_source_message() -> None:
    summary = SessionSummaryRead(
        id="summary-public",
        session_id="session-public",
        version=1,
        covers_from_sequence=1,
        covers_through_sequence=1,
        summary_text="旧资料摘要",
        structured_state={"course_id": "CT"},
        source_message_ids=["message-public"],
        source_checksum="p" * 64,
        generation_method="legacy",
        model_name="",
        token_estimate=1,
        status="completed",
        created_at=datetime.now(UTC),
    )

    public = _public_summary(
        summary,
        {"material-public"},
        source_refs=["kb-material://CT/material-public#chunk-0"],
    )

    assert "kb-material://" not in str(public.structured_state)
    assert public.structured_state["revocation_notice"]["status"] == "needs_review"


def test_compaction_does_not_carry_previous_course_summary_or_messages(
    api, app
) -> None:
    session = api.create_session()

    async def exercise() -> tuple[str, list[str], int, int]:
        async with app.state.session_factory() as db:
            session_model = await db.get(SessionModel, session["id"])
            assert session_model is not None
            messages = ConversationMessageService(db)
            ct_message = await messages.append(
                session=session_model,
                user_id=session_model.user_id,
                role=MessageRole.USER,
                status=MessageStatus.COMPLETED,
                content_text="CT旧问题",
                metadata={"course_id": "CT"},
            )
            ae_message = await messages.append(
                session=session_model,
                user_id=session_model.user_id,
                role=MessageRole.USER,
                status=MessageStatus.COMPLETED,
                content_text="AE当前问题",
                metadata={"course_id": "AE"},
            )
            db.add(
                SessionSummaryModel(
                    id="summary-ct-old",
                    session_id=session_model.id,
                    version=1,
                    covers_from_sequence=1,
                    covers_through_sequence=1,
                    summary_text="CT旧摘要",
                    structured_state={"course_id": "CT"},
                    source_message_ids=[ct_message.id],
                    source_checksum="c" * 64,
                    generation_method="test",
                    model_name="",
                    token_estimate=1,
                    status="completed",
                    created_at=utc_now(),
                )
            )
            await db.commit()

            summary, _ = await SessionCompactionService(
                app.state.settings,
                app.state.context_budget,
            ).summarize_completed_turn(
                db,
                session=session_model,
                source_task_id="task-ae-current",
                course_id="AE",
            )
            assert summary is not None
            assert summary.source_message_ids == [ae_message.id]
            await db.commit()
            selected = await RuntimeContextRepository(db).latest_summary_for_course(
                session_model.id, "AE"
            )
            assert selected is not None
            return (
                str(summary.structured_state["course_id"]),
                list(summary.source_message_ids),
                int(summary.covers_from_sequence),
                int(selected.version),
            )

    course, source_ids, covers_from, version = asyncio.run(exercise())
    assert course == "AE"
    assert len(source_ids) == 1
    assert covers_from == 2
    assert version == 2
