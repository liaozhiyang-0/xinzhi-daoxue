from __future__ import annotations

import ast
import cmath
import math
import operator
from collections.abc import Callable
from typing import Any

_BINARY: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_NAMES: dict[str, complex | float] = {"pi": math.pi, "e": math.e, "j": 1j}
_FUNCTIONS: dict[str, Callable[[Any], Any]] = {
    "sqrt": cmath.sqrt,
    "sin": cmath.sin,
    "cos": cmath.cos,
    "exp": cmath.exp,
}


def calculate(expression: str) -> complex | float:
    """Evaluate a bounded arithmetic expression without eval or file access."""

    tree = ast.parse(expression, mode="eval")

    def visit(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(
            node.value, (int, float, complex)
        ):
            return node.value
        if isinstance(node, ast.Name) and node.id in _NAMES:
            return _NAMES[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            return _BINARY[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](visit(node.operand))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCTIONS
            and len(node.args) == 1
            and not node.keywords
        ):
            return _FUNCTIONS[node.func.id](visit(node.args[0]))
        raise ValueError("表达式包含不允许的语法")

    value = visit(tree)
    if isinstance(value, complex) and abs(value.imag) < 1e-12:
        return float(value.real)
    return value
