from app.services.course_pack import load_course_pack


def test_course_pack_loads() -> None:
    course_pack = load_course_pack()

    assert course_pack.course_id == "CT"
    assert course_pack.agents["solver_agent"] == "SOLVER_CT_V1"
    assert course_pack.tools["code_execution"] is False
