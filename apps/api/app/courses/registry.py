from __future__ import annotations

from app.courses.base import BaseCoursePack, CourseFallbackConfig


class CourseRegistry:
    """The only runtime registry for academic course packs."""

    def __init__(self) -> None:
        self._packs: dict[str, BaseCoursePack] = {}

    def register(self, pack: BaseCoursePack) -> None:
        key = pack.course_code.upper()
        if not key or key in self._packs:
            raise ValueError(f"课程包名称无效或重复: {key}")
        self._packs[key] = pack

    def get(self, course_code: str) -> BaseCoursePack:
        key = course_code.upper()
        return self._packs.get(key, self._packs["UNKNOWN"])

    def list_packs(self) -> list[BaseCoursePack]:
        return [self._packs[key] for key in sorted(self._packs)]


def _pack(
    code: str,
    name: str,
    problem_types: tuple[str, ...],
    capabilities: tuple[str, ...],
    keywords: dict[str, tuple[str, ...]] | None = None,
    *,
    status: str = "skeleton",
    fallback: CourseFallbackConfig = CourseFallbackConfig(),
) -> BaseCoursePack:
    return BaseCoursePack(
        course_code=code,
        display_name=name,
        supported_problem_types=problem_types,
        supported_capabilities=capabilities,
        topic_keywords=keywords or {},
        implementation_status=status,
        fallback=fallback,
    )


def default_course_registry() -> CourseRegistry:
    registry = CourseRegistry()
    registry.register(
        _pack(
            "CT",
            "电路理论",
            (
                "kcl_kvl",
                "node_voltage",
                "mesh_current",
                "superposition",
                "thevenin_norton",
                "first_order",
                "second_order",
                "sinusoidal_steady_state",
                "power",
                "controlled_source",
                "mutual_inductance",
                "two_port",
                "frequency_response",
            ),
            (
                "algebra",
                "equation_system",
                "complex_numbers",
                "differential_equations",
                "circuit_analysis",
                "unit_validation",
                "plotting",
            ),
            {
                "kcl_kvl": ("KCL", "KVL", "基尔霍夫"),
                "node_voltage": ("节点电压",),
                "mesh_current": ("网孔",),
                "first_order": ("一阶", "RC", "RL", "电容电压不能突变"),
                "sinusoidal_steady_state": ("相量", "正弦稳态"),
                "controlled_source": ("受控源",),
            },
            status="implemented",
            fallback=CourseFallbackConfig("SOLVER_CT_V1", True),
        )
    )
    registry.register(
        _pack(
            "AE",
            "模拟电子技术",
            (
                "diode_circuit",
                "bjt_bias",
                "mos_bias",
                "small_signal_amplifier",
                "feedback",
                "frequency_response",
                "op_amp",
                "waveform_circuit",
            ),
            (
                "algebra",
                "equation_system",
                "circuit_analysis",
                "complex_numbers",
                "unit_validation",
                "plotting",
            ),
            {
                "diode_circuit": ("二极管",),
                "bjt_bias": ("BJT", "三极管", "静态工作点"),
                "mos_bias": ("MOS",),
                "op_amp": ("运放", "运算放大器"),
            },
            status="basic",
        )
    )
    registry.register(
        _pack(
            "DE",
            "数字电子技术",
            (
                "number_encoding",
                "logic_simplification",
                "combinational_logic",
                "sequential_logic",
                "flip_flop",
                "counter",
                "state_machine",
                "verilog_analysis",
            ),
            (
                "boolean_algebra",
                "logic_analysis",
                "state_machine",
                "hdl_analysis",
                "code_analysis",
            ),
            {
                "logic_simplification": ("逻辑函数", "卡诺图", "化简"),
                "combinational_logic": ("组合逻辑",),
                "sequential_logic": ("时序逻辑", "触发器", "计数器"),
                "verilog_analysis": ("Verilog",),
            },
            status="basic",
        )
    )
    registry.register(
        _pack(
            "SS",
            "信号与系统",
            (
                "continuous_signal",
                "discrete_signal",
                "system_properties",
                "convolution",
                "fourier_transform",
                "laplace_transform",
                "z_transform",
                "frequency_domain",
            ),
            (
                "calculus",
                "complex_numbers",
                "signal_transform",
                "equation_system",
                "plotting",
            ),
            {
                "convolution": ("卷积",),
                "system_properties": ("线性时不变", "LTI"),
                "laplace_transform": ("拉普拉斯",),
            },
            status="basic",
        )
    )
    minimal = {
        "DSP": "数字信号处理",
        "COMM": "通信原理",
        "RF": "高频电子线路",
        "EM": "电磁场与电磁波",
        "INFO": "信息论与编码",
        "EMBEDDED": "嵌入式系统",
        "IC": "集成电路相关课程",
    }
    for code, name in minimal.items():
        registry.register(_pack(code, name, (), ()))
    registry.register(_pack("UNKNOWN", "未知课程", (), (), status="fallback"))
    return registry
