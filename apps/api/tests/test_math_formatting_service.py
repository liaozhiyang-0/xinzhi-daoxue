from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from app.contracts import MathBlockType, MathSegmentType
from app.services.math_formatting_service import MathFormattingService

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "math_rendering_cases.json"


@pytest.fixture
def formatter() -> MathFormattingService:
    return MathFormattingService()


def fixture_cases() -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", fixture_cases(), ids=lambda item: str(item["case_id"]))
def test_math_rendering_acceptance_fixture(
    formatter: MathFormattingService, case: dict[str, Any]
) -> None:
    source = case["input"]
    expression = (
        formatter.matrix_to_latex(source)
        if isinstance(source, list)
        else formatter.normalize_latex(str(source))
    )

    assert expression.latex == case["expected_latex"]
    assert expression.validation_status != "invalid"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("dv/dt", r"\frac{dv}{dt}"),
        ("d2v/dt2", r"\frac{d^2v}{dt^2}"),
        ("dvdt", r"\frac{dv}{dt}"),
        ("d2vdt2", r"\frac{d^2v}{dt^2}"),
        ("delf/delx", r"\frac{\partial f}{\partial x}"),
        ("partial f / partial x", r"\frac{\partial f}{\partial x}"),
        ("sqrt(3)", r"\sqrt{3}"),
        ("√3t", r"\sqrt{3}t"),
        ("iL", "i_L"),
        ("vC", "v_C"),
        ("omega0", r"\omega_0"),
        ("phasor V", r"\underline{V}"),
    ],
)
def test_exact_repairs(
    formatter: MathFormattingService, source: str, expected: str
) -> None:
    assert formatter.normalize_latex(source).latex == expected


def test_regression_for_damaged_differential_equation(
    formatter: MathFormattingService,
) -> None:
    expression = formatter.normalize_latex("d2vdt2 + 2dvdt + 4v = -12e-t")

    assert expression.latex == (r"\frac{d^2v}{dt^2} + 2\frac{dv}{dt} + 4v = -12e^{-t}")


def test_existing_latex_and_legacy_delimiters_are_not_double_wrapped(
    formatter: MathFormattingService,
) -> None:
    content = formatter.process_markdown(
        r"已有 \(x^2\)，以及 $$\begin{aligned}x&=1\\y&=2\end{aligned}$$"
    )

    assert "$x^2$" in content.markdown
    assert content.markdown.count("$$") == 2
    assert "\\(" not in content.markdown
    assert any(
        item.block_type is MathBlockType.ALIGNED for item in content.math_expressions
    )


def test_code_url_date_json_and_table_are_protected(
    formatter: MathFormattingService,
) -> None:
    source = """日期 2026/07/21，访问 https://example.com/a/b。
`dvdt` 不转换。
```python
dvdt = 1
```
| 字段 | 值 |
| --- | --- |
| code | d2vdt2 |
{"formula": "dvdt"}
"""

    content = formatter.process_markdown(source)

    assert "2026/07/21" in content.markdown
    assert "https://example.com/a/b" in content.markdown
    assert "`dvdt`" in content.markdown
    assert "dvdt = 1" in content.markdown
    assert "| code | d2vdt2 |" in content.markdown
    assert '{"formula": "dvdt"}' in content.markdown
    assert all(item.source_text != "dvdt = 1" for item in content.math_expressions)
    assert MathSegmentType.CODE in {item.segment_type for item in content.segments}
    assert MathSegmentType.TABLE in {item.segment_type for item in content.segments}


def test_currency_and_escaped_dollars_are_not_math(
    formatter: MathFormattingService,
) -> None:
    source = r"金额 $100$，折后 $88.50$；转义符号 \$ 不启动公式。"

    content = formatter.process_markdown(source)

    assert content.markdown == source
    assert content.math_expressions == []


def test_structured_fields_are_processed_before_answer_text(
    formatter: MathFormattingService,
) -> None:
    content = formatter.build_from_structured_result(
        {
            "answer_text": "正文中的现有公式为 $x^2$。",
            "key_equations": ["d2vdt2+2dvdt+4v=-12e-t"],
            "intermediate_results": [{"matrix": [["-2", "-4"], ["1", "0"]]}],
            "solution_steps": [{"equations": [r"\sum_{k=0}^{n}a_k"]}],
        }
    )

    latex = {item.latex for item in content.math_expressions}
    assert "x^2" in latex
    assert r"\frac{d^2v}{dt^2}+2\frac{dv}{dt}+4v=-12e^{-t}" in latex
    assert any(r"\begin{bmatrix}" in item for item in latex)
    assert r"\sum_{k=0}^{n}a_k" in latex


def test_invalid_latex_is_reported_and_preserved_for_safe_fallback(
    formatter: MathFormattingService,
) -> None:
    dangerous = formatter.normalize_latex(r"\input{student.tex}")
    unbalanced = formatter.normalize_latex(r"\frac{1}{2")
    content = formatter.process_markdown(r"危险公式：$\input{student.tex}$")

    assert dangerous.validation_status == "invalid"
    assert "dangerous_command:input" in dangerous.warnings
    assert unbalanced.validation_status == "invalid"
    assert r"$\input{student.tex}$" in content.markdown
    assert content.warnings


def test_matrix_mismatch_and_debug_summary_do_not_expose_formula_text(
    formatter: MathFormattingService,
) -> None:
    expression = formatter.matrix_to_latex([["1", "2"], ["3"]])
    content = formatter.build_from_structured_result(
        {"answer_text": "$x^2$", "key_equations": [r"\frac{1}{2}"]}
    )
    summary = formatter.debug_summary(content)

    assert "matrix_column_count_mismatch" in expression.warnings
    assert summary["math_expression_count"] == 2
    assert "x^2" not in json.dumps(summary)


def test_state_equation_is_valid_display_latex(
    formatter: MathFormattingService,
) -> None:
    equation = r"""\begin{bmatrix}
\dot v\\
\dot i_L
\end{bmatrix}
=
\begin{bmatrix}
-2 & -4\\
1 & 0
\end{bmatrix}
\begin{bmatrix}
v\\
i_L
\end{bmatrix}
+
\begin{bmatrix}
12\\
0
\end{bmatrix}e^{-t}"""

    expression = formatter.normalize_latex(equation)

    assert expression.block_type is MathBlockType.MATRIX
    assert expression.validation_status == "valid"


def test_completed_task_transports_math_content_without_breaking_answer_text(
    api: Any, client: Any
) -> None:
    session = api.create_session()
    created = api.create_task(session["id"])
    completed = api.wait_for_task(created["id"])
    result = completed["result_content"]

    assert isinstance(result["answer"], str)
    assert result["math_content"]["markdown"] == result["answer"]
    assert result["structured_result"]["answer_text"] == result["answer"]
    assert result["structured_result"]["math_content"] == result["math_content"]

    orchestration = client.get(f"/api/v1/chat/{created['id']}")
    assert orchestration.status_code == 200
    payload = orchestration.json()
    assert payload["answer_text"] == result["answer"]
    assert payload["math_content"] == result["math_content"]
