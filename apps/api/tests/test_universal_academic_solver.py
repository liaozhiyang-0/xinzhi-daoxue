from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from app.agents import AgentRegistry, TaskRouter
from app.capabilities import default_capability_registry
from app.contracts import AgentRequest, AttachmentRef, Intent, ModelResponse, ModelUsage
from app.contracts.solver import AcademicProblem
from app.core.config import Settings
from app.courses import default_course_registry
from app.orchestrator.graphs import AcademicProblemSolverGraph
from app.services.academic_solver_service import AcademicProblemSolverService
from app.services.model_registry import ModelRegistry
from app.tools import default_tool_registry
from PIL import Image


def graph() -> AcademicProblemSolverGraph:
    return AcademicProblemSolverGraph(
        default_course_registry(),
        default_capability_registry(),
        default_tool_registry(),
    )


def safe_png_bytes(color: str = "white") -> bytes:
    output = BytesIO()
    Image.new("RGB", (160, 100), color).save(output, format="PNG")
    return output.getvalue()


def test_course_registry_loads_first_wave_and_unknown_fallback() -> None:
    registry = default_course_registry()

    assert registry.get("CT").implementation_status == "implemented"
    assert registry.get("AE").implementation_status == "basic"
    assert registry.get("DE").implementation_status == "basic"
    assert registry.get("SS").implementation_status == "basic"
    assert registry.get("not-a-course").course_code == "UNKNOWN"


def test_academic_text_reasoning_prefers_spark_with_qwen_fallback() -> None:
    registry = ModelRegistry(Settings(app_env="test", _env_file=None))
    route = registry.get_route("academic_problem_solving")

    assert route.primary == "spark_reasoner"
    assert route.fallback == "qwen_vision_primary"


@pytest.mark.parametrize(
    ("course", "text", "expected_type"),
    [
        ("CT", "用节点电压法求解", "node_voltage"),
        ("AE", "判断二极管工作状态", "diode_circuit"),
        ("DE", "化简逻辑函数", "logic_simplification"),
        ("SS", "计算两个信号的卷积", "convolution"),
    ],
)
def test_one_graph_selects_different_course_packs(
    course: str, text: str, expected_type: str
) -> None:
    result = graph().run(
        AcademicProblem(
            course=course,
            problem_text=text,
            extraction_confidence=0.9,
        )
    )

    assert result.course == course
    assert result.problem_type == expected_type
    assert result.status == "partial"


@pytest.mark.parametrize(
    ("course", "text", "expected_type"),
    [
        ("CT", "为什么电容电压不能突变？", "first_order"),
        ("CT", "使用 KCL 列写节点方程", "kcl_kvl"),
        ("CT", "用相量法求正弦稳态响应", "sinusoidal_steady_state"),
        ("CT", "求 RC 一阶电路的零状态响应", "first_order"),
        ("CT", "分析含受控源的复杂拓扑", "controlled_source"),
        ("AE", "判断二极管工作状态", "diode_circuit"),
        ("AE", "计算 BJT 静态工作点", "bjt_bias"),
        ("AE", "求理想运放的输出电压", "op_amp"),
        ("DE", "化简逻辑函数", "logic_simplification"),
        ("DE", "分析组合逻辑电路", "combinational_logic"),
        ("DE", "分析简单时序逻辑", "sequential_logic"),
        ("SS", "计算两个信号的卷积", "convolution"),
        ("SS", "判断系统是否线性时不变", "system_properties"),
        ("SS", "计算简单拉普拉斯变换", "laplace_transform"),
    ],
)
def test_requested_first_wave_problem_matrix(
    course: str, text: str, expected_type: str
) -> None:
    result = graph().run(
        AcademicProblem(
            course=course,
            problem_text=text,
            extraction_confidence=0.9,
        )
    )

    assert result.course == course
    assert result.problem_type == expected_type
    assert result.status == "partial"


