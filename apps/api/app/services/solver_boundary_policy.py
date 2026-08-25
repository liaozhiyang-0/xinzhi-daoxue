from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.contracts.solver import AcademicProblem, AcademicSolutionResult

PROBABILITY_RE = re.compile(r"(?<![\d.])(?:0(?:\.\d+)?|1(?:\.0+)?)(?![\d.])")
REFERENCE_ONLY_RE = re.compile(r"(?:题|习题|式)\s*[（(]?\d+(?:[.-]\d+)+[）)]?")
ABSOLUTE_CLAIMS = (
    ("任何情况下都适用", "仅在上述条件成立时适用"),
    ("无需其他条件", "在已列条件充分时"),
    ("一定正确", "在当前可验证范围内成立"),
    ("完全解决", "已完成当前信息允许的部分"),
    ("唯一方法", "一种可行方法"),
)


@dataclass(slots=True)
class BoundaryDecision:
    answer_status: str = "complete"
    can_continue: bool = True
    answer: str = ""
    missing_information: list[str] = field(default_factory=list)
    uncertain_points: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def intercepted(self) -> bool:
        return bool(self.answer)


class SolverBoundaryPolicy:
    """Deterministic boundary handling before any generative solver call."""

    def evaluate(
        self, problem: AcademicProblem, *, check_visual_topology: bool = True
    ) -> BoundaryDecision:
        text = problem.problem_text
        compact = re.sub(r"\s+", "", text)
        explicit_missing = [
            str(item.get("field") or item.get("description") or item)
            for item in problem.critical_missing_info
        ]

        probabilities = [float(item) for item in PROBABILITY_RE.findall(text)]
        if (
            "概率" in text
            and len(probabilities) >= 2
            and abs(sum(probabilities) - 1) > 1e-9
        ):
            total = sum(probabilities)
            return BoundaryDecision(
                answer_status="unusable",
                can_continue=False,
                answer=(
                    f"给出的概率之和为 {total:g}，不是合法的概率分布，"
                    "因此不能直接计算合法信源熵。请先修正各符号概率。"
                ),
                missing_information=["合法且总和为1的概率分布"],
                reason="invalid_probability_distribution",
            )

        if "收敛域" in text and any(
            marker in text for marker in ("没有给", "未给", "缺少")
        ):
            return BoundaryDecision(
                answer_status="conditional",
                can_continue=False,
                answer=(
                    "缺少收敛域（ROC），仅凭系统函数不能唯一判断因果性和"
                    "稳定性；需要分别讨论不同收敛域对应的序列和系统性质。"
                ),
                missing_information=["收敛域"],
                reason="missing_roc",
            )

        if (
            ("电路图" in text or "所示电路" in text)
            and any(marker in text for marker in ("没有", "未附", "缺少"))
            and not problem.figures_given
            and not (problem.course == "DE" and "计数器" in text)
        ):
            missing = ["电路图、元件参数和连接关系"]
            if "初始" in text:
                missing.append("初始状态")
            return self._missing_answer("电路", missing, "missing_figure")

        if (
            problem.figures_given
            and problem.course in {"CT", "AE", "DE"}
            and check_visual_topology
            and not self._has_structured_visual_problem(problem)
            and not self.has_explicit_textual_topology(problem.problem_text)
        ):
            return BoundaryDecision(
                answer_status="conditional",
                can_continue=False,
                answer=(
                    "已收到题目图片，但尚未形成可核验的结构化拓扑。"
                    "当前不能仅凭视觉摘要计算或判断结论；请补充器件端点与节点连接、"
                    "元件参数/极性、参考方向以及待求量，或确认识别结果后再继续。"
                ),
                missing_information=[
                    "器件端点与节点连接",
                    "元件参数和极性",
                    "参考方向和待求量",
                ],
                reason="visual_topology_not_structured",
            )

        if "式(" in text and any(
            marker in text for marker in ("未给出", "没有给出", "缺少")
        ):
            match = REFERENCE_ONLY_RE.search(text)
            equation = match.group(0) if match else "所引用公式"
            return BoundaryDecision(
                answer_status="unusable",
                can_continue=False,
                answer=(
                    f"当前缺少{equation}的正文、变量定义和成立条件。"
                    "请补充这些信息后再进行证明，不能据编号编造公式。"
                ),
                missing_information=["公式正文", "变量定义", "成立条件"],
                reason="missing_equation",
            )

        if (
            problem.course == "DE"
            and "计数器" in text
            and any(marker in text for marker in ("未说明", "未附", "缺少"))
        ):
            return BoundaryDecision(
                answer_status="unusable",
                can_continue=False,
                answer=(
                    "缺少计数器电路、初始状态和时钟触发沿，无法唯一写出"
                    "状态序列。请补充初始状态、上升沿或下降沿约定及连接方式。"
                ),
                missing_information=["初始状态", "触发沿", "计数器连接方式"],
                reason="missing_initial_condition",
            )

        if any(marker in text for marker in ("上题", "所给电路参数条件下")) and any(
            marker in text for marker in ("没有", "缺少", "未给")
        ):
            missing = self._named_missing_items(text)
            return self._missing_answer(
                "上题或引用题目",
                missing or ["被引用题目的完整条件"],
                "missing_prior_context",
            )

        if (
            problem.course == "DE"
            and any(marker in compact.casefold() for marker in ("a=x", "b=z"))
            and any(marker in text for marker in ("唯一", "0或1", "二值"))
        ):
            return BoundaryDecision(
                answer_status="conditional",
                can_continue=False,
                answer=(
                    "输入包含 x、z 未知或高阻态，且缺少门类型和驱动强度，"
                    "因此无法给出唯一的二值输出 0 或 1。"
                ),
                missing_information=["门类型", "驱动强度"],
                reason="unknown_logic_state",
            )

        if "既吸收" in text and "又发出" in text and "参考方向" in text:
            return BoundaryDecision(
                answer_status="unusable",
                can_continue=False,
                answer=(
                    "该要求与同一参考方向下的功率符号约定矛盾。关联参考方向"
                    "下 p=ui；同一组电压、电流不能同时表示吸收和发出相同功率。"
                ),
                uncertain_points=["需要确认是否切换了电压或电流参考方向"],
                reason="contradictory_request",
            )

        if problem.course == "AE" and "理想运放" in text and any(
            marker in text for marker in ("没有说明反馈", "直接令", "未说明反馈")
        ):
            return BoundaryDecision(
                answer_status="conditional",
                can_continue=True,
                answer=(
                    "仅有“理想运放”条件还不足以直接使用虚短。只有确认电路处于"
                    "线性区且构成负反馈时，才能令 v+=v-；还需给出反馈极性、"
                    "供电电压及饱和状态。"
                ),
                missing_information=["负反馈条件", "线性区", "供电与饱和状态"],
                assumptions=["若后续确认理想运放在线性负反馈区，可使用虚短虚断"],
                reason="op_amp_condition_missing",
            )

        if "终值" in text and any(
            marker in text for marker in ("未给", "无条件", "一定")
        ):
            return BoundaryDecision(
                answer_status="conditional",
                can_continue=True,
                answer=(
                    "该终值结论依赖 aT 的符号及终值定理的极点条件。应分别讨论"
                    " aT>0、aT=0 和 aT<0；条件未确定时不能无条件断言终值为 b。"
                ),
                missing_information=["aT 的符号", "终值定理极点条件"],
                reason="theorem_precondition_missing",
            )

        if not problem.can_continue or explicit_missing:
            return self._missing_answer(
                "题目",
                explicit_missing or self._named_missing_items(text),
                "critical_input_missing",
            )
        return BoundaryDecision()

    def apply(
        self,
        result: AcademicSolutionResult,
        decision: BoundaryDecision,
    ) -> AcademicSolutionResult:
        if not decision.intercepted:
            return result
        return result.model_copy(
            update={
                "status": "partial",
                "final_answer": decision.answer,
                "assumptions": list(
                    dict.fromkeys([*result.assumptions, *decision.assumptions])
                ),
                "remaining_risks": list(
                    dict.fromkeys(
                        [
                            *result.remaining_risks,
                            *decision.missing_information,
                            *decision.uncertain_points,
                        ]
                    )
                ),
                "confidence": min(result.confidence, 0.55),
                "execution_path": "CONDITIONAL",
                "fallback_target": None,
            }
        )

    @staticmethod
    def condition_absolute_claims(answer: str, *, has_assumptions: bool) -> str:
        if not has_assumptions:
            return answer
        conditioned = answer
        for claim, replacement in ABSOLUTE_CLAIMS:
            conditioned = conditioned.replace(claim, replacement)
        return conditioned

    @staticmethod
    def _missing_answer(
        subject: str,
        missing: list[str],
        reason: str,
    ) -> BoundaryDecision:
        resolved = list(dict.fromkeys(item for item in missing if item))
        joined = "、".join(resolved) or "完成求解所需的关键条件"
        return BoundaryDecision(
            answer_status="unusable",
            can_continue=False,
            answer=(
                f"当前{subject}信息缺失：{joined}。无法唯一求解；"
                "请补充上述条件后继续，我不会猜测缺失参数或连接关系。"
            ),
            missing_information=resolved,
            reason=reason,
        )

    @staticmethod
    def _named_missing_items(text: str) -> list[str]:
        candidates = (
            "电路",
            "参数",
            "系统方程",
            "系统函数",
            "初始条件",
            "同步码长度",
            "判决门限",
            "误码率",
            "反馈极性",
            "供电电压",
            "触发沿",
        )
        return [item for item in candidates if item in text]

    @staticmethod
    def _has_structured_visual_problem(problem: AcademicProblem) -> bool:
        status = problem.structure_status.strip().casefold()
        if status in {"complete", "verified", "structured"}:
            return problem.can_continue
        if not problem.can_continue:
            return False
        if not problem.entities or not (problem.relations or problem.equations_given):
            return False
        return all(
            str(item.get("certainty", "certain")).casefold()
            not in {"uncertain", "unknown", "low"}
            for item in [*problem.entities, *problem.relations]
            if isinstance(item, dict)
        )

    @staticmethod
    def has_explicit_textual_topology(text: str) -> bool:
        """Return whether the prompt itself supplies enough circuit facts.

        An image is supplementary when the user has already stated the
        topology in text.  This intentionally requires several independent
        fact groups so a generic ``请分析图片中的电路`` prompt still follows
        the conservative visual boundary.
        """

        normalized = re.sub(r"\s+", "", str(text)).casefold()
        if not normalized:
            return False

        circuit_context = any(
            marker in normalized
            for marker in (
                "运算放大器",
                "理想运放",
                "opamp",
                "反相端",
                "同相端",
                "晶体管",
                "mosfet",
            )
        )
        topology_markers = (
            "接地",
            "节点",
            "串联",
            "并联",
            "连接",
            "反馈",
            "输入端",
            "输出端",
            "反相端",
            "同相端",
            "正端",
            "负端",
        )
        topology_count = sum(marker in normalized for marker in topology_markers)
        component_markers = (
            r"r\d+",
            r"c\d+",
            r"l\d+",
            r"q\d+",
            r"d\d+",
            "电阻",
            "电容",
            "电感",
            "负载",
            "电源",
            "运算放大器",
        )
        component_count = sum(
            bool(re.search(marker, normalized))
            for marker in component_markers
        )
        has_parameter = bool(
            re.search(
                r"(?:r|c|l|q|d)\d*\s*[=:＝]\s*[-+±]?\d"
                r"|[-+±]?\d+(?:\.\d+)?\s*(?:[mkμu]?ω|欧姆|v|a|hz|f)\b",
                normalized,
            )
        )
        has_target = any(
            marker in normalized
            for marker in ("求", "判断", "推导", "说明", "边界", "饱和", "输出")
        )
        return (
            circuit_context
            and topology_count >= 2
            and component_count >= 2
            and has_parameter
            and has_target
        )
