from pathlib import Path

from app.agents import AgentRegistry
from app.core.config import Settings
from app.services.scenario_catalog import ScenarioCatalog
from app.services.scenario_preflight import ScenarioPreflightService

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_scenario_preflight_separates_demo_and_production_readiness() -> None:
    catalog = ScenarioCatalog(PROJECT_ROOT / "config" / "scenarios.yaml")
    scenario = catalog.get("faculty_course_copilot_v1")

    result = ScenarioPreflightService().check(
        scenario,
        registry=AgentRegistry(),
        settings=Settings(app_env="test"),
        mock_available=True,
    )

    assert result.demo_ready is True
    assert result.commercialization_complete is True
    assert result.evidence_review_required is True
    assert result.input_modes == ["text"]
    assert "demo_uses_mock_or_local_fallback" in result.warnings or (
        result.runtime_available is True
    )