def test_ct_equation_uses_deterministic_shared_tool() -> None:
    result = graph().run(
        AcademicProblem(
            course="CT",
            problem_text="已知 2*x=4，求 x",
            equations_given=["2*x=4"],
            target_quantities=[{"name": "x"}],
            extraction_confidence=0.95,
        )
    )

    assert result.status == "success"
    assert result.execution_path == "FAST"
    assert result.tool_verification[0]["deterministic"] is True
    assert result.tool_verification[0]["tool_id"] == "linear_equation_solver"


def test_ct_high_risk_path_exposes_frozen_cloud_baseline_target() -> None:
    result = graph().run(
        AcademicProblem(
            course="CT",
            problem_text="根据两张存在冲突的受控源电路图求解",
            figures_given=[{"file_id": "one"}, {"file_id": "two"}],
            source_conflicts=[{"description": "受控源方向不一致"}],
            extraction_confidence=0.5,
        )
    )

    assert result.execution_path == "HIGH_RISK"
    assert result.fallback_target == "SOLVER_CT_V1"
    assert result.fallback_used is False


@pytest.mark.parametrize("course", ["CT", "AE", "DE", "SS"])
def test_all_courses_route_to_same_solver_agent(course: str) -> None:
    registry = AgentRegistry()
    decision = TaskRouter(
        registry, Settings(app_env="test", rag_enabled=False, _env_file=None)
    ).route(
        AgentRequest(
            session_id="session",
            user_id="user",
            course_id=course,
            intent=Intent.SOLVE_PROBLEM,
            canonical_input={"text": "请计算并给出结果"},
        )
    )

    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"


@pytest.mark.asyncio
async def test_service_adapts_existing_agent_request_contract() -> None:
    service = AcademicProblemSolverService(graph())
    result = await service.run(
        AgentRequest(
            session_id="session",
            user_id="user",
            course_id="AE",
            intent=Intent.SOLVE_PROBLEM,
            canonical_input={"text": "判断二极管工作状态"},
        )
    )

    assert result.agent_id == "ACADEMIC_PROBLEM_SOLVER"
    assert result.provider == "local_graph"
    assert result.structured_result["course"] == "AE"


@pytest.mark.asyncio
async def test_image_input_uses_vision_summary_without_storing_base64() -> None:
    class FakeRegistry:
        @staticmethod
        def get_route(_task_type: str) -> object:
            return type("Route", (), {"primary": "model"})()

        @staticmethod
        def get_model(_alias: str) -> object:
            return type("Definition", (), {"provider": "fake"})()

        @staticmethod
        def enabled(_definition: object) -> bool:
            return True

    class FakeModelService:
        registry = FakeRegistry()
        providers = {"fake": type("Provider", (), {"available": True})()}
        settings = Settings(app_env="test", _env_file=None)

        @staticmethod
        async def analyze_images_for_task(
            *_args: object, **_kwargs: object
        ) -> ModelResponse:
            return ModelResponse(
                provider="fake",
                model="vision",
                content="识别到受控源与参考方向标注",
                elapsed_ms=5,
            )

        @staticmethod
        async def generate_for_task(*_args: object, **_kwargs: object) -> ModelResponse:
            return ModelResponse(
                provider="fake",
                model="reasoner",
                content="根据可观察信息给出条件化解答。",
                elapsed_ms=7,
            )

    class FakeStorage:
        @staticmethod
        async def read(_storage_key: str) -> bytes:
            return safe_png_bytes()

    service = AcademicProblemSolverService(
        graph(),
        FakeModelService(),
        FakeStorage(),  # type: ignore[arg-type]
    )
    result = await service.run(
        AgentRequest(
            session_id="session",
            user_id="user",
            course_id="CT",
            intent=Intent.SOLVE_PROBLEM,
            canonical_input={"text": "请分析图片中的电路"},
            attachments=[
                AttachmentRef(
                    file_id="image",
                    filename="circuit.png",
                    content_type="image/png",
                    size_bytes=16,
                    storage_key="local:image",
                )
            ],
        )
    )

    assert result.structured_result["vision_execution"]["model"] == "vision"
    assert result.structured_result["model_execution"]["model"] == "reasoner"
    assert "base64" not in str(result.structured_result).casefold()
    assert result.metrics.model_calls == 2


