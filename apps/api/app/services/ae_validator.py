from __future__ import annotations

import re
from typing import Any

from app.contracts.solver import (
    AcademicProblem,
    AcademicSolutionResult,
    ProfessionalConflict,
    ProfessionalValidationResult,
)

POSITIVE_GAIN_RE = re.compile(
    r"(?:A[_\s]*v|电压增益)\s*(?:=|为)\s*\+?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


class AEValidator:
    """Finite AE checks. It reports conflicts and never regenerates an answer."""

    validator_id = "ae_deterministic_v1"

    def validate(
        self,
        problem: AcademicProblem,
        result: AcademicSolutionResult,
    ) -> ProfessionalValidationResult:
        if problem.course != "AE":
            return ProfessionalValidationResult(validator=self.validator_id)
        text = f"{problem.problem_text}\n{result.final_answer}"
        mode = self.analysis_mode(problem)
        conflicts: list[ProfessionalConflict] = []

        if mode == "dc_bias" and any(
            marker in result.final_answer for marker in ("交流等效", "中频增益", "rπ")
        ):
            conflicts.append(
                self._conflict(
                    "analysis_mode_mixed",
                    "静态工作点分析中混入了交流小信号等效关系。",
                    "先用直流等效电路确定工作点，再另行建立小信号模型。",
                )
            )

        vbe = self._condition(problem.known_conditions, "vbe", "v_be")
        if (
            vbe is not None
            and vbe < 0.5
            and any(marker in text.casefold() for marker in ("放大区", "active"))
        ):
            conflicts.append(
                self._conflict(
                    "bjt_operating_region",
                    f"V_BE={vbe:g} V 与硅管按放大区导通的假设不自洽。",
                    "先判定截止、放大或饱和区，再使用对应电流关系。",
                    {"v_be": vbe},
                )
            )

        vgs = self._condition(problem.known_conditions, "vgs", "v_gs")
        vth = self._condition(
            problem.known_conditions, "vth", "v_th", "阈值电压"
        )
        if (
            vgs is not None
            and vth is not None
            and vgs <= vth
            and any(marker in text.casefold() for marker in ("饱和区", "i_d", "id="))
        ):
            conflicts.append(
                self._conflict(
                    "mos_operating_region",
                    f"V_GS={vgs:g} V 不大于 V_TH={vth:g} V，不能使用强反型饱和区公式。",
                    "按截止条件处理，或补充能证明器件导通的偏置条件。",
                    {"v_gs": vgs, "v_th": vth},
                )
            )

        if (
            mode == "op_amp"
            and any(marker in text for marker in ("虚短", "v+=v-", "v+ = v-"))
            and not any(
                marker in text for marker in ("负反馈", "线性区", "未饱和")
            )
        ):
            conflicts.append(
                self._conflict(
                    "op_amp_condition",
                    "使用虚短时未确认理想运放处于线性负反馈区。",
                    "显式核对负反馈、供电与饱和条件后再令 v+=v-。",
                )
            )

        if (
            mode == "bjt_small_signal"
            and any(marker in problem.problem_text for marker in ("共射", "共源"))
            and POSITIVE_GAIN_RE.search(result.final_answer)
            and "同相" not in problem.problem_text
        ):
            conflicts.append(
                self._conflict(
                    "gain_sign",
                    "共射或共源中频电压增益通常应体现反相负号。",
                    "核对输入、输出参考极性，并在增益中保留负号。",
                )
            )

        if mode in {"bjt_small_signal", "mos_small_signal"}:
            if "信号源电压增益" in problem.problem_text and "输入电阻" not in text:
                conflicts.append(
                    self._conflict(
                        "source_gain_definition",
                        "源电压增益需要计入信号源电阻与放大器输入电阻的分压。",
                        "区分 v_o/v_i 与 v_o/v_s，并补上输入端分压。",
                    )
                )

        affected = [
            item.affected_step
            for item in conflicts
            if item.affected_step is not None
        ]
        corrections = [
            item.suggested_correction
            for item in conflicts
            if item.suggested_correction
        ]
        return ProfessionalValidationResult(
            valid=not conflicts,
            validator=self.validator_id,
            analysis_mode=mode,
            conflicts=conflicts,
            affected_steps=list(dict.fromkeys(affected)),
            suggested_corrections=list(dict.fromkeys(corrections)),
            requires_regeneration=False,
        )
    @staticmethod
    def analysis_mode(problem: AcademicProblem) -> str:
        problem_type = (problem.problem_type or "").casefold()
        text = problem.problem_text.casefold()
        if problem_type in {
            "dc_bias",
            "bjt_small_signal",
            "mos_small_signal",
            "op_amp",
            "feedback",
            "frequency_response",
            "power_amplifier",
            "waveform_generation",
            "comparator",
            "regulated_power_supply",
        }:
            return problem_type
        if any(marker in text for marker in ("静态工作点", "偏置", "直流")):
            return "dc_bias"
        if "bjt" in text or "三极管" in text:
            return "bjt_small_signal" if "小信号" in text else "dc_bias"
        if "mos" in text or "场效应" in text:
            return "mos_small_signal" if "小信号" in text else "dc_bias"
        if "运放" in text or "运算放大器" in text:
            return "op_amp"
        if "反馈" in text:
            return "feedback"
        if any(marker in text for marker in ("频率响应", "截止频率", "带宽")):
            return "frequency_response"
        return "unknown"

    @staticmethod
    def _condition(
        conditions: list[dict[str, Any]],
        *names: str,
    ) -> float | None:
        wanted = {item.casefold().replace("_", "") for item in names}
        for item in conditions:
            name = str(item.get("name") or item.get("symbol") or "").casefold()
            if name.replace("_", "") not in wanted:
                continue
            try:
                return float(item["value"])
            except (KeyError, TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _conflict(
        conflict_type: str,
        message: str,
        correction: str,
        evidence: dict[str, Any] | None = None,
    ) -> ProfessionalConflict:
        return ProfessionalConflict(
            conflict_type=conflict_type,
            message=message,
            affected_step="final_answer",
            evidence=evidence or {},
            suggested_correction=correction,
        )
