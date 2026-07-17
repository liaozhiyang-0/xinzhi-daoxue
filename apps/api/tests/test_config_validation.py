from app.core.config import Settings

from scripts.validate_config import validate


def test_missing_xingchen_fields_are_not_required() -> None:
    result = validate(
        Settings(
            app_env="test",
            default_agent_provider="mock",
            xingchen_base_url="",
            xingchen_api_key="",
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
    assert set(knowledge["sources"]) == {"CT", "AE", "DE"}
