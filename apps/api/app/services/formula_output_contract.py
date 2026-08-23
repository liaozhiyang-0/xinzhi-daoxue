from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from tokenize import TokenError
from typing import Any

_UNIT_RE = re.compile(
    r"(?<![A-Za-z])(?:p|n|u|μ|m|k|M|G)?(?:Hz|V|A|Ω|ohm|s|F|H|dB)\b",
    re.IGNORECASE,
)
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_UNIT_DIMENSIONS: dict[str, dict[str, int]] = {
    "1": {},
    "dimensionless": {},
    "V": {"kg": 1, "m": 2, "s": -3, "A": -1},
    "A": {"A": 1},
    "Ω": {"kg": 1, "m": 2, "s": -3, "A": -2},
    "ohm": {"kg": 1, "m": 2, "s": -3, "A": -2},
    "F": {"kg": -1, "m": -2, "s": 4, "A": 2},
    "H": {"kg": 1, "m": 2, "s": -2, "A": -2},
    "Hz": {"s": -1},
    "s": {"s": 1},
    "W": {"kg": 1, "m": 2, "s": -3},
    "dB": {},
}
_UNIT_BASES = frozenset(_UNIT_DIMENSIONS)
_UNIT_PREFIXES = ("p", "n", "u", "μ", "m", "k", "M", "G")


