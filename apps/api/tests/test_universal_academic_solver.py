from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.agents import AgentRegistry, TaskRouter
from app.capabilities import default_capability_registry
from app.contracts import AgentRequest, AttachmentRef, Intent, ModelResponse, ModelUsage
from app.contracts.solver import AcademicProblem
from app.core.config import Settings
from app.courses import default_course_registry
from app.orchestrator.graphs import AcademicProblemSolverGraph
from app.orchestrator.state import new_graph_state
from app.services.academic_solver_service import AcademicProblemSolverService
from app.services.model_registry import ModelRegistry
from app.services.solver_boundary_policy import SolverBoundaryPolicy
from app.tools import default_tool_registry
from langgraph.checkpoint.memory import InMemorySaver
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


def test_visual_solver_requires_structured_topology_before_calculation() -> None:
    policy = SolverBoundaryPolicy()
    incomplete = AcademicProblem(
        course="CT",
        problem_text="请分析图片中的电路",
        figures_given=[{"file_id": "image-1"}],
    )
    decision = policy.evaluate(incomplete)

    assert decision.intercepted
    assert decision.reason == "visual_topology_not_structured"

    complete = incomplete.model_copy(
        update={
            "structure_status": "complete",
            "entities": [{"name": "R1", "value": "1kΩ"}],
            "relations": [{"from": "R1.1", "to": "GND"}],
        }
    )
    assert not policy.evaluate(complete).intercepted


def test_visual_route_preflight_accepts_available_fallback_model() -> None:
    class ModelServiceWithFallback:
        @staticmethod
        def preflight(task_type: str, *, modality: str) -> SimpleNamespace:
            assert task_type == "circuit_image_extraction"
            assert modality == "image"
            return SimpleNamespace(available=True)

    service = AcademicProblemSolverService(
        graph(), ModelServiceWithFallback()  # type: ignore[arg-type]
    )

    assert service._model_route_available("circuit_image_extraction") is True


def test_visual_json_extraction_builds_a_verified_topology() -> None:
    problem = AcademicProblem(
        course="CT",
        problem_text="请分析图片中的电路",
        figures_given=[{"file_id": "image-1"}],
    )
    merged, metadata = AcademicProblemSolverService._merge_visual_extraction(
        problem,
        (
            '{"recognized_text":["求 R1 电流"],'
            '"diagram_description":"R1 连接在 V1 与 GND 之间",'
            '"components":['
            '{"component_type":"resistor","label":"R1",'
            '"value":"1kΩ","connections":["V1","GND"],'
            '"terminal_map":{"left":"V1","right":"GND"},'
            '"certainty":"certain"}],'
            '"uncertain_info":[],"confidence":0.92}'
        ),
    )

    assert metadata["structured_extraction"] is True
    assert metadata["visual_structure_status"] == "complete"
    assert merged.structure_status == "complete"
    assert merged.entities[0]["label"] == "R1"
    assert merged.relations[0]["node"] == "V1"
    assert not SolverBoundaryPolicy().evaluate(merged).intercepted


def test_unstructured_visual_extraction_cannot_continue_to_reasoning() -> None:
    problem = AcademicProblem(
        course="CT",
        problem_text="请分析图片中的电路",
        figures_given=[{"file_id": "image-1"}],
    )

    merged, metadata = AcademicProblemSolverService._merge_visual_extraction(
        problem,
        "视觉模型只返回了自然语言摘要，未能输出结构化拓扑。",
    )

    assert metadata["structured_extraction"] is False
    assert metadata["visual_structure_status"] == "unstructured"
    assert metadata["visual_topology_validated"] is False
    assert "visual_extraction_unstructured" in metadata["visual_topology_issues"]
    assert merged.can_continue is False
    assert SolverBoundaryPolicy().evaluate(merged).reason == (
        "visual_topology_not_structured"
    )


def test_explicit_circuit_prompt_survives_unstructured_visual_extraction() -> None:
    problem = AcademicProblem(
        course="AE",
        problem_text=(
            "图中为理想运算放大器，反相端接地，同相端由输入 vi 经 "
            "R1=1 MΩ 串联后接到节点 vp，再由 R2=1 kΩ 接地，输出端接负载 RL；"
            "电源为 ±15 V。请判断反馈状态并推导 vp、vo 饱和方向和输出边界。"
        ),
        figures_given=[{"file_id": "image-1"}],
    )

    merged, metadata = AcademicProblemSolverService._merge_visual_extraction(
        problem,
        "视觉模型只返回了自然语言摘要，未能输出结构化拓扑。",
    )

    assert metadata["text_facts_fallback"] is True
    assert merged.can_continue is True
    assert not SolverBoundaryPolicy().evaluate(merged).intercepted


