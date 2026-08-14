from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest
from app.agents.internal import InternalAgentHub, InternalAgentResult
from app.contracts import (
    AgentRequest,
    AgentResult,
    Intent,
    KnowledgeCourseId,
    KnowledgeHit,
    RetrievalContextPacket,
    Scene,
    UserRole,
)
from app.services.internal_agent_execution import InternalAgentExecutionService


class FakeHub:
    def __init__(self) -> None:
        self.input_text = ""
        self.extra_options: dict[str, Any] | None = None

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {"agent_id": agent_id, "configured": True, "enabled": True}
            for agent_id in (
                "LESSON_PREP_LOCAL_V1",
                "ASSIGNMENT_REVIEW_LOCAL_V1",
                "ACADEMIC_WRITING_LOCAL_V1",
                "DATA_ANALYSIS_LOCAL_V1",
            )
        ]

    async def run_text(self, agent_id: str, **kwargs: Any) -> InternalAgentResult:
        self.input_text = str(kwargs["input_text"])
        self.extra_options = kwargs.get("extra_options")
        values: dict[str, dict[str, Any]] = {
            "LESSON_PREP_LOCAL_V1": {
                "title": "电容连续性",
                "learning_objectives": ["解释连续性"],
                "lesson_flow": ["证据导入", "例题讨论"],
                "formative_assessment": ["出口题"],
                "warnings": ["需教师确认学情"],
            },
            "ASSIGNMENT_REVIEW_LOCAL_V1": {
                "correctness": "partially_correct",
                "correct_parts": ["欧姆定律正确"],
                "errors": ["缺少方向说明"],
                "feedback": "补充参考方向。",
                "review_required": True,
            },
            "ACADEMIC_WRITING_LOCAL_V1": {
                "revised_text": "现有描述提示滤波器可能有效。",
                "revision_notes": ["降低结论强度"],
                "unsupported_claims": ["效果很好"],
                "citation_check_required": True,
            },
            "DATA_ANALYSIS_LOCAL_V1": {
                "analysis_status": "interpreted",
                "method": "先检查分组和缺失值",
                "steps": ["定义变量", "选择模型"],
                "interpretation": (
                    "The computed comparison addresses the declared research question."
                ),
                "limitations": ["Review assignment and sampling before causal claims."],
            },
        }
        return InternalAgentResult(
            agent_id=agent_id,
            task_type="test",
            provider="iflytek_spark+dashscope",
            model="spark-x->qwen3.5-flash",
            content="{}",
            structured_result=values[agent_id],
            prompt_tokens=20,
            completion_tokens=10,
            total_tokens=30,
            elapsed_ms=25,
        )


class FakeGeneralQuestion:
    async def run(self, _: AgentRequest) -> AgentResult:
        return AgentResult(
            agent_id="GENERAL_QUESTION_V1",
            provider="local_agent",
            answer="本地回答",
            structured_result={
                "status": "completed",
                "model_execution": {"status": "success"},
            },
        )


class FakeResearchFrontier:
    def available(self) -> bool:
        return True

    async def run(self, _: AgentRequest) -> AgentResult:
        return AgentResult(
            agent_id="RESEARCH_01_ACADEMIC_SEARCH_V1",
            provider="local_agent",
            answer="科研前沿证据简报",
            structured_result={"status": "completed"},
        )


def service() -> tuple[InternalAgentExecutionService, FakeHub]:
    hub = FakeHub()
    return InternalAgentExecutionService(cast(InternalAgentHub, hub)), hub


def request(intent: Intent) -> AgentRequest:
    return AgentRequest(
        task_id="task-internal",
        session_id="session-internal",
        user_id="teacher",
        user_role=UserRole.TEACHER,
        scene=Scene.TEACHING,
        course_id="CT",
        intent=intent,
        canonical_input={"text": "请设计电容连续性教案"},
        options={"request_id": "request-internal", "response_depth": "standard"},
    )


