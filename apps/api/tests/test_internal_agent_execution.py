from __future__ import annotations

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
                "analysis_status": "plan",
                "method": "先检查分组和缺失值",
                "steps": ["定义变量", "选择模型"],
                "interpretation": "尚无数据，只能给出方案。",
                "limitations": ["缺少样本"],
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
