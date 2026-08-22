from __future__ import annotations

from app.capabilities import default_capability_registry
from app.courses import default_course_registry
from app.services.skill_registry import SkillMatch, SkillRegistry


def test_legacy_skill_yaml_populates_phase_c_contract_defaults() -> None:
    registry = SkillRegistry(
        default_course_registry(), default_capability_registry()
    )

    skill = registry.get("CT.KCL")

    assert skill.version == "1.0"
    assert skill.name == skill.title == "基尔霍夫电流定律"
    assert skill.description == skill.title
    assert skill.domain == "CT"
    assert skill.semantic_description.startswith(skill.title)
    assert skill.status == "active"


def test_skill_match_contract_is_explicitly_non_executable() -> None:
    match = SkillMatch(
        skill_id="CT.KCL",
        score=100,
        match_reasons=["capability:circuit_analysis"],
        eligibility="eligible",
        prerequisite_status="satisfied",
        policy_status="approved",
        version="1.0",
    )

    assert match.model_dump()["skill_id"] == "CT.KCL"
    assert "handler_id" not in match.model_dump()