def context() -> RetrievalContextPacket:
    hit = KnowledgeHit(
        evidence_id="S1",
        course_id=KnowledgeCourseId.CIRCUIT_THEORY,
        course_name="电路理论",
        chapter="动态电路",
        document_path="CT/chapter.md",
        title="电容连续性",
        content_type="concept",
        content="有限电流下电容电压不能突变。",
        score=0.9,
        source_ref="kb://CT/chapter.md#chunk-1",
    )
    return RetrievalContextPacket(
        query="电容连续性教案",
        course_id="CT",
        intent="lesson_prep",
        evidence=[hit],
        source_refs=[hit.source_ref],
        evidence_status="sufficient",
        max_context_chars=6000,
    )


@pytest.mark.asyncio
async def test_lesson_internal_agent_reuses_local_rag_context() -> None:
    executor, hub = service()

    result = await executor.run(
        "TEACH_01_LESSON_PREP_V1", request(Intent.LESSON_PREP), context()
    )

    assert result.provider == "local_agent"
    assert result.metrics.model_calls == 2
    assert result.metrics.input_tokens == 20
    assert result.business_data["learning_objectives"] == ["解释连续性"]
    assert result.business_data["activities"] == ["证据导入", "例题讨论"]
    assert "[S1]" in hub.input_text
    assert result.artifacts[0].content["execution_source"] == "internal_agent_hub"


@pytest.mark.asyncio
async def test_runtime_internal_agent_enables_structured_fallback() -> None:
    executor, hub = service()
    runtime_request = request(Intent.LESSON_PREP).model_copy(
        update={
            "options": {
                "request_id": "request-runtime",
                "runtime_allow_structured_fallback": True,
            }
        }
    )

    await executor.run("TEACH_01_LESSON_PREP_V1", runtime_request)

    assert hub.extra_options == {"_allow_structured_fallback": True}


@pytest.mark.asyncio
async def test_lesson_runtime_replan_prefers_configured_route_fallback() -> None:
    executor, hub = service()
    runtime_request = request(Intent.LESSON_PREP).model_copy(
        update={
            "options": {
                "request_id": "request-runtime-replan",
                "runtime_allow_structured_fallback": True,
                "lesson_prep_runtime": {
                    "execute": True,
                    "runtime_replan_iteration": 1,
                },
            }
        }
    )

    await executor.run("TEACH_01_LESSON_PREP_V1", runtime_request)

    assert hub.extra_options == {
        "_allow_structured_fallback": True,
        "_prefer_route_fallback": True,
    }


@pytest.mark.asyncio
async def test_academic_writing_replan_prefers_route_fallback() -> None:
    executor, hub = service()
    runtime_request = request(Intent.ACADEMIC_WRITING).model_copy(
        update={
            "options": {
                "request_id": "request-writing-replan",
                "runtime_allow_structured_fallback": True,
                "academic_writing_runtime": {
                    "execute": True,
                    "runtime_replan_iteration": 1,
                },
            }
        }
    )

    await executor.run("RESEARCH_02_ACADEMIC_WRITING_V1", runtime_request)

    assert hub.extra_options == {
        "_allow_structured_fallback": True,
        "_prefer_route_fallback": True,
    }


def test_lesson_formatter_fills_empty_title_for_reviewable_draft() -> None:
    answer, data, _, _ = InternalAgentExecutionService._lesson(
        {
            "title": "",
            "learning_objectives": [],
            "lesson_flow": [],
            "formative_assessment": [],
            "warnings": [],
        }
    )

    assert data["title"] == "Lesson plan draft"
    assert answer.startswith("## ")


