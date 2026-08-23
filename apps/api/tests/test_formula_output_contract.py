from __future__ import annotations

from app.services.formula_output_contract import evaluate_formula_output_contract


def test_formula_contract_accepts_structured_equations_steps_units_and_markers(
) -> None:
    result = evaluate_formula_output_contract(
        structured_result={
            "key_equations": ["A_f=A/(1+AF)", "f_H≈GBW/A_f"],
            "solution_steps": [
                {
                    "step_id": "s1",
                    "content": "先比较闭环带宽附近的相位和幅值。",
                    "equation": "f_H≈GBW/A_f",
                    "unit": "Hz",
                }
            ],
            "final_answer_detail": {"value": "稳定", "unit": "Hz"},
        },
        answer_text="闭环带宽附近会出现相位延迟和幅值失真，频率单位为 Hz。",
        contract={
            "minimum_equations": 2,
            "require_step_expressions": True,
            "required_units": ["Hz"],
            "required_markers": ["闭环带宽", "相位", "幅值"],
            "require_math_rendering": True,
        },
        math_quality={"status": "passed"},
    )

    assert result["status"] == "passed"
    assert result["publishable"] is True
    assert result["missing"] == []


def test_formula_contract_blocks_missing_reasoning_and_units() -> None:
    result = evaluate_formula_output_contract(
        structured_result={"key_equations": ["x=y"]},
        answer_text="只给出一个结论。",
        contract={
            "minimum_equations": 2,
            "require_step_expressions": True,
            "required_units": ["V"],
            "required_markers": ["相位"],
            "require_math_rendering": True,
        },
        math_quality={"status": "blocked"},
    )

    assert result["status"] == "blocked"
    assert result["publishable"] is False
    assert {
        "key_equations",
        "solution_step_expressions",
        "units",
        "marker:相位",
        "math_rendering",
    } <= set(result["missing"])


def test_formula_contract_is_opt_in() -> None:
    result = evaluate_formula_output_contract(
        structured_result={},
        answer_text="普通文本回答。",
        contract=None,
    )

    assert result["status"] == "not_configured"
    assert result["publishable"] is True


def test_formula_contract_validates_ast_and_equation_dimensions() -> None:
    result = evaluate_formula_output_contract(
        structured_result={
            "key_equations": ["f_H≈GBW/A_f"],
            "symbol_units": {"f_H": "Hz", "GBW": "Hz", "A_f": "1"},
        },
        answer_text="闭环带宽约为 GBW/A_f，单位为 Hz。",
        contract={
            "minimum_equations": 1,
            "require_formula_ast": True,
            "require_unit_consistency": True,
            "equation_unit_checks": [
                {"equation_index": 0, "expected_unit": "Hz"}
            ],
        },
    )

    assert result["status"] == "passed"
    assert result["formula_semantics"]["ast_status"] == "passed"
    assert result["formula_semantics"]["unit_status"] == "passed"
    assert result["formula_semantics"]["parseable_count"] == 1


def test_formula_contract_blocks_unparseable_or_dimensionally_inconsistent_formula(
) -> None:
    result = evaluate_formula_output_contract(
        structured_result={
            "key_equations": ["f_H=GBW/(A_f", "f_H=V"],
            "symbol_units": {"f_H": "Hz", "GBW": "Hz", "A_f": "1", "V": "V"},
        },
        answer_text="公式需要复核。",
        contract={
            "minimum_equations": 2,
            "require_formula_ast": True,
            "require_unit_consistency": True,
        },
    )

    assert result["status"] == "blocked"
    assert result["publishable"] is False
    assert {"formula_ast", "formula_units"} <= set(result["missing"])
    assert {
        "formula_not_parseable",
        "equation_unit_mismatch",
    } <= {
        str(issue["code"])
        for issue in result["formula_semantics"]["issues"]
    }
