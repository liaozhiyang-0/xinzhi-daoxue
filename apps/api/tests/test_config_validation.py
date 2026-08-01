import pytest
from app.core.config import Settings
from pydantic import ValidationError

from scripts.validate_config import validate


def test_missing_xingchen_fields_are_not_required() -> None:
    result = validate(
        Settings(
            app_env="test",
            default_agent_provider="mock",
            xingchen_base_url="",
            xingchen_api_key="",
            xingchen_publication_status="published",
            _env_file=None,
        )
    )
    provider = result["provider"]
    assert isinstance(provider, dict)
    assert provider["publication_status"] == "published"
    assert provider["runtime_configuration_required"] is False
    assert provider["xingchen_credentials"] == "not_required"
    knowledge = result["knowledge"]
    assert isinstance(knowledge, dict)
    assert knowledge["enabled"] is True
    assert set(knowledge["sources"]) == {"CT", "AE", "DE", "SS", "DSP", "COMM"}


def test_xingchen_timeout_is_bounded_and_local_context_defaults_on() -> None:
    settings = Settings(app_env="test", _env_file=None)
    assert settings.xingchen_timeout_seconds == 300
    assert settings.xingchen_use_local_kb_context is True

    with pytest.raises(ValidationError):
        Settings(
            app_env="test",
            _env_file=None,
            xingchen_timeout_seconds=601,
        )


def test_academic_solver_complex_deadlines_are_extended_but_bounded() -> None:
    settings = Settings(app_env="test", _env_file=None)

    assert (
        settings.academic_solver_complex_soft_deadline_seconds,
        settings.academic_solver_complex_finalization_deadline_seconds,
        settings.academic_solver_complex_hard_deadline_seconds,
    ) == (200, 225, 235)

    with pytest.raises(
        ValidationError,
        match="complex solver deadlines must satisfy",
    ):
        Settings(
            app_env="test",
            _env_file=None,
            academic_solver_complex_soft_deadline_seconds=230,
            academic_solver_complex_finalization_deadline_seconds=220,
            academic_solver_complex_hard_deadline_seconds=235,
        )