def test_lesson_runtime_uses_deep_structured_output_budget() -> None:
    runtime_request = request(Intent.LESSON_PREP).model_copy(
        update={
            "options": {
                "lesson_prep_runtime": {"execute": True},
                "response_depth": "standard",
            }
        }
    )

    assert InternalAgentExecutionService._max_tokens(runtime_request) == 512
    assert InternalAgentExecutionService._max_tokens(
        request(Intent.LESSON_PREP)
    ) == 384


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("workflow_id", "intent", "field"),
    [
        ("TEACH_02_ASSIGNMENT_REVIEW_V1", Intent.ASSIGNMENT_REVIEW, "teacher_feedback"),
        ("RESEARCH_02_ACADEMIC_WRITING_V1", Intent.ACADEMIC_WRITING, "revised_text"),
        ("RESEARCH_03_DATA_ANALYSIS_V1", Intent.DATA_ANALYSIS, "analysis_steps"),
    ],
)
async def test_internal_business_agents_adapt_to_existing_result_contract(
    workflow_id: str, intent: Intent, field: str
) -> None:
    executor, _ = service()

    result = await executor.run(workflow_id, request(intent))

    assert field in result.business_data
    assert result.answer.startswith("## ")
    assert result.structured_result["internal_execution"]["usage"]["total_tokens"] == 30


def test_internal_agent_availability_is_sanitized() -> None:
    executor, _ = service()

    assert executor.available("TEACH_01_LESSON_PREP_V1") is True
    assert executor.available("SOLVER_CT_V1") is False


@pytest.mark.asyncio
async def test_research_frontier_alias_uses_local_research_agent() -> None:
    hub = FakeHub()
    executor = InternalAgentExecutionService(
        cast(InternalAgentHub, hub),
        general_question=cast(Any, FakeGeneralQuestion()),
        research_frontier=cast(Any, FakeResearchFrontier()),
    )

    assert executor.available("RESEARCH_01_ACADEMIC_SEARCH_V1") is True
    result = await executor.run(
        "RESEARCH_01_ACADEMIC_SEARCH_V1", request(Intent.GENERAL_QA)
    )

    assert result.agent_id == "RESEARCH_01_ACADEMIC_SEARCH_V1"
    assert result.provider == "local_agent"


@pytest.mark.asyncio
async def test_research_analysis_v2_prefers_direct_model_and_keeps_local_fallback(
    tmp_path: Path,
) -> None:
    executor, hub = service()
    data_path = tmp_path / "analysis.csv"
    data_path.write_text(
        "outcome,treatment\n10,control\n12,control\n16,treatment\n18,treatment\n",
        encoding="utf-8",
    )
    task_request = request(Intent.DATA_ANALYSIS).model_copy(
        update={
            "options": {
                "request_id": "request-v2",
                "research_analysis_v2": {
                    "execute": True,
                    "model_assist": False,
                    "output_dir": str(tmp_path / "pack"),
                    "request": {
                        "research_question": "What is the declared group difference?",
                        "hypothesis": "The declared groups differ.",
                        "analysis_goal": "compare",
                        "design": "experimental_comparison",
                        "unit_of_analysis": "one row",
                        "variables": [
                            {"name": "outcome", "role": "outcome", "unit": "score"},
                            {"name": "treatment", "role": "treatment"},
                        ],
                        "data_manifest": {
                            "dataset_id": "local-test",
                            "version": "1",
                            "format": "csv",
                            "checksum_sha256": sha256(
                                data_path.read_bytes()
                            ).hexdigest(),
                            "row_count": 4,
                            "column_count": 2,
                            "authorized": True,
                            "source_ref": str(data_path),
                        },
                        "data_dictionary": "outcome and treatment are documented",
                        "evidence": [
                            {
                                "evidence_id": "method-001",
                                "role": "method_reference",
                                "source_ref": "https://example.test/method",
                                "cited": True,
                            }
                        ],
                        "exploratory": False,
                    },
                },
            }
        }
    )

    result = await executor.run("RESEARCH_03_DATA_ANALYSIS_V1", task_request)

    assert result.provider == "local_analysis_v2"
    assert result.business_data["status"] == "executed"
    assert result.metrics.model_calls == 0
    assert result.business_data["evidence_ids"] == ["method-001"]
    assert result.business_data["evidence_references"][0]["role"] == (
        "method_reference"
    )
    assert hub.input_text == ""

    assisted_options = dict(task_request.options)
    assisted_analysis = dict(assisted_options["research_analysis_v2"])
    assisted_analysis["model_assist"] = True
    assisted_options["research_analysis_v2"] = assisted_analysis
    assisted_request = task_request.model_copy(update={"options": assisted_options})
    assisted = await executor.run("RESEARCH_03_DATA_ANALYSIS_V1", assisted_request)

    assert assisted.provider == "model_analysis:iflytek_spark+dashscope"
    assert assisted.metrics.model_calls == 2
    assert assisted.business_data["explanation_source"] == "model_direct"
    assert assisted.structured_result["model_analysis"]["status"] == "used"
    assert "受控数据" in hub.input_text
    assert '"outcome":"10"' in hub.input_text
    assert str(data_path) not in hub.input_text