@pytest.mark.asyncio
async def test_simple_multi_image_solver_stitches_before_vision_model() -> None:
    class FakeRegistry:
        @staticmethod
        def get_route(_task_type: str) -> object:
            return type("Route", (), {"primary": "model"})()

        @staticmethod
        def get_model(_alias: str) -> object:
            return type("Definition", (), {"provider": "fake"})()

        @staticmethod
        def enabled(_definition: object) -> bool:
            return True

    class FakeModelService:
        registry = FakeRegistry()
        providers = {"fake": type("Provider", (), {"available": True})()}
        settings = Settings(
            app_env="test",
            multi_image_stitch_max_images=4,
            _env_file=None,
        )

        def __init__(self) -> None:
            self.vision_image_counts: list[int] = []

        async def analyze_images_for_task(
            self, *_args: object, **kwargs: object
        ) -> ModelResponse:
            images = kwargs["images"]
            self.vision_image_counts.append(len(images))
            return ModelResponse(
                provider="fake",
                model="vision",
                content="组合图包含连续的题干与电路图。",
                elapsed_ms=5,
            )

        @staticmethod
        async def generate_for_task(*_args: object, **_kwargs: object) -> ModelResponse:
            return ModelResponse(
                provider="fake",
                model="reasoner",
                content="根据组合图信息完成解答。",
                elapsed_ms=7,
            )

    class FakeStorage:
        @staticmethod
        async def read(storage_key: str) -> bytes:
            return safe_png_bytes("white" if storage_key.endswith("1") else "gray")

    model_service = FakeModelService()
    service = AcademicProblemSolverService(
        graph(),
        model_service,  # type: ignore[arg-type]
        FakeStorage(),  # type: ignore[arg-type]
    )
    result = await service.run(
        AgentRequest(
            session_id="session",
            user_id="user",
            course_id="CT",
            intent=Intent.SOLVE_PROBLEM,
            canonical_input={"text": "结合两张图完成题目"},
            attachments=[
                AttachmentRef(
                    file_id=str(index),
                    filename=f"{index}.png",
                    content_type="image/png",
                    size_bytes=100,
                    storage_key=f"local:{index}",
                )
                for index in (1, 2)
            ],
        )
    )

    execution = result.structured_result["vision_execution"]
    assert execution["strategy"] == "stitched"
    assert execution["source_image_count"] == 2
    assert execution["model_image_count"] == 1
    assert model_service.vision_image_counts == [1]
    assert result.metrics.model_calls == 2


