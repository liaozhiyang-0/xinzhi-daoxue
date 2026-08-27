from __future__ import annotations

from app.capabilities.base import BaseCapability


class CapabilityRegistry:
    """The only runtime registry for cross-course capabilities."""

    def __init__(self) -> None:
        self._items: dict[str, BaseCapability] = {}

    def register(self, capability: BaseCapability) -> None:
        key = capability.capability_id
        if not key or key in self._items:
            raise ValueError(f"能力名称无效或重复: {key}")
        self._items[key] = capability

    def get(self, capability_id: str) -> BaseCapability:
        try:
            return self._items[capability_id]
        except KeyError as exc:
            raise KeyError(f"未注册能力: {capability_id}") from exc

    def list_capabilities(self) -> list[BaseCapability]:
        return [self._items[key] for key in sorted(self._items)]


def default_capability_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    definitions = {
        "algebra": ("代数", ("calculator", "sympy_solver")),
        "calculus": ("微积分", ("sympy_solver",)),
        "complex_numbers": ("复数计算", ("complex_number_tool",)),
        "equation_system": ("方程组", ("linear_equation_solver",)),
        "differential_equations": ("微分方程", ("sympy_solver",)),
        "signal_transform": ("信号变换", ("signal_transform_tool",)),
        "boolean_algebra": ("布尔代数", ("boolean_simplifier",)),
        "logic_analysis": ("逻辑分析", ("truth_table_generator",)),
        "state_machine": ("状态机分析", ("truth_table_generator",)),
        "circuit_analysis": (
            "电路分析",
            ("sympy_solver", "complex_number_tool", "unit_checker"),
        ),
        "code_analysis": ("代码分析", ("python_executor",)),
        "hdl_analysis": ("HDL静态分析", ("hdl_static_analyzer",)),
        "unit_validation": ("单位校验", ("unit_checker",)),
        "plotting": ("绘图", ("plotting_tool",)),
        "teaching.lesson_design": ("教学设计", ()),
        "teaching.assignment_review": ("作业首错诊断", ()),
        "learning.first_error_diagnosis": ("首错诊断", ()),
        "learning.path_plan": ("学习路径规划", ()),
        "research.evidence_brief": ("科研证据简报", ()),
        "research.academic_writing": ("学术写作", ()),
        "academic_writing": ("学术写作兼容能力", ()),
        "citation_check": ("引用检查兼容能力", ()),
        "knowledge.govern": ("知识资产治理", ()),
        "knowledge.qa": ("课程知识问答", ()),
        "academic.solve": ("学术问题求解", ()),
        "vision.circuit_parse": ("电路图像解析", ()),
        "circuit.visualize": ("电路可视化", ("circuit.render",)),
        # Legacy recognition labels remain registered as aliases during the
        # migration window; Planner canonicalizes the six showcase paths.
        "lesson_design": ("教学设计兼容能力", ()),
        "answer_review": ("作业诊断兼容能力", ()),
        "general_answer": ("通用回答兼容能力", ()),
        "problem_solving": ("问题求解兼容能力", ()),
        "deterministic_verification": ("确定性验证兼容能力", ()),
        "course_knowledge": ("课程知识兼容能力", ()),
    }
    for capability_id, (name, tools) in definitions.items():
        registry.register(BaseCapability(capability_id, name, tools))
    return registry