def evaluate_formula_output_contract(
    *,
    structured_result: Mapping[str, Any],
    answer_text: str,
    contract: Mapping[str, Any] | None,
    math_quality: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate an explicitly requested formula-output contract.

    This is a structural gate, not a symbolic-equivalence proof.  It prevents
    a workflow from claiming that a formula-based answer is complete when its
    required equations, reasoning steps, units, or rendering state are absent.
    Domain-specific numerical and physical checks remain the responsibility of
    the relevant Agent validator.
    """

    if not isinstance(contract, Mapping) or contract.get("enabled", True) is False:
        return {
            "contract_version": "formula_output_contract.v1",
            "status": "not_configured",
            "publishable": True,
            "checks": [],
            "missing": [],
        }

    equations = _equations(structured_result)
    steps = _mapping_list(structured_result.get("solution_steps"))
    step_expressions = [
        item
        for item in steps
        if any(
            str(item.get(key, "")).strip()
            for key in ("expression", "equation", "formula", "equations", "result")
        )
    ]
    units = _units(structured_result, answer_text)
    searchable_text = "\n".join(
        [
            str(answer_text),
            *equations,
            *(str(item.get("content", "")) for item in steps),
        ]
    )

    checks: list[dict[str, Any]] = []
    missing: list[str] = []

    minimum_equations = _non_negative_int(contract.get("minimum_equations"), 0)
    if minimum_equations:
        passed = len(equations) >= minimum_equations
        checks.append(
            _check(
                "equation_count",
                passed,
                f"关键方程数量 {len(equations)}/{minimum_equations}",
            )
        )
        if not passed:
            missing.append("key_equations")

    if bool(contract.get("require_step_expressions", False)):
        passed = bool(step_expressions)
        checks.append(
            _check(
                "step_expressions",
                passed,
                "推理步骤包含结构化公式"
                if passed
                else "推理步骤缺少 expression/equation/formula/result",
            )
        )
        if not passed:
            missing.append("solution_step_expressions")

    required_units = _string_list(contract.get("required_units"))
    if required_units:
        normalized_units = {item.casefold() for item in units}
        expected_units = {item.casefold() for item in required_units}
        passed = bool(normalized_units & expected_units)
        checks.append(
            _check(
                "unit_presence",
                passed,
                "已发现要求单位"
                if passed
                else f"缺少要求单位：{', '.join(required_units)}",
            )
        )
        if not passed:
            missing.append("units")

    required_markers = _string_list(contract.get("required_markers"))
    missing_markers = [item for item in required_markers if item not in searchable_text]
    if required_markers:
        checks.append(
            _check(
                "semantic_markers",
                not missing_markers,
                "关键语义标记齐全"
                if not missing_markers
                else f"缺少关键语义标记：{', '.join(missing_markers)}",
            )
        )
        missing.extend(f"marker:{item}" for item in missing_markers)

    formula_semantics = _evaluate_formula_semantics(
        equations,
        structured_result=structured_result,
        contract=contract,
    )
    if formula_semantics["status"] == "blocked":
        if formula_semantics["ast_status"] == "blocked":
            missing.append("formula_ast")
        if formula_semantics["unit_status"] == "blocked":
            missing.append("formula_units")

    if bool(contract.get("require_math_rendering", False)):
        render_status = (
            str(math_quality.get("status", "not_available"))
            if isinstance(math_quality, Mapping)
            else "not_available"
        )
        passed = render_status == "passed"
        checks.append(
            _check(
                "math_rendering",
                passed,
                "数学内容已通过渲染质量门"
                if passed
                else f"数学渲染状态为 {render_status}，不能视为已核验公式",
            )
        )
        if not passed:
            missing.append("math_rendering")

    missing = list(dict.fromkeys(missing))
    status = "blocked" if missing else "passed"
    return {
        "contract_version": "formula_output_contract.v1",
        "status": status,
        "publishable": status == "passed",
        "checks": checks,
        "missing": missing,
        "equation_count": len(equations),
        "step_expression_count": len(step_expressions),
        "detected_units": sorted(units),
        "formula_semantics": formula_semantics,
    }


def _evaluate_formula_semantics(
    equations: Sequence[str],
    *,
    structured_result: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    require_ast = bool(contract.get("require_formula_ast", False))
    require_units = bool(contract.get("require_unit_consistency", False))
    expected_units = _mapping_list(contract.get("equation_unit_checks"))
    configured = require_ast or require_units or bool(expected_units)
    if not configured:
        return {
            "status": "not_configured",
            "ast_status": "not_configured",
            "unit_status": "not_configured",
            "parseable_count": 0,
            "issues": [],
        }

    parsed: list[tuple[Any, Any] | None] = []
    issues: list[dict[str, Any]] = []
    for index, equation in enumerate(equations):
        result = _parse_equation(equation)
        if result is None:
            issues.append(
                {
                    "code": "formula_not_parseable",
                    "equation_index": index,
                    "equation": equation,
                }
            )
            continue
        parsed.append(result)

    parseable_count = sum(item is not None for item in parsed)
    ast_status = (
        "passed"
        if bool(equations) and parseable_count == len(equations)
        else "blocked"
    )
    if not require_ast and not expected_units and not require_units:
        ast_status = "not_configured"

    unit_status = "not_configured"
    unit_checks: list[dict[str, Any]] = []
    if require_units or expected_units:
        symbol_units: dict[str, str] = {}
        symbol_units.update(_string_mapping(contract.get("symbol_units")))
        symbol_units.update(_string_mapping(structured_result.get("symbol_units")))
        dimensions = {
            name: _unit_dimension(unit) for name, unit in symbol_units.items()
        }
        unit_issues: list[dict[str, Any]] = []
        for index, pair in enumerate(parsed):
            if pair is None:
                continue
            left, right = pair
            left_dimension = _infer_dimension(left, dimensions, unit_issues, index)
            right_dimension = _infer_dimension(right, dimensions, unit_issues, index)
            if require_units and left_dimension != right_dimension:
                unit_issues.append(
                    {
                        "code": "equation_unit_mismatch",
                        "equation_index": index,
                        "left_dimension": left_dimension,
                        "right_dimension": right_dimension,
                    }
                )
        for check in expected_units:
            index = _equation_index(check.get("equation_index"))
            expected = str(check.get("expected_unit", "")).strip()
            expected_dimension = _unit_dimension(expected)
            inferred = None
            pair = parsed[index] if 0 <= index < len(parsed) else None
            if pair is not None:
                inferred = _infer_dimension(pair[0], dimensions, unit_issues, index)
            passed = expected_dimension is not None and inferred == expected_dimension
            unit_checks.append(
                _check(
                    f"equation_unit_{index}",
                    passed,
                    "公式左侧量纲符合预期"
                    if passed
                    else f"公式 {index} 的量纲不符合预期单位 {expected or '未提供'}",
                )
            )
            if not passed:
                unit_issues.append(
                    {
                        "code": "equation_expected_unit_mismatch",
                        "equation_index": index,
                        "expected_unit": expected,
                        "inferred_dimension": inferred,
                    }
                )
        if require_units and not symbol_units:
            unit_issues.append({"code": "symbol_units_missing"})
        issues.extend(unit_issues)
        unit_status = "passed" if not unit_issues else "blocked"

    blocked = ast_status == "blocked" or unit_status == "blocked"
    return {
        "status": "blocked" if blocked else "passed",
        "ast_status": ast_status,
        "unit_status": unit_status,
        "parseable_count": parseable_count,
        "checks": unit_checks,
        "issues": _deduplicate_issue_dicts(issues),
    }


def _parse_equation(equation: str) -> tuple[Any, Any] | None:
    try:
        import sympy  # type: ignore[import-untyped]
        from sympy.parsing.sympy_parser import (  # type: ignore[import-untyped]
            convert_xor,
            implicit_multiplication_application,
            parse_expr,
            standard_transformations,
        )
    except ImportError:
        return None
    source = _normalize_equation_source(equation)
    left_text, separator, right_text = source.partition("=")
    if not separator or not left_text.strip() or not right_text.strip():
        return None
    names = set(_IDENTIFIER_RE.findall(source))
    locals_map = {name: sympy.Symbol(name) for name in names}
    transformations = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
    )
    try:
        left = parse_expr(
            left_text, local_dict=locals_map, transformations=transformations
        )
        right = parse_expr(
            right_text, local_dict=locals_map, transformations=transformations
        )
    except (SyntaxError, TokenError, TypeError, ValueError, sympy.SympifyError):
        return None
    return left, right


def _normalize_equation_source(equation: str) -> str:
    source = str(equation).strip()
    source = source.replace("\\approx", "=").replace("≈", "=").replace("≃", "=")
    source = source.replace("\\cdot", "*").replace("·", "*")
    source = source.replace("\\times", "*")
    source = re.sub(r"\\(?:mathrm|text)\{([^{}]*)\}", r"\1", source)
    source = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", source)
    source = source.replace("{", "(").replace("}", ")")
    return source.replace("^", "**")


def _infer_dimension(
    expression: Any,
    symbol_units: Mapping[str, dict[str, int] | None],
    issues: list[dict[str, Any]],
    equation_index: int,
) -> dict[str, int] | None:
    if expression.is_Number:
        return {}
    if expression.is_Symbol:
        name = str(expression)
        dimension = symbol_units.get(name)
        if dimension is None:
            issues.append(
                {
                    "code": "symbol_unit_unknown",
                    "equation_index": equation_index,
                    "symbol": name,
                }
            )
        return dimension
    if expression.is_Add:
        dimensions = [
            _infer_dimension(item, symbol_units, issues, equation_index)
            for item in expression.args
        ]
        if any(item is None for item in dimensions):
            return None
        first = dimensions[0]
        if any(item != first for item in dimensions[1:]):
            issues.append(
                {"code": "sum_unit_mismatch", "equation_index": equation_index}
            )
            return None
        return first
    if expression.is_Mul:
        result: dict[str, int] = {}
        for item in expression.args:
            dimension = _infer_dimension(item, symbol_units, issues, equation_index)
            if dimension is None:
                return None
            result = _combine_dimensions(result, dimension, sign=1)
        return result
    if expression.is_Pow:
        base, exponent = expression.args
        dimension = _infer_dimension(base, symbol_units, issues, equation_index)
        if dimension is None or not exponent.is_Number:
            return None
        if not bool(exponent.is_Integer):
            issues.append(
                {
                    "code": "non_integer_dimension_power",
                    "equation_index": equation_index,
                }
            )
            return None
        return _combine_dimensions({}, dimension, sign=int(exponent))
    if expression.is_Function:
        issues.append(
            {
                "code": "function_dimension_unknown",
                "equation_index": equation_index,
                "function": str(expression.func),
            }
        )
    return None


def _unit_dimension(unit: str) -> dict[str, int] | None:
    normalized = str(unit).strip()
    if normalized in _UNIT_BASES:
        return dict(_UNIT_DIMENSIONS[normalized])
    for prefix in _UNIT_PREFIXES:
        if normalized.startswith(prefix) and normalized[len(prefix) :] in _UNIT_BASES:
            return dict(_UNIT_DIMENSIONS[normalized[len(prefix) :]])
    return None


def _combine_dimensions(
    left: Mapping[str, int], right: Mapping[str, int], *, sign: int
) -> dict[str, int]:
    result = dict(left)
    for key, value in right.items():
        result[key] = result.get(key, 0) + sign * value
        if result[key] == 0:
            del result[key]
    return result


def _string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key).strip(): str(item).strip()
        for key, item in value.items()
        if str(key).strip() and str(item).strip()
    }


def _deduplicate_issue_dicts(issues: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for issue in issues:
        key = repr(sorted(issue.items()))
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result


def _equations(structured_result: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    values.extend(_string_list(structured_result.get("key_equations")))
    for item in _mapping_list(structured_result.get("solution_steps")):
        for key in ("equation", "formula", "expression", "result"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
        equations = item.get("equations")
        values.extend(_string_list(equations))
    return list(dict.fromkeys(values))


def _units(structured_result: Mapping[str, Any], answer_text: str) -> set[str]:
    units = set(_string_list(structured_result.get("units")))
    final_detail = structured_result.get("final_answer_detail")
    if isinstance(final_detail, Mapping) and final_detail.get("unit"):
        units.add(str(final_detail["unit"]).strip())
    for item in _mapping_list(structured_result.get("solution_steps")):
        if item.get("unit"):
            units.add(str(item["unit"]).strip())
    units.update(match.group(0) for match in _UNIT_RE.finditer(answer_text))
    return {item for item in units if item}


def _mapping_list(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _non_negative_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            return default
    else:
        return default
    return max(0, parsed)


def _equation_index(value: object) -> int:
    if isinstance(value, bool):
        return -1
    if isinstance(value, int):
        return value if value >= 0 else -1
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            return -1
        return parsed if parsed >= 0 else -1
    return -1


def _check(check_id: str, passed: bool, message: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "message": message,
        "deterministic": True,
    }