@pytest.mark.asyncio
async def test_complex_multi_image_solver_recognizes_each_then_summarizes() -> None:
    class FakeRegistry:
        @staticmethod
        def get_route(_task_type: str) -> object:
            return type("Route", (), {"primary": "model"})()

        @staticmethod
        def get_model(_alias: str) -> object:
            return type("Definition", (), {"provider": "fake"})()

        @staticmethod
        def enabled(_definition: object) -> bool:
            return True

    class FakeModelService:
        registry = FakeRegistry()
        providers = {"fake": type("Provider", (), {"available": True})()}
        settings = Settings(
            app_env="test",
            multi_image_stitch_max_images=2,
            multi_image_fallback_concurrency=2,
            _env_file=None,
        )

        def __init__(self) -> None:
            self.vision_image_counts: list[int] = []
            self.text_task_types: list[str] = []

        async def analyze_images_for_task(
            self, *_args: object, **kwargs: object
        ) -> ModelResponse:
            images = kwargs["images"]
            self.vision_image_counts.append(len(images))
            return ModelResponse(
                provider="fake",
                model="vision",
                content=f"识别结果 {len(self.vision_image_counts)}",
                elapsed_ms=5,
            )

        async def generate_for_task(
            self, task_type: str, **_kwargs: object
        ) -> ModelResponse:
            self.text_task_types.append(task_type)
            content = (
                "三张图按顺序组成完整题目。"
                if task_type == "multi_image_summary"
                else "根据多图汇总完成解答。"
            )
            return ModelResponse(
                provider="fake",
                model="reasoner",
                content=content,
                elapsed_ms=7,
            )

    class FakeStorage:
        @staticmethod
        async def read(storage_key: str) -> bytes:
            colors = {"local:1": "white", "local:2": "gray", "local:3": "blue"}
            return safe_png_bytes(colors[storage_key])

    model_service = FakeModelService()
    service = AcademicProblemSolverService(
        graph(),
        model_service,  # type: ignore[arg-type]
        FakeStorage(),  # type: ignore[arg-type]
    )
    result = await service.run(
        AgentRequest(
            session_id="session",
            user_id="user",
            course_id="CT",
            intent=Intent.SOLVE_PROBLEM,
            canonical_input={"text": "结合三张图完成题目"},
            attachments=[
                AttachmentRef(
                    file_id=str(index),
                    filename=f"{index}.png",
                    content_type="image/png",
                    size_bytes=100,
                    storage_key=f"local:{index}",
                )
                for index in (1, 2, 3)
            ],
        )
    )

    execution = result.structured_result["vision_execution"]
    assert execution["strategy"] == "per_image"
    assert execution["fallback_reason"] == "image_count_exceeds_stitch_limit"
    assert execution["source_image_count"] == 3
    assert execution["summary_execution"]["status"] == "completed"
    assert model_service.vision_image_counts == [1, 1, 1]
    assert model_service.text_task_types == [
        "multi_image_summary",
        "academic_problem_solving",
    ]
    assert result.metrics.model_calls == 5


class FakeAcademicRegistry:
    @staticmethod
    def get_route(_task_type: str) -> object:
        return type("Route", (), {"primary": "model"})()

    @staticmethod
    def get_model(_alias: str) -> object:
        return type("Definition", (), {"provider": "fake"})()

    @staticmethod
    def enabled(_definition: object) -> bool:
        return True


class SequencedAcademicModelService:
    registry = FakeAcademicRegistry()
    providers = {"fake": type("Provider", (), {"available": True})()}

    def __init__(self, responses: list[ModelResponse], *, continuations: int) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []
        self.settings = Settings(
            app_env="test",
            iflytek_spark_max_tokens=4096,
            academic_solver_max_tokens=4096,
            academic_solver_max_continuations=continuations,
            academic_solver_timeout_seconds=180,
            _env_file=None,
        )

    async def generate_for_task(
        self, *_args: object, **kwargs: object
    ) -> ModelResponse:
        self.calls.append(kwargs)
        return self.responses[len(self.calls) - 1]


@pytest.mark.asyncio
async def test_solver_continues_when_model_reaches_output_limit() -> None:
    model_service = SequencedAcademicModelService(
        [
            ModelResponse(
                provider="fake",
                model="reasoner",
                content="### 第一步\n完整内容。\n\n### 第二步\n$$ x_",
                elapsed_ms=5,
                finish_reason="length",
                usage=ModelUsage(completion_tokens=4096),
            ),
            ModelResponse(
                provider="fake",
                model="reasoner",
                content="$$x=2$$\n\n其余小问与能量平衡已完成。",
                elapsed_ms=7,
                finish_reason="stop",
                usage=ModelUsage(completion_tokens=42),
            ),
        ],
        continuations=2,
    )
    service = AcademicProblemSolverService(graph(), model_service)  # type: ignore[arg-type]

    result = await service.run(
        AgentRequest(
            session_id="session",
            user_id="user",
            course_id="CT",
            intent=Intent.SOLVE_PROBLEM,
            canonical_input={"text": "求解二阶动态电路并验证能量平衡"},
        )
    )

    execution = result.structured_result["model_execution"]
    assert "### 续答（第 1 部分）" in result.answer
    assert "$$ x_" not in result.answer
    assert execution["output_status"] == "complete"
    assert execution["model_calls"] == 2
    assert execution["continuation_count"] == 1
    assert execution["finish_reasons"] == ["length", "stop"]
    assert result.metrics.model_calls == 2
    assert all(
        call["extra_options"] == {"max_tokens": 4096, "timeout": 180.0}
        for call in model_service.calls
    )
    assert execution["timeout_seconds_per_call"] == 180.0


