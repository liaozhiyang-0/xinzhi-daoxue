from pathlib import Path

import pytest
from app.services.agent_scaffold import AgentScaffoldService, AgentScaffoldSpec


def spec() -> AgentScaffoldSpec:
    return AgentScaffoldSpec(
        agent_id="DEMO_01_SAMPLE_V1",
        display_name="脚手架样例",
        output_fields=("summary", "items"),
        mock_profile="demo_sample_v1",
    )


def test_scaffold_dry_run_builds_schema_valid_bundle() -> None:
    files = AgentScaffoldService().build(spec())

    assert "agent_definition.yaml" in files
    assert "contract_cases.json" in files
    assert "test_real_cloud_template.py" in files
    assert "XINGCHEN_DEMO_01_SAMPLE_FLOW_ID=" in files[".env.example"]
    assert "enabled: false" in files["agent_definition.yaml"]
    assert "publication_status: planned" in files["agent_definition.yaml"]


def test_scaffold_writes_and_refuses_overwrite(tmp_path: Path) -> None:
    service = AgentScaffoldService()
    written = service.write(spec(), tmp_path)

    assert len(written) == 8
    assert all(path.is_file() for path in written)
    with pytest.raises(FileExistsError):
        service.write(spec(), tmp_path)
    overwritten = service.write(spec(), tmp_path, force=True)
    assert len(overwritten) == 8
