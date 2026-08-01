from __future__ import annotations

import ast
import itertools
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.solver import (
    AcademicProblem,
    AcademicSolutionResult,
    ProfessionalConflict,
    ProfessionalValidationResult,
)

POSTFIX_NOT_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)'")


class BooleanEquivalenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equivalent: bool
    variables: list[str]
    checked_rows: int = Field(ge=0)
    counterexample: dict[str, int] | None = None


class StateTransitionRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cycle: int = Field(ge=1)
    current_state: str
    input_value: str
    edge: str
    next_state: str
    output: str | None = None


class DEValidator:
    """Deterministic DE expression and state-transition checks."""

    validator_id = "de_deterministic_v1"

    def truth_table_equivalent(
        self,
        left: str,
        right: str,
        variables: list[str] | None = None,
    ) -> BooleanEquivalenceResult:
        left_tree = self._parse(left)
        right_tree = self._parse(right)
        resolved = sorted(
            set(variables or [])
            or (self._names(left_tree) | self._names(right_tree))
        )
        if not resolved or len(resolved) > 8:
            raise ValueError("truth-table validation supports 1 to 8 variables")
        rows = 0
        for values in itertools.product((False, True), repeat=len(resolved)):
            env = dict(zip(resolved, values, strict=True))
            rows += 1
            if self._eval(left_tree.body, env) != self._eval(right_tree.body, env):
                return BooleanEquivalenceResult(
                    equivalent=False,
                    variables=resolved,
                    checked_rows=rows,
                    counterexample={
                        key: int(value) for key, value in env.items()
                    },
                )
        return BooleanEquivalenceResult(
            equivalent=True,
            variables=resolved,
            checked_rows=rows,
        )

    def simulate_state_transitions(
        self,
        *,
        initial_state: str,
        inputs: list[str | int],
        transition_table: dict[str, str | dict[str, Any]],
        edge: str = "rising",
    ) -> list[StateTransitionRow]:
        if edge not in {"rising", "falling"}:
            raise ValueError("edge must be rising or falling")
        current = str(initial_state)
        rows: list[StateTransitionRow] = []
        for cycle, raw_input in enumerate(inputs, start=1):
            input_value = str(raw_input)
            key = f"{current}|{input_value}"
            if key not in transition_table:
                raise ValueError(f"missing transition: {key}")
            raw_next = transition_table[key]
            if isinstance(raw_next, dict):
                next_state = str(raw_next.get("next_state", ""))
                output = (
                    str(raw_next["output"]) if "output" in raw_next else None
                )
            else:
                next_state = str(raw_next)
                output = None
            if not next_state:
                raise ValueError(f"empty next state: {key}")
            rows.append(
                StateTransitionRow(
                    cycle=cycle,
                    current_state=current,
                    input_value=input_value,
                    edge=edge,
                    next_state=next_state,
                    output=output,
                )
            )
            current = next_state
        return rows

    def validate(
        self,
        problem: AcademicProblem,
        result: AcademicSolutionResult,
    ) -> ProfessionalValidationResult:
        if problem.course != "DE":
            return ProfessionalValidationResult(validator=self.validator_id)
        conflicts: list[ProfessionalConflict] = []
        for relation in problem.relations:
            reference = relation.get("reference_expression")
            candidate = relation.get("candidate_expression")
            if not isinstance(reference, str) or not isinstance(candidate, str):
                continue
            try:
                check = self.truth_table_equivalent(candidate, reference)
            except ValueError as exc:
                conflicts.append(
                    self._conflict(
                        "logic_expression_unverifiable",
                        str(exc),
                        "将逻辑式整理为不超过8个变量的布尔表达式后再验证。",
                    )
                )
                continue
            if not check.equivalent:
                conflicts.append(
                    self._conflict(
                        "logic_inequivalence",
                        "候选逻辑式与参考逻辑式不等价。",
                        "使用反例输入重新检查真值表或卡诺图化简。",
                        {
                            "counterexample": check.counterexample,
                            "checked_rows": check.checked_rows,
                        },
                    )
                )

        if "算术右移" in problem.problem_text and "补0" in result.final_answer:
            conflicts.append(
                self._conflict(
                    "arithmetic_shift",
                    "有符号数算术右移应扩展符号位，不能统一补0。",
                    "按给定位宽保留最高符号位并检查截断和溢出。",
                )
            )
        if (
            any(
                marker in problem.problem_text
                for marker in ("触发器", "状态机", "计数器")
            )
            and "连续更新" in result.final_answer
        ):
            conflicts.append(
                self._conflict(
                    "clock_edge",
                    "时序状态只能在指定有效触发沿更新。",
                    "逐个有效边沿列出当前状态、输入、下一状态和输出。",
                )
            )

        return ProfessionalValidationResult(
            valid=not conflicts,
            validator=self.validator_id,
            analysis_mode=self._analysis_mode(problem),
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

    @staticmethod
    def _analysis_mode(problem: AcademicProblem) -> str:
        value = (problem.problem_type or "").casefold()
        if value in {
            "logic_simplification",
            "combinational_logic",
            "sequential_logic",
            "flip_flop",
            "counter",
            "state_machine",
            "number_encoding",
        }:
            return value
        text = problem.problem_text
        if any(marker in text for marker in ("状态机", "状态转移")):
            return "state_machine"
        if any(marker in text for marker in ("触发器", "计数器", "寄存器")):
            return "sequential_logic"
        if any(marker in text for marker in ("真值表", "卡诺图", "逻辑函数")):
            return "combinational_logic"
        return "unknown"

    @staticmethod
    def _translate(expression: str) -> str:
        value = expression.strip()
        while POSTFIX_NOT_RE.search(value):
            value = POSTFIX_NOT_RE.sub(r"(not \1)", value)
        value = value.replace("¬", " not ").replace("!", " not ")
        value = value.replace("·", " and ").replace("*", " and ")
        value = value.replace("+", " or ")
        return value

    @classmethod
    def _parse(cls, expression: str) -> ast.Expression:
        try:
            tree = ast.parse(cls._translate(expression), mode="eval")
        except SyntaxError as exc:
            raise ValueError("invalid boolean expression") from exc
        for node in ast.walk(tree):
            if not isinstance(
                node,
                (
                    ast.Expression,
                    ast.BoolOp,
                    ast.UnaryOp,
                    ast.BinOp,
                    ast.Name,
                    ast.Constant,
                    ast.Load,
                    ast.And,
                    ast.Or,
                    ast.Not,
                    ast.BitAnd,
                    ast.BitOr,
                    ast.BitXor,
                    ast.Invert,
                ),
            ):
                raise ValueError(f"unsupported boolean syntax: {type(node).__name__}")
        return tree

    @staticmethod
    def _names(tree: ast.AST) -> set[str]:
        return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

    @classmethod
    def _eval(cls, node: ast.AST, env: dict[str, bool]) -> bool:
        if isinstance(node, ast.Name):
            return env[node.id]
        if isinstance(node, ast.Constant) and node.value in {0, 1}:
            return bool(node.value)
        if isinstance(node, ast.BoolOp):
            values = [cls._eval(item, env) for item in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(
            node.op, (ast.Not, ast.Invert)
        ):
            return not cls._eval(node.operand, env)
        if isinstance(node, ast.BinOp):
            left = cls._eval(node.left, env)
            right = cls._eval(node.right, env)
            if isinstance(node.op, ast.BitAnd):
                return left and right
            if isinstance(node.op, ast.BitOr):
                return left or right
            if isinstance(node.op, ast.BitXor):
                return left != right
        raise ValueError(f"unsupported boolean node: {type(node).__name__}")

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
