from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def solve_equations(
    equations: Sequence[str], symbols: Sequence[str]
) -> list[dict[str, str]]:
    if not equations or not symbols:
        raise ValueError("equations 与 symbols 不能为空")
    try:
        import sympy  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("符号求解需要安装 sympy") from exc
    symbol_map = {name: sympy.Symbol(name) for name in symbols}
    allowed: dict[str, Any] = {
        **symbol_map,
        "I": sympy.I,
        "pi": sympy.pi,
        "exp": sympy.exp,
        "sin": sympy.sin,
        "cos": sympy.cos,
    }
    parsed = []
    for equation in equations:
        left, separator, right = equation.partition("=")
        expression = (
            sympy.sympify(left, locals=allowed) - sympy.sympify(right, locals=allowed)
            if separator
            else sympy.sympify(left, locals=allowed)
        )
        parsed.append(expression)
    solved = sympy.solve(parsed, list(symbol_map.values()), dict=True)
    return [
        {str(key): str(sympy.simplify(value)) for key, value in item.items()}
        for item in solved
    ]