def test_generic_image_prompt_still_requires_structured_topology() -> None:
    assert not SolverBoundaryPolicy.has_explicit_textual_topology(
        "请分析图片中的电路并给出答案。"
    )


def test_real_provider_signal_aliases_are_normalized_without_circuit_topology() -> None:
    problem = AcademicProblem(
        course="SS",
        problem_text="请分析图片中的两个信号",
        figures_given=[{"file_id": "image-1"}],
    )
    merged, metadata = AcademicProblemSolverService._merge_visual_extraction(
        problem,
        (
            '{"recognized_text":["Q01"],'
            '"diagram_description":"两个矩形脉冲信号",'
            '"components":['
            '{"type":"signal_plot","label":"x(t)","shape":"rectangular_pulse",'
            '"amplitude":1,"start_time":0,"end_time":1},'
            '{"type":"signal_plot","label":"h(t)","shape":"rectangular_pulse",'
            '"amplitude":0.5,"start_time":0,"end_time":4}],'
            '"uncertain_info":[],"confidence":0.95}'
        ),
    )

    assert metadata["structured_extraction"] is True
    assert metadata["visual_structure_status"] == "complete"
    assert "x(t)" in merged.problem_text
    assert "support [0,1]" in merged.problem_text
    assert "support [0,4]" in merged.problem_text
    assert merged.can_continue is True


def test_explicit_signal_prompt_survives_uncertain_empty_visual_structure() -> None:
    problem = AcademicProblem(
        course="CT",
        problem_text=(
            "连续时间信号 x(t) 在 0≤t≤1 时幅值为1，h(t) 在 0≤t≤4 时幅值为0.5；"
            "求卷积 y(t)=x(t)*h(t)。"
        ),
        figures_given=[{"file_id": "image-1"}],
    )
    merged, metadata = AcademicProblemSolverService._merge_visual_extraction(
        problem,
        (
            '{"diagram_description":"无法确认图中拓扑", "components":[], '
            '"uncertain_info":["端点和节点连接不确定"], "confidence":1.0}'
        ),
    )

    assert metadata["visual_text_fallback"] is True
    assert metadata["visual_structure_status"] == "partial"
    assert metadata["visual_topology_validated"] is False
    assert merged.can_continue is True


def test_visual_extraction_requires_terminal_map_for_connected_components() -> None:
    merged, metadata = AcademicProblemSolverService._merge_visual_extraction(
        AcademicProblem(
            course="CT",
            problem_text="请分析图片中的电路",
            figures_given=[{"file_id": "image-1"}],
        ),
        (
            '{"diagram_description":"R1连接V1和GND",'
            '"components":[{"component_type":"resistor","label":"R1",'
            '"connections":["V1","GND"],"certainty":"certain"}],'
            '"confidence":0.95}'
        ),
    )

    assert metadata["visual_topology_validated"] is False
    assert "visual_component_missing_terminal_map" in (
        metadata["visual_topology_issues"]
    )
    assert merged.can_continue is False


def test_visual_extraction_requires_orientation_for_source_components() -> None:
    _, metadata = AcademicProblemSolverService._merge_visual_extraction(
        AcademicProblem(
            course="CT",
            problem_text="请分析图片中的电路",
            figures_given=[{"file_id": "image-1"}],
        ),
        (
            '{"diagram_description":"电压源连接V1和GND",'
            '"components":[{"component_type":"voltage source","label":"V1",'
            '"connections":["V1","GND"],'
            '"terminal_map":{"positive":"V1","negative":"GND"},'
            '"certainty":"certain"}],'
            '"confidence":0.95}'
        ),
    )

    assert metadata["visual_topology_validated"] is False
    assert "visual_component_missing_polarity_or_reference_direction" in (
        metadata["visual_topology_issues"]
    )


def test_visual_extraction_low_confidence_cannot_continue_to_solver() -> None:
    problem = AcademicProblem(
        course="CT",
        problem_text="请分析图片中的电路",
        figures_given=[{"file_id": "image-1"}],
    )

    merged, metadata = AcademicProblemSolverService._merge_visual_extraction(
        problem,
        (
            '{"diagram_description":"R1连接V1和GND",'
            '"components":[{"component_type":"resistor","label":"R1",'
            '"connections":["V1","GND"],"certainty":"certain"}],'
            '"confidence":0.74}'
        ),
    )

    assert metadata["visual_topology_validated"] is False
    assert "visual_topology_low_confidence" in metadata["visual_topology_issues"]
    assert merged.can_continue is False
    assert SolverBoundaryPolicy().evaluate(merged).reason == (
        "visual_topology_not_structured"
    )


