from app.agents.solver_ct import CircuitProblem, LocalCircuitSolverGraph


def test_local_solver_uses_fast_path_and_records_tool_result() -> None:
    result = LocalCircuitSolverGraph().run(
        CircuitProblem(
            problem_text="求 x",
            target_quantities=["x"],
            circuit_relations=["2*x=4"],
            structure_status="complete",
            extraction_confidence=0.95,
        )
    )

    assert result.path == "fast"
    assert result.status == "success"
    assert result.tool_results[0]["tool"] == "sympy_solver"


def test_local_solver_does_not_invent_critical_missing_information() -> None:
    result = LocalCircuitSolverGraph().run(
        CircuitProblem(
            problem_text="识图有冲突",
            critical_missing_info=["参考方向"],
            can_continue=False,
        )
    )

    assert result.path == "blocked"
    assert "参考方向" in result.answer_text
    assert "未擅自补充" in result.warnings[0]
