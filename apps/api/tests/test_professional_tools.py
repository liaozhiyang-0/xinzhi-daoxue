import pytest
from app.tools import calculate, check_unit_compatibility, solve_equations


def test_calculator_supports_complex_phasors_without_eval() -> None:
    assert calculate("(3+4*j) * 2") == 6 + 8j
    with pytest.raises(ValueError):
        calculate("__import__('os').getcwd()")


def test_sympy_solver_and_unit_checker() -> None:
    assert solve_equations(["2*x=4"], ["x"]) == [{"x": "2"}]
    assert check_unit_compatibility("V", "mV").compatible is True
    assert check_unit_compatibility("V", "A").compatible is False