def test_visual_extraction_rejects_disconnected_multi_component_graph() -> None:
    problem = AcademicProblem(
        course="CT",
        problem_text="请分析图片中的电路",
        figures_given=[{"file_id": "image-1"}],
    )

    merged, metadata = AcademicProblemSolverService._merge_visual_extraction(
        problem,
        (
            '{"diagram_description":"两组器件",'
            '"components":['
            '{"component_type":"resistor","label":"R1",'
            '"connections":["V1","N1"],"certainty":"certain"},'
            '{"component_type":"resistor","label":"R2",'
            '"connections":["V2","N2"],"certainty":"certain"}],'
            '"confidence":0.95}'
        ),
    )

    assert metadata["visual_topology_validated"] is False
    assert "visual_topology_disconnected_components" in (
        metadata["visual_topology_issues"]
    )
    assert merged.can_continue is False


def test_visual_extraction_rejects_unknown_connection_labels() -> None:
    extraction = (
        '{"diagram_description":"R1连接未知节点",'
        '"components":[{"component_type":"resistor","label":"R1",'
        '"connections":["unknown","GND"],"certainty":"certain"}],'
        '"confidence":0.95}'
    )

    _, metadata = AcademicProblemSolverService._merge_visual_extraction(
        AcademicProblem(
            course="CT",
            problem_text="请分析图片中的电路",
            figures_given=[{"file_id": "image-1"}],
        ),
        extraction,
    )

    assert metadata["visual_topology_validated"] is False
    assert "visual_component_has_uncertain_connection" in (
        metadata["visual_topology_issues"]
    )


def test_academic_reasoning_routes_by_problem_complexity() -> None:
    registry = ModelRegistry(Settings(app_env="test", _env_file=None))
    complex_route = registry.get_route("academic_problem_solving")
    standard_route = registry.get_route("academic_problem_solving_simple")

    assert complex_route.primary == "qwen_vision_primary"
    assert complex_route.fallback == "qwen_vision_fast"
    assert standard_route.primary == "qwen_vision_fast"
    assert standard_route.fallback == "qwen_vision_primary"


def test_langgraph_populates_real_preparation_state() -> None:
    state = new_graph_state(request_id="audit-graph-001", message="KCL")
    result = graph().run(
        AcademicProblem(
            course="CT",
            problem_text="使用 KCL 列写节点方程",
            extraction_confidence=0.9,
        ),
        state=state,
        retrieved_chunks=[{"evidence_id": "kb-1", "title": "KCL"}],
    )

    assert result.course == "CT"
    assert state["selected_course_pack"] == "CT"
    assert state["problem_type"] == "kcl_kvl"
    assert state["selected_capabilities"]
    assert state["selected_tools"]
    assert state["execution_path"] == "FAST"
    assert state["citations"] == [{"evidence_id": "kb-1", "title": "KCL"}]


def test_langgraph_checkpoint_can_interrupt_and_resume() -> None:
    checkpointed = AcademicProblemSolverGraph(
        default_course_registry(),
        default_capability_registry(),
        default_tool_registry(),
        checkpointer=InMemorySaver(),
    )
    state = new_graph_state(request_id="audit-checkpoint-001", message="KCL")
    problem = AcademicProblem(
        course="CT",
        problem_text="浣跨敤 KCL 鍒楀啓鑺傜偣鏂圭▼",
        extraction_confidence=0.9,
    )

    interrupted = checkpointed.invoke_state(
        problem,
        state=state,
        thread_id="audit-thread-001",
        interrupt_before=["format_course_answer"],
    )

    assert not interrupted.get("structured_result")
    checkpoint = checkpointed.checkpoint_state(thread_id="audit-thread-001")
    assert checkpoint["next"] == ["format_course_answer"]
    assert checkpoint["values"]["current_stage"] == "generate_learning_feedback"

    resumed = checkpointed.resume_state(thread_id="audit-thread-001")

    assert "structured_result" in resumed
    assert resumed["current_stage"] == "finalize_solver_response"
    assert resumed["structured_result"]["course"] == "CT"

    same_session_other_task = new_graph_state(
        request_id="audit-checkpoint-002", session_id="same-session", message="KCL"
    )
    assert state["thread_id"] != same_session_other_task["thread_id"]


@pytest.mark.asyncio
async def test_langgraph_async_run_returns_solution() -> None:
    state = new_graph_state(request_id="audit-async-001", message="KCL")
    result = await graph().arun(
        AcademicProblem(
            course="CT",
            problem_text="浣跨敤 KCL 鍒楀啓鑺傜偣鏂圭▼",
            extraction_confidence=0.9,
        ),
        state=state,
        thread_id=state["thread_id"],
    )

    assert result.course == "CT"
    assert state["current_stage"] == "finalize_solver_response"


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
    assert result.structured_result["model_execution"]["status"] == "skipped"
    assert (
        result.structured_result["boundary_decision"]["reason"]
        == "visual_topology_not_structured"
    )
    assert "base64" not in str(result.structured_result).casefold()
    assert result.metrics.model_calls == 1


