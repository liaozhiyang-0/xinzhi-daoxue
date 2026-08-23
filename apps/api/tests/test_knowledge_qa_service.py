import json
from pathlib import Path
from typing import Any

from app.contracts import AgentRequest, ModelResponse, RetrievalResult
from app.contracts.learning import LearningPathDraft
from app.services.knowledge_qa_service import DISCLAIMER, KnowledgeQAService
from app.services.retrieval_context import RetrievalContextService

from tests.knowledge_test_utils import make_service


class _UnexpectedModelService:
    async def generate_for_task(self, *_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("cloud/model generation must not run")


class _RecordingContextService(RetrievalContextService):
    def __init__(self) -> None:
        super().__init__(2000)
        self.last_query_override: str | None = None

    def build(self, result: RetrievalResult, **kwargs: object):  # type: ignore[no-untyped-def]
        value = kwargs.get("query_override")
        self.last_query_override = value if isinstance(value, str) else None
        return super().build(result, **kwargs)  # type: ignore[arg-type]


class _RecordingModelService:
    def __init__(
        self,
        content: str = "整理结果 [S1]",
        provider: str = "test-model",
    ) -> None:
        self.content = content
        self.provider = provider
        self.task_type = ""
        self.messages: list[dict[str, Any]] = []

    async def generate_for_task(self, task_type: str, **kwargs: Any) -> ModelResponse:
        self.task_type = task_type
        self.messages = list(kwargs["messages"])
        return ModelResponse(
            provider=self.provider,
            model="test-governance-model",
            content=self.content,
            elapsed_ms=1,
        )

    async def generate_json_for_task(
        self, task_type: str, **kwargs: Any
    ) -> ModelResponse:
        self.task_type = task_type
        self.messages = list(kwargs["messages"])
        return ModelResponse(
            provider=self.provider,
            model="test-learning-path-model",
            content=json.dumps(
                {
                    "evidence_summary": "三次作答记录显示分数下降。[S1]",
                    "weak_knowledge_points": [
                        {
                            "knowledge_point": "参考方向符号",
                            "basis": "用户明确描述反复写反",
                            "confidence": "tentative",
                        }
                    ],
                    "prerequisite_path": ["符号约定", "KCL", "方程自检"],
                    "staged_plan": [
                        {"day": 1, "goal": "复习符号约定", "duration_minutes": 20}
                    ],
                    "verification_tasks": ["完成一道新题", "提交符号自检"],
                    "completion_evidence": ["提交独立完成的新题推导"],
                    "teacher_intervention_points": ["连续两次验证仍错误时复核"],
                },
                ensure_ascii=False,
            ),
            elapsed_ms=1,
        )


def test_knowledge_output_normalizes_math_but_preserves_verilog_monitor(
    tmp_path: Path,
) -> None:
    service = KnowledgeQAService(
        make_service(
            tmp_path,
            {
                "CT": {
                    "math.md": (
                        "# KCL\n"
                        "节点方程为 \\(i_1+i_2=i_3\\)。\n"
                        "\\[\\begin{bmatrix}i_1\\\\i_2\\end{bmatrix}=b\\]\n"
                        "```verilog\n"
                        '$monitor("v=%0d", v);\n'
                        "```\n"
                    )
                }
            },
        ),
        RetrievalContextService(2000),
    )
    request = AgentRequest(
        session_id="s-math-output",
        user_id="u-math-output",
        scene="learning",
        course_id="CT",
        intent="general_qa",
        canonical_input={"question": "KCL"},
        options={"allow_cloud": False},
    )

    execution = service.run("LEARN_01_LOCAL_RETRIEVAL_V1", request)

    assert execution.result.answer
    assert "\\(" not in execution.result.answer
    assert "\\[" not in execution.result.answer
    assert "$i_1+i_2=i_3$" in execution.result.answer
    assert '$monitor("v=%0d", v);' in execution.result.answer
    assert execution.result.structured_result["math_rendering"]["status"] in {
        "passed",
        "needs_review",
    }


async def test_knowledge_qa_skips_generation_when_cloud_is_disabled(
    tmp_path: Path,
) -> None:
    kb = make_service(
        tmp_path,
        {"CT": {"chapter.md": "# Capacitor\nCapacitor voltage is continuous."}},
    )
    service = KnowledgeQAService(
        kb,
        RetrievalContextService(2000),
        model_service=_UnexpectedModelService(),  # type: ignore[arg-type]
    )
    request = AgentRequest(
        session_id="s1",
        user_id="u1",
        scene="learning",
        course_id="CT",
        intent="general_qa",
        canonical_input={"question": "What is capacitor voltage continuity?"},
        options={"allow_cloud": False},
    )

    execution = await service.run_with_generation(
        "LEARN_01_LOCAL_RETRIEVAL_V1", request
    )

    assert execution.result.provider == "local"
    assert execution.result.structured_result["mode"] == "retrieval_only"


async def test_governance_uses_model_to_organize_input_and_evidence(
    tmp_path: Path,
) -> None:
    model = _RecordingModelService()
    service = KnowledgeQAService(
        make_service(
            tmp_path,
            {"CT": {"governance.md": "# 节点电压法\n课程资产版本需要逐项复核。"}},
        ),
        RetrievalContextService(2000),
        model_service=model,  # type: ignore[arg-type]
    )
    request = AgentRequest(
        session_id="s-governance",
        user_id="u-governance",
        scene="teaching",
        course_id="CT",
        intent="summarize_knowledge",
        scenario_id="department_knowledge_governance_v1",
        canonical_input={
            "text": "讲义《节点电压法》v3、练习题包《直流网络》v2、教师修订说明 v1"
        },
        options={"scenario_id": "department_knowledge_governance_v1"},
    )

    execution = await service.run_with_generation(
        "LEARN_01_LOCAL_RETRIEVAL_V1", request
    )

    assert model.task_type == "knowledge_answer"
    assert "节点电压法" in model.messages[1]["content"]
    assert execution.result.structured_result["mode"] == "governance_model_generation"
    assert execution.result.provider == "test-model"
    assert execution.result.citations == ["kb://CT/governance.md#chunk-1"]
    assert execution.result.metrics.provider_latency_ms == 1
    assert execution.result.metrics.model_latency_ms == 1
    assert execution.result.structured_result["synthesis_trace"] == {
        "task_type": "knowledge_answer",
        "raw_request_included": True,
        "evidence_ids": ["S1"],
        "source_refs": ["kb://CT/governance.md#chunk-1"],
    }


async def test_governance_model_runs_even_without_retrieved_chunks(
    tmp_path: Path,
) -> None:
    model = _RecordingModelService("只依据输入资产记录整理；无课程证据。")
    service = KnowledgeQAService(
        make_service(tmp_path, {"CT": {"unrelated.md": "完全无关的章节。"}}),
        RetrievalContextService(2000),
        model_service=model,  # type: ignore[arg-type]
    )
    request = AgentRequest(
        session_id="s-governance-empty",
        user_id="u-governance-empty",
        scene="teaching",
        course_id="CT",
        intent="summarize_knowledge",
        canonical_input={"text": "资产清单：讲义《节点电压法》v3"},
        options={"scenario_id": "department_knowledge_governance_v1"},
    )

    execution = await service.run_with_generation(
        "LEARN_01_LOCAL_RETRIEVAL_V1", request
    )

    assert model.messages
    assert "未检索到课程证据" in model.messages[1]["content"]
    assert execution.result.structured_result["mode"] == "governance_model_generation"


async def test_governance_never_presents_local_text_when_model_is_unavailable(
    tmp_path: Path,
) -> None:
    service = KnowledgeQAService(
        make_service(tmp_path, {"CT": {"governance.md": "课程资产记录。"}}),
        RetrievalContextService(2000),
    )
    request = AgentRequest(
        session_id="s-governance-no-model",
        user_id="u-governance-no-model",
        scene="teaching",
        course_id="CT",
        intent="summarize_knowledge",
        canonical_input={"text": "资产清单：讲义《节点电压法》v3"},
        options={"scenario_id": "department_knowledge_governance_v1"},
    )

    execution = await service.run_with_generation(
        "LEARN_01_LOCAL_RETRIEVAL_V1", request
    )

    assert execution.result.answer == ""
    assert execution.result.structured_result["mode"] == "governance_model_required"
    assert execution.result.structured_result["publishable"] is False
    assert any("必须经过大模型整理" in warning for warning in execution.result.warnings)


async def test_governance_rejects_mock_model_as_publishable_synthesis(
    tmp_path: Path,
) -> None:
    service = KnowledgeQAService(
        make_service(tmp_path, {"CT": {"governance.md": "课程资产记录。"}}),
        RetrievalContextService(2000),
        model_service=_RecordingModelService(provider="mock"),  # type: ignore[arg-type]
    )
    request = AgentRequest(
        session_id="s-governance-mock",
        user_id="u-governance-mock",
        scene="teaching",
        course_id="CT",
        intent="summarize_knowledge",
        canonical_input={"text": "资产清单：讲义《节点电压法》v3"},
        options={"scenario_id": "department_knowledge_governance_v1"},
    )

    execution = await service.run_with_generation(
        "LEARN_01_LOCAL_RETRIEVAL_V1", request
    )

    assert execution.result.structured_result["mode"] == "governance_model_required"
    assert execution.result.fallback_reason == "model_generation_mock"


async def test_learning_path_synthesizes_user_evidence_without_local_chunks(
    tmp_path: Path,
) -> None:
    model = _RecordingModelService("证据摘要：三次分数下降；薄弱点暂定为参考方向符号。")
    service = KnowledgeQAService(
        make_service(tmp_path, {"CT": {"unrelated.md": "完全无关的章节。"}}),
        RetrievalContextService(2000),
        model_service=model,  # type: ignore[arg-type]
    )
    request = AgentRequest(
        session_id="s-learning-path",
        user_id="u-learning-path",
        scene="learning",
        course_id="CT",
        intent="learning_advice",
        scenario_id="student_learning_path_v1",
        canonical_input={"text": "三次KCL得分80、60、40，参考方向题经常写反。"},
        options={"scenario_id": "student_learning_path_v1"},
    )

    execution = await service.run_with_generation(
        "LEARN_01_LOCAL_RETRIEVAL_V1", request
    )

    assert model.messages
    assert "三次KCL得分" in model.messages[1]["content"]
    assert execution.result.structured_result["mode"] == (
        "learning_path_model_generation"
    )
    assert execution.result.answer.startswith("证据摘要")


async def test_learning_path_preserves_requested_two_week_horizon(
    tmp_path: Path,
) -> None:
    model = _RecordingModelService()
    service = KnowledgeQAService(
        make_service(tmp_path, {"AE": {"unrelated.md": "无关资料。"}}),
        RetrievalContextService(2000),
        model_service=model,  # type: ignore[arg-type]
    )
    request = AgentRequest(
        session_id="s-learning-two-week",
        user_id="u-learning-two-week",
        scene="learning",
        course_id="AE",
        intent="learning_advice",
        scenario_id="student_learning_path_v1",
        canonical_input={
            "text": "请制定为期两周的BJT静态工作点与动态参数专项复习计划。"
        },
        options={"scenario_id": "student_learning_path_v1"},
    )

    execution = await service.run_with_generation(
        "LEARN_01_LOCAL_RETRIEVAL_V1", request
    )

    assert "至少14天" in model.messages[0]["content"]
    assert execution.result.business_data["plan_horizon_check"] == {
        "status": "mismatch",
        "requested_days": 14,
        "planned_days": 1,
        "reason": "模型计划未覆盖请求的完整周期",
    }


def test_learning_path_normalizes_provider_object_shaped_plan() -> None:
    draft = LearningPathDraft.model_validate(
        {
            "evidence_summary": "输入证据有限",
            "weak_knowledge_points": ["BJT静态工作点"],
            "prerequisite_path": ["器件基础"],
            "staged_plan": {
                "day_1": {"focus": "复盘静态工作点"},
                "day_2": {"focus": "验证动态参数"},
            },
            "verification_tasks": ["计算Q点", "完成测量记录"],
            "completion_evidence": ["提交复盘记录"],
            "teacher_intervention_points": ["测量异常时复核"],
        }
    )

    assert draft.staged_plan[0]["day"] == 1
    assert draft.staged_plan[1]["day"] == 2


def test_learning_path_flattens_nested_week_plan() -> None:
    payload = {
        "evidence_summary": "输入证据有限",
        "weak_knowledge_points": ["BJT静态工作点"],
        "prerequisite_path": ["器件基础"],
        "staged_plan": {
            "week_1": {
                "day_1": "复盘静态工作点",
                "day_2": "验证动态参数",
            },
            "week_2": {
                "day_8": "完成测量记录",
                "day_14": "综合复测",
            },
        },
        "verification_tasks": ["计算Q点", "完成测量记录"],
        "completion_evidence": ["提交复盘记录"],
        "teacher_intervention_points": ["测量异常时复核"],
    }

    draft = LearningPathDraft.model_validate(payload)

    assert len(draft.staged_plan) == 4
    assert [item["day"] for item in draft.staged_plan] == [1, 2, 8, 14]


def test_learning_path_preserves_outer_week_markers() -> None:
    payload = {
        "evidence_summary": "输入证据有限",
        "weak_knowledge_points": ["Buck闭环"],
        "prerequisite_path": ["电源基础"],
        "staged_plan": {
            "week_1": {"focus": "闭环建模"},
            "week_2": {"focus": "PCB抗干扰"},
        },
        "verification_tasks": ["完成仿真", "记录波形"],
        "completion_evidence": ["提交实验记录"],
        "teacher_intervention_points": ["上电前复核"],
    }

    draft = LearningPathDraft.model_validate(payload)

    assert [item["week"] for item in draft.staged_plan] == [1, 2]


async def test_learning_path_does_not_publish_local_only_result_without_model(
    tmp_path: Path,
) -> None:
    service = KnowledgeQAService(
        make_service(tmp_path, {"CT": {"chapter.md": "课程资料。"}}),
        RetrievalContextService(2000),
    )
    request = AgentRequest(
        session_id="s-learning-path-no-model",
        user_id="u-learning-path-no-model",
        scene="learning",
        course_id="CT",
        intent="learning_advice",
        scenario_id="student_learning_path_v1",
        canonical_input={"text": "三次练习分数下降，想要7天学习路径。"},
        options={"scenario_id": "student_learning_path_v1"},
    )

    execution = await service.run_with_generation(
        "LEARN_01_LOCAL_RETRIEVAL_V1", request
    )

    assert execution.result.answer == ""
    assert execution.result.structured_result["mode"] == (
        "learning_path_model_required"
    )
    assert execution.result.fallback_reason == "model_service_not_configured"


def test_local_knowledge_qa_is_explicitly_retrieval_only(tmp_path: Path) -> None:
    kb = make_service(
        tmp_path, {"CT": {"chapter.md": "# 戴维南定理\n线性含源一端口网络可以等效。"}}
    )
    service = KnowledgeQAService(kb, RetrievalContextService(2000))
    request = AgentRequest(
        session_id="s1",
        user_id="u1",
        scene="learning",
        course_id="CT",
        intent="general_qa",
        canonical_input={"question": "什么是戴维南定理"},
    )

    execution = service.run("LEARN_01_LOCAL_RETRIEVAL_V1", request)

    assert execution.result.provider == "local"
    assert execution.result.structured_result["mode"] == "retrieval_only"
    assert DISCLAIMER in execution.result.warnings
    assert "本地资料依据" in execution.result.answer
    assert execution.result.citations[0].startswith("kb://CT/")


def test_knowledge_qa_falls_back_to_local_lexical_search_when_rag_fails(
    tmp_path: Path,
) -> None:
    kb = make_service(
        tmp_path,
        {
            "AE": {
                "chapter.md": (
                    "# Switching regulator\n"
                    "A switching regulator controls output voltage with a "
                    "high-frequency "
                    "switch and an inductor."
                )
            }
        },
    )

    class BrokenRag:
        def search(self, **_: object) -> object:
            raise RuntimeError("embedding service unavailable")

    request = AgentRequest(
        session_id="s1",
        user_id="u1",
        scene="learning",
        course_id="AE",
        intent="explain_concept",
        canonical_input={"question": "switching regulator"},
    )
    execution = KnowledgeQAService(
        kb,
        RetrievalContextService(2000),
        rag_retrieval=BrokenRag(),  # type: ignore[arg-type]
    ).run("LEARN_01_LOCAL_RETRIEVAL_V1", request)

    assert execution.retrieval.hits
    assert "local_lexical_fallback:RuntimeError" in execution.retrieval.warnings
    assert "本地资料依据" in execution.result.answer
    assert "[S1]" in execution.result.answer


def test_knowledge_qa_compatibility_path_preserves_user_query_for_filtering(
    tmp_path: Path,
) -> None:
    context_service = _RecordingContextService()
    service = KnowledgeQAService(
        make_service(tmp_path, {"CT": {"chapter.md": "课程资料"}}),
        context_service,
    )
    request = AgentRequest(
        session_id="s-compat-query",
        user_id="u-compat-query",
        scene="teaching",
        course_id="CT",
        intent="lesson_prep",
        canonical_input={
            "question": "请设计电容电压连续性的课堂教案，并给出课程资料依据。"
        },
    )
    retrieval = RetrievalResult(
        query="电路理论",
        normalized_query="电路理论",
        course_ids=["CT"],
        latency_ms=0,
    )

    service.from_retrieval("LEARN_01_LOCAL_RETRIEVAL_V1", request, retrieval)

    assert (
        context_service.last_query_override
        == "请设计电容电压连续性的课堂教案，并给出课程资料依据。"
    )
