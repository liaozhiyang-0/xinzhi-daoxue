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
EXPLICIT_GAIN_RE = re.compile(
    r"(?:A[_\s]*v|gain|增益)\s*(?:=|:|：|is|为)?\s*([+-]?)\s*\d+(?:\.\d+)?",
    re.IGNORECASE,
)


FREQUENCY_UNIT_FACTORS = {
    "hz": 1.0,
    "khz": 1_000.0,
    "mhz": 1_000_000.0,
    "ghz": 1_000_000_000.0,
}

UNIT_DIMENSIONS = {
    "v": "voltage",
    "mv": "voltage",
    "kv": "voltage",
    "a": "current",
    "ma": "current",
    "ka": "current",
    "ohm": "resistance",
    "kohm": "resistance",
    "mohm": "resistance",
    "ω": "resistance",
    "kω": "resistance",
    "mω": "resistance",
    "w": "power",
    "mw": "power",
    "kw": "power",
    "f": "capacitance",
    "uf": "capacitance",
    "nf": "capacitance",
    "pf": "capacitance",
    "h": "inductance",
    "mh": "inductance",
    "uh": "inductance",
    "s": "time",
    "ms": "time",
    "us": "time",
    "ns": "time",
    "hz": "frequency",
    "khz": "frequency",
    "mhz": "frequency",
    "ghz": "frequency",
    "v/v": "gain",
    "db": "gain",
    "1": "gain",
}


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

        vce = self._condition(problem.known_conditions, "vce", "v_ce")
        if (
            mode in {"bjt_bias", "dc_bias"}
            and vce is not None
            and vce < 0
            and self._contains_any(text, ("active", "放大区", "有源区"))
        ):
            conflicts.append(
                self._conflict(
                    "q_point_region_mismatch",
                    f"V_CE={vce:g} V 与 BJT 放大区工作点假设不一致。",
                    "重新核对 Q 点的 V_BE、V_CE 以及各端电流方向，再确定工作区域。",
                    {"v_ce": vce},
                )
            )

        if mode == "diode_circuit":
            anode = self._condition(problem.known_conditions, "anode_voltage", "v_a")
            cathode = self._condition(
                problem.known_conditions, "cathode_voltage", "v_k"
            )
            diode_voltage = self._condition(
                problem.known_conditions, "vd", "v_d", "diode_voltage"
            )
            forward_bias = (
                anode is not None and cathode is not None and anode > cathode
            ) or (diode_voltage is not None and diode_voltage <= 0)
            if forward_bias and self._contains_any(
                text, ("conduct", "forward", "on", "导通", "正向")
            ):
                conflicts.append(
                    self._conflict(
                        "diode_operating_region",
                        "二极管端电压与正向导通结论不一致。",
                        "先计算阳极与阴极的电压差，确认正向偏置后再选择导通模型。",
                        {
                            "anode_voltage": anode,
                            "cathode_voltage": cathode,
                            "diode_voltage": diode_voltage,
                        },
                    )
                )

        vgs = self._condition(problem.known_conditions, "vgs", "v_gs")
        vth = self._condition(problem.known_conditions, "vth", "v_th", "阈值电压")
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
            and not any(marker in text for marker in ("负反馈", "线性区", "未饱和"))
        ):
            conflicts.append(
                self._conflict(
                    "op_amp_condition",
                    "使用虚短时未确认理想运放处于线性负反馈区。",
                    "显式核对负反馈、供电与饱和条件后再令 v+=v-。",
                )
            )

        feedback_polarity = self._condition_text(
            problem.known_conditions, "feedback_polarity", "feedback"
        )
        if mode == "feedback" and feedback_polarity:
            expected = feedback_polarity.casefold()
            mentions_positive = self._contains_any(
                text, ("positive feedback", "正反馈")
            )
            mentions_negative = self._contains_any(
                text, ("negative feedback", "负反馈")
            )
            polarity_conflict = (
                expected in {"negative", "负"} and mentions_positive
            ) or (expected in {"positive", "正"} and mentions_negative)
            if polarity_conflict:
                conflicts.append(
                    self._conflict(
                        "feedback_polarity",
                        "答案中的反馈极性与结构化题目条件不一致。",
                        "按输入与反馈信号的相位关系重新判断正反馈或负反馈，再写出闭环关系。",
                        {"expected_feedback_polarity": feedback_polarity},
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

        if mode in {"small_signal_amplifier", "bjt_small_signal", "mos_small_signal"}:
            expected_gain_polarity = self._condition_text(
                problem.known_conditions,
                "gain_polarity",
                "expected_gain_sign",
                "transfer_polarity",
            )
            gain_conflict = self._gain_polarity_conflict(
                expected_gain_polarity,
                result,
            )
            if gain_conflict is not None:
                conflicts.append(gain_conflict)

        if mode == "small_signal_amplifier":
            prerequisite = self._condition_text(
                problem.known_conditions,
                "q_point_status",
                "bias_status",
                "small_signal_prerequisite",
            )
            if prerequisite and not self._is_verified_status(prerequisite):
                if self._contains_any(
                    text,
                    (
                        "small signal",
                        "small-signal",
                        "small_signal",
                        "small-signal model",
                        "gain",
                        "voltage gain",
                    ),
                ):
                    conflicts.append(
                        self._conflict(
                            "small_signal_prerequisite_missing",
                            (
                                "The structured bias or Q-point status does not permit "
                                "a small-signal model."
                            ),
                            (
                                "Verify the DC operating point and device region "
                                "before deriving small-signal parameters."
                            ),
                            {"prerequisite_status": prerequisite},
                        )
                    )

        conflicts.extend(self._unit_conflicts(problem, result))
        conflicts.extend(self._frequency_conflicts(problem, result, mode))

        affected = [
            item.affected_step for item in conflicts if item.affected_step is not None
        ]
        corrections = [
            item.suggested_correction for item in conflicts if item.suggested_correction
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
            "diode_circuit",
            "bjt_bias",
            "mos_bias",
            "small_signal_amplifier",
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
    def _condition_text(conditions: list[dict[str, Any]], *names: str) -> str | None:
        wanted = {item.casefold().replace("_", "") for item in names}
        for item in conditions:
            name = str(item.get("name") or item.get("symbol") or "").casefold()
            if name.replace("_", "") not in wanted:
                continue
            value = item.get("value")
            if value is None:
                return None
            return str(value).strip()
        return None

    @staticmethod
    def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
        normalized = text.casefold()
        return any(marker.casefold() in normalized for marker in markers)

    @staticmethod
    def _is_verified_status(value: str) -> bool:
        normalized = value.strip().casefold().replace("_", "-")
        return normalized in {
            "ok",
            "pass",
            "passed",
            "valid",
            "verified",
            "ready",
            "confirmed",
            "true",
            "yes",
            "通过",
            "有效",
            "已确认",
        }

    @classmethod
    def _gain_polarity_conflict(
        cls,
        expected: str | None,
        result: AcademicSolutionResult,
    ) -> ProfessionalConflict | None:
        if not expected:
            return None
        normalized = expected.strip().casefold().replace("_", "-")
        expected_sign = (
            -1
            if normalized in {"negative", "negative-gain", "负", "反相"}
            else 1
            if normalized in {"positive", "positive-gain", "正", "同相"}
            else 0
        )
        if not expected_sign:
            return None
        answer_text = result.final_answer
        explicit = EXPLICIT_GAIN_RE.search(answer_text)
        observed_sign = 0
        if explicit:
            sign = explicit.group(1)
            observed_sign = -1 if sign == "-" else 1
        elif result.final_answer_detail and result.final_answer_detail.value:
            value = result.final_answer_detail.value.strip()
            if value.startswith("-"):
                observed_sign = -1
            elif value.startswith("+") or re.match(r"\d", value):
                observed_sign = 1
        if not observed_sign or observed_sign == expected_sign:
            return None
        return cls._conflict(
            "gain_sign",
            (
                "The explicit voltage-gain sign conflicts with the structured "
                "topology condition."
            ),
            (
                "Recheck the input/output reference polarity and retain the "
                "correct gain sign."
            ),
            {
                "expected_gain_polarity": expected,
                "observed_gain_sign": "negative" if observed_sign < 0 else "positive",
            },
        )

    @classmethod
    def _unit_conflicts(
        cls,
        problem: AcademicProblem,
        result: AcademicSolutionResult,
    ) -> list[ProfessionalConflict]:
        expected_units = {
            cls._unit_dimension(str(item.get("unit")))
            for item in problem.target_quantities
            if isinstance(item, dict) and item.get("unit")
        }
        expected_units.discard(None)
        answer_detail = result.final_answer_detail
        answer_unit = answer_detail.unit if answer_detail else None
        answer_dimension = cls._unit_dimension(answer_unit)
        if len(expected_units) != 1 or answer_detail is None:
            return []
        expected_dimension = next(iter(expected_units))
        if not answer_unit:
            return [
                cls._conflict(
                    "unit_missing",
                    (
                        "The structured final answer provides a target value "
                        "without a unit."
                    ),
                    (
                        "Add the unit required by the target quantity, such as "
                        "ohm for input/output resistance."
                    ),
                    {"expected_dimension": expected_dimension},
                )
            ]
        if not answer_dimension:
            return [
                cls._conflict(
                    "unit_consistency",
                    "The structured final-answer unit is not recognized.",
                    "Use a recognized unit for the requested target quantity.",
                    {
                        "expected_dimension": expected_dimension,
                        "answer_unit": answer_unit,
                    },
                )
            ]
        if answer_dimension == expected_dimension:
            return []
        return [
            cls._conflict(
                "unit_consistency",
                (
                    "The structured final-answer unit is incompatible with the "
                    "target quantity."
                ),
                (
                    "Use a unit with the same physical dimension as the requested "
                    "target quantity."
                ),
                {
                    "expected_dimension": expected_dimension,
                    "answer_unit": answer_unit,
                    "answer_dimension": answer_dimension,
                },
            )
        ]

    @classmethod
    def _frequency_conflicts(
        cls,
        problem: AcademicProblem,
        result: AcademicSolutionResult,
        mode: str,
    ) -> list[ProfessionalConflict]:
        if mode != "frequency_response":
            return []
        conflicts: list[ProfessionalConflict] = []
        lower = cls._frequency_condition(
            problem.known_conditions,
            "lower_cutoff_frequency",
            "f_l",
            "fl",
        )
        upper = cls._frequency_condition(
            problem.known_conditions,
            "upper_cutoff_frequency",
            "f_h",
            "fh",
        )
        center = cls._frequency_condition(
            problem.known_conditions,
            "frequency",
            "signal_frequency",
            "f",
        )
        for name, quantity in (("lower", lower), ("upper", upper), ("center", center)):
            if quantity is not None and quantity[1] == "invalid":
                conflicts.append(
                    cls._conflict(
                        "frequency_unit",
                        f"The {name} frequency condition has a non-frequency unit.",
                        "Express frequency conditions using Hz, kHz, MHz, or GHz.",
                        {"condition": name, "unit": quantity[2]},
                    )
                )
        if (
            lower is not None
            and upper is not None
            and lower[1] not in {None, "invalid"}
            and upper[1] not in {None, "invalid"}
            and lower[0] >= upper[0]
        ):
            conflicts.append(
                cls._conflict(
                    "frequency_range",
                    (
                        "The lower cutoff frequency must be smaller than the upper "
                        "cutoff frequency."
                    ),
                    (
                        "Recheck f_L and f_H before applying bandwidth or midband "
                        "formulas."
                    ),
                    {"f_l_hz": lower[0], "f_h_hz": upper[0]},
                )
            )
        if (
            lower is not None
            and upper is not None
            and center is not None
            and lower[1] not in {None, "invalid"}
            and upper[1] not in {None, "invalid"}
            and center[1] not in {None, "invalid"}
            and lower[0] < upper[0]
            and not lower[0] <= center[0] <= upper[0]
            and cls._contains_any(
                f"{problem.problem_text}\n{result.final_answer}",
                ("midband", "passband", "中频", "通带"),
            )
        ):
            conflicts.append(
                cls._conflict(
                    "frequency_region",
                    (
                        "The stated signal frequency is outside the declared "
                        "passband but is described as midband."
                    ),
                    (
                        "Compare the signal frequency with f_L and f_H before "
                        "calling it midband or passband."
                    ),
                    {"frequency_hz": center[0], "f_l_hz": lower[0], "f_h_hz": upper[0]},
                )
            )
        return conflicts

    @classmethod
    def _frequency_condition(
        cls,
        conditions: list[dict[str, Any]],
        *names: str,
    ) -> tuple[float, str | None, str | None] | None:
        wanted = {item.casefold().replace("_", "") for item in names}
        for item in conditions:
            name = str(item.get("name") or item.get("symbol") or "").casefold()
            if name.replace("_", "") not in wanted:
                continue
            try:
                value = float(item["value"])
            except (KeyError, TypeError, ValueError):
                return None
            raw_unit = str(item.get("unit") or "").strip() or None
            if raw_unit is None:
                return (value, None, raw_unit)
            normalized = cls._normalize_unit(raw_unit)
            factor = FREQUENCY_UNIT_FACTORS.get(normalized)
            return (
                value * factor if factor else value,
                normalized if factor else "invalid",
                raw_unit,
            )
        return None

    @classmethod
    def _unit_dimension(cls, value: str | None) -> str | None:
        if not value:
            return None
        return UNIT_DIMENSIONS.get(cls._normalize_unit(value))

    @staticmethod
    def _normalize_unit(value: str) -> str:
        return (
            value.strip()
            .casefold()
            .replace("μ", "u")
            .replace("µ", "u")
            .replace("Ω", "ω")
            .replace(" ", "")
        )

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
