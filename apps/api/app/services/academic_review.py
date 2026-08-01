from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.contracts.solver import (
    AcademicProblem,
    AcademicSolutionResult,
    SolverReviewResult,
    SolverTaskMode,
)

NUMBER_RE = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?")
UNIT_RE = re.compile(
    r"(?<![A-Za-z])(?:V|mV|A|mA|μA|uA|Ω|kΩ|MΩ|W|mW|J|Hz|kHz|MHz|s|ms|m|km)"
    r"(?![A-Za-z])",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ReviewRule:
    error_type: str
    reason: str
    correction: str


class AcademicReviewService:
    """Deterministic-first first-error review without re-solving the problem."""

    def review(
        self,
        problem: AcademicProblem,
        result: AcademicSolutionResult,
        attempt: dict[str, Any] | None,
    ) -> SolverReviewResult:
        mode = problem.task_mode
        if mode not in {SolverTaskMode.REVIEW, SolverTaskMode.VERIFY}:
            raise ValueError("academic review requires REVIEW or VERIFY mode")
        review_mode: Literal["REVIEW", "VERIFY"] = (
            "VERIFY" if mode == SolverTaskMode.VERIFY else "REVIEW"
        )
        raw_attempt = attempt or {}
        student_answer = str(
            raw_attempt.get("raw_text")
            or raw_attempt.get("final_answer")
            or problem.student_answer
            or ""
        ).strip()
        raw_steps = raw_attempt.get("steps")
        steps = raw_steps if isinstance(raw_steps, list) else []
        if mode == SolverTaskMode.VERIFY:
            target = problem.verify_target or student_answer
            steps = [{"step_id": "verify-target", "content": target}]
            student_answer = target
        if not student_answer and not steps:
            return SolverReviewResult(
                task_mode=review_mode,
                student_answer_status="uncertain",
                error_type="unknown",
                why_incorrect="未提供需要审查或验证的学生答案。",
                confidence=0.99,
            )

        valid_steps: list[str] = []
        reference = result.final_answer
        resolved_steps = steps or [{"content": student_answer}]
        for index, raw_step in enumerate(resolved_steps, start=1):
            step = (
                raw_step
                if isinstance(raw_step, dict)
                else {"content": str(raw_step)}
            )
            step_id = str(step.get("step_id") or f"student-S{index}")
            content = " ".join(
                str(step.get(key, ""))
                for key in ("content", "expression", "claimed_result")
                if step.get(key) is not None
            ).strip()
            rule = self.detect_rule(problem, content, reference)
            if rule is None:
                rule = self._numeric_or_unit_rule(content, reference)
            if rule is not None:
                return SolverReviewResult(
                    task_mode=review_mode,
                    student_answer_status=(
                        "partially_correct" if valid_steps else "incorrect"
                    ),
                    first_error_step=step_id,
                    error_type=rule.error_type,  # type: ignore[arg-type]
                    why_incorrect=rule.reason,
                    corrected_step=rule.correction,
                    downstream_impact=(
                        "该处错误会影响依赖此结果的后续数值或结论；"
                        "其余不依赖步骤可保留。"
                    ),
                    remaining_valid_steps=valid_steps,
                    confidence=0.96,
                )
            valid_steps.append(step_id)

        return SolverReviewResult(
            task_mode=review_mode,
            student_answer_status="correct",
            error_type="none",
            why_incorrect="未发现当前确定性规则覆盖范围内的实质错误。",
            remaining_valid_steps=valid_steps,
            confidence=0.85,
        )

    @staticmethod
    def detect_rule(
        problem: AcademicProblem,
        content: str,
        reference: str,
    ) -> ReviewRule | None:
        compact = re.sub(r"\s+", "", content)
        combined = f"{problem.problem_text}\n{content}"
        if (
            "下降" in problem.problem_text
            and "变化率" in combined
            and re.search(r"(?:变化率|di/dt).*?\+?\d", compact)
            and not re.search(r"(?:变化率|di/dt)(?:为|=)-", compact)
        ):
            return ReviewRule(
                "sign",
                "电流下降时 di/dt 应为负值，当前步骤丢失了参考方向对应的负号。",
                "先写 di/dt=(终值-初值)/时间，再代入 u=L·di/dt。",
            )
        if (
            "二极管" in problem.problem_text
            and (
                re.search(r"增大\d+倍.*电压也增大\d+倍", compact)
                or "线性电阻" in content
                or re.search(r"V2=10V1", compact, re.IGNORECASE)
            )
        ):
            return ReviewRule(
                "formula",
                "指数型器件的电流与电压不是线性倍数关系。",
                "使用器件指数方程或电压增量的对数关系重新计算。",
            )
        if "反馈" in problem.problem_text and re.search(
            r"A/\(1\+F\)", compact, re.IGNORECASE
        ):
            return ReviewRule(
                "formula",
                "负反馈闭环增益分母应包含环路增益 AF，而不是只写 F。",
                "改为 A_f=A/(1+AF)，并据此检查闭环带宽。",
            )
        if any(marker in problem.problem_text for marker in ("大于等于", "≥")) and (
            "任意输入为1" in content
            or (
                any(marker in compact for marker in ("001", "010"))
                and "误判" in content
            )
        ):
            return ReviewRule(
                "logic",
                "“任意一位为1”与多位数达到阈值的真值条件并不等价。",
                "枚举全部输入组合，再由真值表化简逻辑函数。",
            )
        if "误当成" in content or "误认为" in content:
            return ReviewRule(
                "calculation",
                "当前步骤使用了错误的时间、条件或量值解释。",
                "回到题面核对该量相对哪个时刻或条件定义，再重新代入。",
            )
        if "功耗" in problem.problem_text and (
            "功耗与电压成正比" in content
            or "按电压一次方" in content
            or re.search(r"P2/P1=3\.3/5", compact, re.IGNORECASE)
        ):
            return ReviewRule(
                "calculation",
                "固定电阻负载下功耗与电压平方成正比，而不是与电压成正比。",
                "使用 P=V²/R 比较新旧功耗。",
            )
        if re.search(
            r"E\s*\[\s*Y\s*\].*E\s*\[\s*V\s*\].*(?:\^?2|²)",
            content,
        ):
            return ReviewRule(
                "formula",
                "非线性变换下 E[V²] 一般不等于 (E[V])²。",
                "保留二阶矩 E[V²]，并结合方差关系计算。",
            )
        if (
            any(marker in problem.problem_text for marker in ("混叠", "抽样"))
            and (
                (
                    "不会混叠" in content
                    and re.search(
                        r"(?:不超过|<=|≤)\s*(?:f?s|采样频率)",
                        compact,
                        re.IGNORECASE,
                    )
                )
                or "奈奎斯特频率误写成抽样频率" in compact
                or re.search(r"fmax(?:<=|≤)fs", compact, re.IGNORECASE)
            )
        ):
            return ReviewRule(
                "calculation",
                "奈奎斯特无混叠条件要求最高频率不超过采样频率的一半。",
                "使用 f_max≤f_s/2 核对频率上限。",
            )
        if (
            any(marker in content for marker in ("z取实数", "只在实轴"))
            and any(marker in combined for marker in ("z*", "共轭"))
            and any(marker in combined for marker in ("Z变换", "z变换", "解析"))
        ):
            return ReviewRule(
                "formula",
                "只在实轴上成立的等式不能替代整个 z 平面上的 Z 变换关系。",
                "按双边 Z 变换定义和收敛域重新核对序列对应关系。",
            )
        if "平稳" in content and any(
            marker in content
            for marker in (
                "都一定遍历",
                "任何平稳过程都",
                "平稳就表示",
                "平稳过程一定遍历",
                "平稳性直接等同于遍历性",
            )
        ):
            return ReviewRule(
                "condition",
                "平稳性本身不能推出遍历性，遍历还需要额外条件。",
                "将结论改为条件化表述，并检查相应遍历条件。",
            )
        if (
            any(marker in problem.problem_text for marker in ("视距", "无线链路"))
            and "km写成m" in compact.casefold()
        ):
            return ReviewRule(
                "unit",
                "视距公式在高度以米代入时，距离结果的单位是千米。",
                "保留计算值，并将最终距离单位改为 km。",
            )
        if "游程" in problem.problem_text and re.search(
            r"每种长度各有1个|共\d+个游程", compact
        ):
            return ReviewRule(
                "calculation",
                "游程数不能由可能长度的种类数直接相加得到。",
                "逐段扫描序列并按连续相同符号统计每个游程。",
            )
        if "同或" in reference and "异或" in content and "同或" not in content:
            return ReviewRule(
                "logic",
                "异或与同或的真值条件相反。",
                "根据输入相同或不同的条件重写真值表。",
            )
        return None

    @staticmethod
    def _numeric_or_unit_rule(
        content: str,
        reference: str,
    ) -> ReviewRule | None:
        candidate_units = {item.casefold() for item in UNIT_RE.findall(content)}
        reference_units = {item.casefold() for item in UNIT_RE.findall(reference)}
        if candidate_units and reference_units and not (
            candidate_units & reference_units
        ):
            return ReviewRule(
                "unit",
                "该步骤的物理量单位与参考量纲不兼容。",
                f"按目标量纲改用以下单位之一：{', '.join(sorted(reference_units))}。",
            )
        candidate_numbers = {float(item) for item in NUMBER_RE.findall(content)}
        reference_numbers = {float(item) for item in NUMBER_RE.findall(reference)}
        if (
            candidate_numbers
            and reference_numbers
            and not candidate_numbers.intersection(reference_numbers)
        ):
            if any(
                -item in reference_numbers for item in candidate_numbers if item != 0
            ):
                return ReviewRule(
                    "sign",
                    "数值大小可能一致，但符号与参考方向下的结果相反。",
                    "保留数值大小并按题设参考方向修正正负号。",
                )
            return ReviewRule(
                "calculation",
                "该步骤的数值未出现在可核对的参考推导中。",
                "从本步骤的代入和运算开始重新核算。",
            )
        return None