@pytest.mark.asyncio
async def test_solver_marks_partial_after_continuation_limit() -> None:
    model_service = SequencedAcademicModelService(
        [
            ModelResponse(
                provider="fake",
                model="reasoner",
                content="第一部分已完成。\n\n$$ y_",
                elapsed_ms=4,
                finish_reason="length",
            ),
            ModelResponse(
                provider="fake",
                model="reasoner",
                content="继续推导，但仍未结束。\n\n$$ z_",
                elapsed_ms=6,
                finish_reason="length",
            ),
        ],
        continuations=1,
    )
    service = AcademicProblemSolverService(graph(), model_service)  # type: ignore[arg-type]

    result = await service.run(
        AgentRequest(
            session_id="session",
            user_id="user",
            course_id="CT",
            intent=Intent.SOLVE_PROBLEM,
            canonical_input={"text": "求解较长的电路综合题"},
        )
    )

    execution = result.structured_result["model_execution"]
    assert execution["output_status"] == "partial"
    assert execution["model_calls"] == 2
    assert result.structured_result["status"] == "partial"
    assert "仍可能不完整" in "；".join(result.warnings)
    assert result.answer.count("$$") % 2 == 0


@pytest.mark.asyncio
async def test_long_solver_continues_until_completion_marker() -> None:
    marker = AcademicProblemSolverService.completion_marker
    model_service = SequencedAcademicModelService(
        [
            ModelResponse(
                provider="fake",
                model="reasoner",
                content="前半部分以完整句号结束，但还有小问没有回答。",
                elapsed_ms=4,
                finish_reason="stop",
            ),
            ModelResponse(
                provider="fake",
                model="reasoner",
                content=f"后半部分和能量平衡已经完成。\n{marker}",
                elapsed_ms=6,
                finish_reason="stop",
            ),
        ],
        continuations=2,
    )
    service = AcademicProblemSolverService(graph(), model_service)  # type: ignore[arg-type]

    result = await service.run(
        AgentRequest(
            session_id="session",
            user_id="user",
            course_id="CT",
            intent=Intent.SOLVE_PROBLEM,
            canonical_input={"text": "含受控源的综合动态电路。" * 120},
        )
    )

    execution = result.structured_result["model_execution"]
    assert execution["output_status"] == "complete"
    assert execution["model_calls"] == 2
    assert "### 续答（第 1 部分）" in result.answer
    assert marker not in result.answer


def test_unclosed_formula_overrides_stop_finish_reason() -> None:
    response = ModelResponse(
        provider="fake",
        model="reasoner",
        content=("完整推导。" * 120) + "\n$$ x_",
        elapsed_ms=1,
        finish_reason="stop",
    )

    assert AcademicProblemSolverService._response_truncated(response, 4096) is True


def test_architecture_has_one_graph_state_and_no_direct_model_in_course_packs() -> None:
    app_root = Path(__file__).parents[1] / "app"
    state_defs: list[str] = []
    for path in app_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "class XZDGraphState(" in source:
            state_defs.append(str(path))
    assert len(state_defs) == 1

    course_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (app_root / "courses").rglob("*.py")
    )
    assert "AsyncOpenAI" not in course_source
    assert "ModelService(" not in course_source


def test_legacy_solver_is_an_adapter_not_a_second_core() -> None:
    path = Path(__file__).parents[1] / "app" / "agents" / "solver_ct" / "local_graph.py"
    source = path.read_text(encoding="utf-8")

    assert "AcademicProblemSolverGraph" in source
    assert "class CircuitSolverState" not in source
    assert "StateGraph" not in source
