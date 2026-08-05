from __future__ import annotations

import math
from typing import Any

from app.contracts.solver import (
    AcademicProblem,
    AcademicSolutionResult,
    ProfessionalConflict,
    ProfessionalValidationResult,
)


class CTValidator:
    """Finite CT checks for explicitly structured balance data.

    The validator never parses arbitrary prose or infers circuit topology. A
    conflict is emitted only when an upstream structured representation
    provides all numeric operands needed for the requested check.
    """

    validator_id = "ct_deterministic_v1"
    default_tolerance = 1e-9

    def validate(
        self,
        problem: AcademicProblem,
        result: AcademicSolutionResult,
    ) -> ProfessionalValidationResult:
        if problem.course != "CT":
            return ProfessionalValidationResult(validator=self.validator_id)

        conflicts: list[ProfessionalConflict] = []
        for relation in problem.relations:
            if not isinstance(relation, dict):
                continue
            rule = str(
                relation.get("rule") or relation.get("verification_rule") or ""
            ).strip()
            if rule in {"kcl", "kvl", "kcl_kvl_consistency"}:
                conflict = self._validate_equation_balance(relation)
            elif rule == "power_energy_balance":
                conflict = self._validate_power_balance(relation)
            elif rule == "equivalent_resistance_error":
                conflict = self._validate_scalar_mismatch(
                    relation,
                    candidate_key="candidate_resistance",
                    reference_key="reference_resistance",
                    conflict_type="equivalent_resistance_error",
                    label="等效电阻",
                    correction="重新核对独立源置零和端口条件，再计算端口看到的等效电阻。",
                )
            elif rule == "kcl_sign_error":
                conflict = self._validate_equation_balance(
                    relation, conflict_type="kcl_sign_error"
                )
            elif rule == "phase_sign_error":
                conflict = self._validate_phase_mismatch(relation)
            elif rule == "power_factor_error":
                conflict = self._validate_power_factor(relation)
            else:
                conflict = None
            if conflict is not None:
                conflicts.append(conflict)

        return ProfessionalValidationResult(
            valid=not conflicts,
            validator=self.validator_id,
            analysis_mode=problem.problem_type or "unknown",
            conflicts=conflicts,
            affected_steps=list(
                dict.fromkeys(
                    item.affected_step
                    for item in conflicts
                    if item.affected_step
                )
            ),
            suggested_corrections=list(
                dict.fromkeys(
                    item.suggested_correction
                    for item in conflicts
                    if item.suggested_correction
                )
            ),
            requires_regeneration=False,
        )

    def _validate_equation_balance(
        self,
        relation: dict[str, Any],
        *,
        conflict_type: str = "kcl_kvl_consistency",
    ) -> ProfessionalConflict | None:
        lhs = self._number(relation.get("candidate_lhs"))
        rhs = self._number(relation.get("candidate_rhs"))
        if lhs is None or rhs is None:
            return None
        tolerance = self._tolerance(relation.get("tolerance"))
        residual = lhs - rhs
        if math.isclose(residual, 0.0, abs_tol=tolerance, rel_tol=0.0):
            return None
        law = str(relation.get("law") or "KCL/KVL")
        return self._conflict(
            conflict_type,
            f"显式 {law} 候选方程两侧不相等，残差为 {residual:g}。",
            "重新核对电流/电压参考方向，并将方程两侧按同一约定整理后再求解。",
            {
                "law": law,
                "candidate_lhs": lhs,
                "candidate_rhs": rhs,
                "residual": residual,
                "tolerance": tolerance,
            },
        )

    def _validate_scalar_mismatch(
        self,
        relation: dict[str, Any],
        *,
        candidate_key: str,
        reference_key: str,
        conflict_type: str,
        label: str,
        correction: str,
    ) -> ProfessionalConflict | None:
        candidate = self._number(relation.get(candidate_key))
        reference = self._number(relation.get(reference_key))
        if candidate is None or reference is None:
            return None
        tolerance = self._tolerance(relation.get("tolerance"))
        difference = candidate - reference
        if math.isclose(difference, 0.0, abs_tol=tolerance, rel_tol=0.0):
            return None
        return self._conflict(
            conflict_type,
            f"显式{label}候选值与参考值不一致，差值为 {difference:g}。",
            correction,
            {
                "candidate": candidate,
                "reference": reference,
                "difference": difference,
                "tolerance": tolerance,
            },
        )

    def _validate_phase_mismatch(
        self, relation: dict[str, Any]
    ) -> ProfessionalConflict | None:
        candidate = self._number(relation.get("candidate_phase_degrees"))
        reference = self._number(relation.get("reference_phase_degrees"))
        if candidate is None or reference is None:
            return None
        tolerance = self._tolerance(relation.get("tolerance"))
        difference = (candidate - reference + 180.0) % 360.0 - 180.0
        if math.isclose(difference, 0.0, abs_tol=tolerance, rel_tol=0.0):
            return None
        return self._conflict(
            "phase_sign_error",
            f"显式相位与参考相位不一致，归一化差值为 {difference:g}°。",
            "统一正弦/余弦参考和超前/滞后约定，再检查相位符号。",
            {
                "candidate_phase_degrees": candidate,
                "reference_phase_degrees": reference,
                "difference_degrees": difference,
                "tolerance": tolerance,
            },
        )

    def _validate_power_factor(
        self, relation: dict[str, Any]
    ) -> ProfessionalConflict | None:
        power_factor = self._number(relation.get("power_factor"))
        if power_factor is None:
            return None
        tolerance = self._tolerance(relation.get("tolerance"))
        if abs(power_factor) <= 1.0 + tolerance:
            return None
        return self._conflict(
            "power_factor_error",
            f"显式功率因数为 {power_factor:g}，超出 [-1, 1] 的边界。",
            "重新核对电压电流相角，并区分有功功率与视在功率。",
            {"power_factor": power_factor, "tolerance": tolerance},
        )

    def _validate_power_balance(
        self, relation: dict[str, Any]
    ) -> ProfessionalConflict | None:
        supplied = self._number(relation.get("supplied_power"))
        absorbed = self._number(relation.get("absorbed_power"))
        generated_value = relation.get("generated_power")
        generated = self._number(generated_value)
        if supplied is None or absorbed is None:
            return None
        if generated_value is not None and generated is None:
            return None
        generated = 0.0 if generated is None else generated
        tolerance = self._tolerance(relation.get("tolerance"))
        residual = supplied + generated - absorbed
        if math.isclose(residual, 0.0, abs_tol=tolerance, rel_tol=0.0):
            return None
        return self._conflict(
            "power_energy_balance",
            f"显式功率平衡不成立，供给与吸收残差为 {residual:g} W。",
            "统一功率吸收/发出符号约定，并重新核对各支路功率之和。",
            {
                "supplied_power": supplied,
                "generated_power": generated,
                "absorbed_power": absorbed,
                "residual": residual,
                "tolerance": tolerance,
            },
        )

    @classmethod
    def _tolerance(cls, value: Any) -> float:
        number = cls._number(value)
        return max(number, 0.0) if number is not None else cls.default_tolerance

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        return number if math.isfinite(number) else None

    @staticmethod
    def _conflict(
        conflict_type: str,
        message: str,
        correction: str,
        evidence: dict[str, Any],
    ) -> ProfessionalConflict:
        return ProfessionalConflict(
            conflict_type=conflict_type,
            message=message,
            affected_step="structured_relation",
            evidence=evidence,
            suggested_correction=correction,
        )