def test_research_analysis_no_data_message_is_user_facing_and_actionable() -> None:
    executor, _ = service()
    task_request = request(Intent.DATA_ANALYSIS).model_copy(
        update={
            "options": {
                "request_id": "request-v2-no-data",
                "research_analysis_v2": {
                    "execute": False,
                    "request": {
                        "research_question": "不同教学方法对成绩的影响是什么？",
                        "analysis_goal": "compare",
                        "design": "unknown",
                    },
                },
            }
        }
    )

    result = executor._run_research_analysis_v2(task_request)
    interpretation = str(result.business_data["interpretation"])

    assert "分析计划已冻结" in interpretation
    assert "等待质量门禁与人工复核" in interpretation
    assert "execute=true" not in interpretation


class FakeTaskInternalExecution:
    def available(self, agent_id: str) -> bool:
        return agent_id == "TEACH_01_LESSON_PREP_V1"

    async def run(
        self,
        agent_id: str,
        task_request: AgentRequest,
        context_packet: RetrievalContextPacket | None = None,
    ) -> AgentResult:
        del context_packet
        return AgentResult(
            agent_id=agent_id,
            provider="local_agent",
            answer="## 教案草稿\n\n### 教学目标\n- 解释电容连续性",
            business_data={
                "learning_objectives": ["解释电容连续性"],
                "lesson_flow": ["概念导入"],
                "activities": ["小组讨论"],
                "formative_assessment": ["出口题"],
            },
            structured_result={
                "status": "completed",
                "business_data": {
                    "learning_objectives": ["解释电容连续性"],
                    "lesson_flow": ["概念导入"],
                    "activities": ["小组讨论"],
                    "formative_assessment": ["出口题"],
                },
            },
            cloud_status="not_required",
            request_id=str(task_request.options.get("request_id", "")),
        )


def test_task_api_executes_internal_agent_without_second_task_path(client, api) -> None:
    client.app.state.task_runner.internal_agents = FakeTaskInternalExecution()
    session = api.create_session(user_id="teacher-internal")
    payload = {
        "session_id": session["id"],
        "user_id": "teacher-internal",
        "user_role": "teacher",
        "scene": "teaching",
        "course_id": "CT",
        "intent": "lesson_prep",
        "canonical_input": {"text": "请设计电容连续性课堂教案"},
        "options": {"request_id": "request-task-internal"},
    }

    created = client.post("/api/v1/tasks", json=payload)
    assert created.status_code == 202
    task = api.wait_for_task(created.json()["id"])

    assert task["status"] == "completed"
    assert task["provider"] == "local_agent"
    structured = task["result_content"]["structured_result"]
    assert structured["execution_source"] == "internal_agent"
    assert structured["presentation"]["provider_label"] == "内部 Agent 协作"
    events = client.get(f"/api/v1/tasks/{task['id']}/events").json()
    sequences = [item["sequence"] for item in events]
    assert sequences == sorted(sequences)
