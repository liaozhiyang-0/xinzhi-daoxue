from __future__ import annotations

from pathlib import Path

import pytest
from app.capabilities import default_capability_registry
from app.courses import default_course_registry
from app.services.skill_registry import SkillRegistry


def registry(root: Path | None = None) -> SkillRegistry:
    kwargs = {"config_root": root} if root is not None else {}
    return SkillRegistry(
        default_course_registry(), default_capability_registry(), **kwargs
    )


def test_ct_ae_de_skill_catalogs_load_and_map_stable_ids() -> None:
    skills = registry()
    assert len(skills.list_for_course("CT")) == 10
    assert len(skills.list_for_course("AE")) == 17
    assert len(skills.list_for_course("DE")) == 10
    assert skills.map_skills(
        course_id="CT", problem_type="node_voltage"
    ).skill_ids == ["CT.NODAL"]
    assert skills.map_skills(
        course_id="AE", problem_type="bjt_bias", terms=["静态工作点"]
    ).skill_ids[0] == "AE.Q_POINT"
    assert skills.map_skills(
        course_id="DE", problem_type="logic_simplification", terms=["卡诺图"]
    ).skill_ids[0] == "DE.KMAP"
    assert len(skills.list_for_course("RESEARCH")) == 4
    assert len(skills.list_for_course("KNOWLEDGE")) == 3


def test_registry_filters_versions_and_prerequisites_without_execution() -> None:
    skills = registry()

    assert skills.validate_identity_version("CT.KCL", "1.0") is True
    assert skills.list(status="active", domain="research")[0].skill_id == (
        "RESEARCH.EVIDENCE_BRIEF"
    )
    assert skills.validate_prerequisites("CT.NODAL", available_skill_ids=[])[0] is False
    assert skills.validate_prerequisites(
        "CT.NODAL", available_skill_ids=["CT.KCL"]
    ) == (True, [])
    assert skills.serialize("CT.KCL")["skill_id"] == "CT.KCL"


def test_unsupported_course_and_unknown_skill_do_not_fabricate_mapping() -> None:
    skills = registry()
    unavailable = skills.map_skills(course_id="SS", problem_type="convolution")
    assert unavailable.status == "unavailable"
    assert unavailable.skill_ids == []
    unknown = skills.map_skills(course_id="CT", problem_type="general")
    assert unknown.status == "partial"
    assert unknown.skill_ids == []


def test_registry_rejects_cyclic_prerequisites(tmp_path: Path) -> None:
    for course in ("AE", "DE"):
        source = Path("config/skills") / f"{course}.yaml"
        (tmp_path / f"{course}.yaml").write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )
    (tmp_path / "CT.yaml").write_text(
        """
version: "1.0"
course_id: "CT"
skills:
  - skill_id: "CT.A"
    title: "A"
    course_id: "CT"
    chapter: "test"
    prerequisites: ["CT.B"]
    problem_types: ["kcl_kvl"]
    capability_ids: []
    common_error_signatures: []
  - skill_id: "CT.B"
    title: "B"
    course_id: "CT"
    chapter: "test"
    prerequisites: ["CT.A"]
    problem_types: ["kcl_kvl"]
    capability_ids: []
    common_error_signatures: []
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="循环"):
        registry(tmp_path)