@pytest.mark.asyncio
async def test_multi_image_solver_sends_ordered_originals_to_vision_model() -> None:
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
    assert execution["strategy"] == "ordered_multi_image"
    assert execution["source_image_count"] == 2
    assert execution["model_image_count"] == 2
    assert execution["original_order_preserved"] is True
    assert model_service.vision_image_counts == [2]
    # Ordinary multimodal solving continues through the Solver after the
    # general vision pass; the generation call is therefore intentional.
    assert result.metrics.model_calls == 2


@pytest.mark.asyncio
async def test_complex_multi_image_solver_uses_one_cross_image_vision_call() -> None:
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
    assert execution["strategy"] == "ordered_multi_image"
    assert execution["source_image_count"] == 3
    assert execution["model_image_count"] == 3
    assert execution["original_order_preserved"] is True
    assert model_service.vision_image_counts == [3]
    assert model_service.text_task_types == ["academic_problem_solving"]
    assert result.metrics.model_calls == 2


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


class UnexpectedAcademicModelService(SequencedAcademicModelService):
    def __init__(self) -> None:
        super().__init__([], continuations=0)

    async def generate_for_task(
        self, *_args: object, **kwargs: object
    ) -> ModelResponse:
        self.calls.append(kwargs)
        raise RuntimeError("unexpected model adapter failure")


@pytest.mark.asyncio
async def test_solver_preserves_deterministic_result_on_unexpected_model_error(
) -> None:
    model_service = UnexpectedAcademicModelService()
    service = AcademicProblemSolverService(graph(), model_service)  # type: ignore[arg-type]

    result = await service.run(
        AgentRequest(
            session_id="session",
            user_id="user",
            course_id="CT",
            intent=Intent.SOLVE_PROBLEM,
            canonical_input={"text": "已知电阻为2Ω、电压为10V，求电流。"},
        )
    )

    execution = result.structured_result["model_execution"]
    assert result.answer
    assert execution["status"] == "failed"
    assert execution["error_type"] == "academic_model_unexpected_error"
    assert "已保留确定性结果" in "；".join(result.warnings)


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
    assert result.answer.startswith("$$x=2$$")
    assert "完整内容" not in result.answer
    assert "$$ x_" not in result.answer
    assert execution["output_status"] == "complete"
    assert execution["model_calls"] == 2
    assert execution["continuation_count"] == 1
    assert execution["continuation_mode"] == "replace_consolidated"
    assert execution["finish_reasons"] == ["length", "stop"]
    assert result.metrics.model_calls == 2
    assert all(
        call["extra_options"] == {"max_tokens": 4096, "timeout": 180.0}
        for call in model_service.calls
    )
    assert execution["timeout_seconds_per_call"] == 180.0


@pytest.mark.asyncio
async def test_solver_continuation_reuses_successful_route_fallback() -> None:
    model_service = SequencedAcademicModelService(
        [
            ModelResponse(
                provider="dashscope",
                model="qwen3.7-plus",
                content="第一部分。\n\n$$ y_",
                elapsed_ms=5,
                finish_reason="length",
                raw_metadata={
                    "route_fallback_used": True,
                    "target_model": "qwen_vision_primary",
                },
            ),
            ModelResponse(
                provider="dashscope",
                model="qwen3.7-plus",
                content="$$y=1$$\n\n其余部分完成。",
                elapsed_ms=7,
                finish_reason="stop",
            ),
        ],
        continuations=1,
    )
    service = AcademicProblemSolverService(graph(), model_service)  # type: ignore[arg-type]

    result = await service.run(
        AgentRequest(
            session_id="session",
            user_id="user",
            course_id="SS",
            intent=Intent.SOLVE_PROBLEM,
            canonical_input={"text": "逐项判断多个连续时间系统的性质"},
        )
    )

    assert result.answer.startswith("$$y=1$$")
    assert "第一部分" not in result.answer
    assert model_service.calls[1]["extra_options"] == {
        "max_tokens": 4096,
        "timeout": 180.0,
        "_preferred_route_alias": "qwen_vision_primary",
        "_allow_route_fallback": False,
    }


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
    assert "第一部分已完成" not in result.answer


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
    assert result.answer.startswith("后半部分")
    assert "前半部分" not in result.answer
    assert marker not in result.answer


def test_academic_images_use_quality_first_vision_route() -> None:
    assert (
        AcademicProblemSolverService._visual_task_type("CT")
        == "circuit_image_extraction"
    )
    for course in ("AE", "DE", "SS", "DSP", "COMM"):
        assert (
            AcademicProblemSolverService._visual_task_type(course)
            == "academic_image_extraction"
        )


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
