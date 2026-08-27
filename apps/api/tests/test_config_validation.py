import pytest
from app.core.config import Settings
from pydantic import ValidationError

from scripts.validate_config import validate


def test_local_runtime_configuration_is_sufficient() -> None:
    result = validate(
        Settings(
            app_env="test",
            default_agent_provider="mock",
            _env_file=None,
        )
    )
    provider = result["provider"]
    assert isinstance(provider, dict)
    assert provider["publication_status"] == "local_only"
    assert provider["runtime_configuration_required"] is False
    assert provider["runtime_available"] is True
    knowledge = result["knowledge"]
    assert isinstance(knowledge, dict)
    assert knowledge["enabled"] is True
    assert set(knowledge["sources"]) == {"CT", "AE", "DE", "SS", "DSP", "COMM"}
    teaching = result["teaching_foundation"]
    assert isinstance(teaching, dict)
    assert teaching["error_pool_coverage"]["AE"]["covered_error_signature_count"] == 3
    assert "bjt_region_error" in teaching["error_pool_coverage"]["AE"][
        "uncovered_error_signatures"
    ]
    assert teaching["course_packs"]["CT"]["implementation_status"] == "implemented"


def test_frozen_data_analysis_is_not_reported_as_runtime_available() -> None:
    result = validate(
        Settings(
            app_env="test",
            default_agent_provider="mock",
            data_analysis_enabled=False,
            _env_file=None,
        )
    )

    agents = result["agents"]
    assert isinstance(agents, list)
    research_agent = next(
        agent
        for agent in agents
        if agent["agent_id"] == "RESEARCH_03_DATA_ANALYSIS_V1"
    )
    assert research_agent["runtime_available"] is False
    assert research_agent["frozen"] is True
    assert research_agent["unavailable_reason"] == "data_analysis_frozen"


def test_runtime_timeout_is_bounded_and_local_context_defaults_on() -> None:
    settings = Settings(app_env="test", _env_file=None)
    assert settings.workflow_default_timeout_seconds == 120
    assert settings.knowledge_enabled is True
    assert settings.agent_runtime_semantic_evidence == ""
    assert settings.legacy_hash_embedding_enabled is False
    assert settings.qwen_warmup_enabled is True
    assert settings.qwen_warmup_timeout_seconds == 45

    with pytest.raises(ValidationError):
        Settings(
            app_env="test",
            _env_file=None,
            workflow_default_timeout_seconds=601,
        )

    with pytest.raises(ValidationError):
        Settings(
            app_env="test",
            _env_file=None,
            qwen_warmup_timeout_seconds=0,
        )


def test_research_analysis_model_assistance_defaults_are_bounded() -> None:
    settings = Settings(app_env="test", _env_file=None)

    assert settings.research_analysis_model_assist_enabled is True
    assert settings.research_analysis_model_assist_max_tokens == 900
    assert settings.research_analysis_model_direct_enabled is True
    assert settings.research_analysis_model_direct_max_tokens == 2400
    assert settings.research_analysis_model_input_max_chars == 80_000

    with pytest.raises(ValidationError):
        Settings(
            app_env="test",
            research_analysis_model_assist_max_tokens=128,
            _env_file=None,
        )

    with pytest.raises(ValidationError):
        Settings(
            app_env="test",
            research_analysis_model_input_max_chars=999,
            _env_file=None,
        )


def test_production_requires_server_qdrant() -> None:
    with pytest.raises(ValidationError, match="QDRANT_MODE must be server"):
        Settings(
            app_env="production",
            auth_required=True,
            auth_allow_guest=False,
            default_agent_provider="local",
            qdrant_mode="local",
            _env_file=None,
        )

    settings = Settings(
        app_env="production",
        auth_required=True,
        auth_allow_guest=False,
        default_agent_provider="local",
        qdrant_mode="server",
        langgraph_checkpoint_enabled=False,
        langgraph_checkpoint_backend="disabled",
        allow_mock_fallback=False,
        allow_agent_mocks=False,
        enable_debug_api=False,
        rag_debug_enabled=False,
        _env_file=None,
    )
    assert settings.qdrant_mode == "server"


def test_production_rejects_process_local_langgraph_checkpoints() -> None:
    with pytest.raises(ValidationError, match="LANGGRAPH_CHECKPOINT_BACKEND=memory"):
        Settings(
            app_env="production",
            auth_required=True,
            auth_allow_guest=False,
            qdrant_mode="server",
            _env_file=None,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("allow_mock_fallback", True, "ALLOW_MOCK_FALLBACK must be false"),
        ("allow_agent_mocks", True, "ALLOW_AGENT_MOCKS must be false"),
        ("enable_debug_api", True, "ENABLE_DEBUG_API must be false"),
        ("rag_debug_enabled", True, "RAG_DEBUG_ENABLED must be false"),
        ("enable_legacy_runtime", True, "legacy executable"),
        ("allow_legacy_fallback", True, "legacy executable"),
        ("use_old_router", True, "legacy executable"),
        ("shadow_can_mutate", True, "legacy executable"),
    ],
)
def test_production_forbids_mock_and_debug_surfaces(
    field: str, value: bool, message: str
) -> None:
    base: dict[str, object] = dict(
        app_env="production",
        auth_required=True,
        auth_allow_guest=False,
        default_agent_provider="local",
        qdrant_mode="server",
        langgraph_checkpoint_enabled=False,
        langgraph_checkpoint_backend="disabled",
        allow_mock_fallback=False,
        allow_agent_mocks=False,
        enable_debug_api=False,
        rag_debug_enabled=False,
        _env_file=None,
    )
    base[field] = value
    with pytest.raises(ValidationError, match=message):
        Settings(**base)


def test_production_rejects_mock_agent_provider() -> None:
    with pytest.raises(
        ValidationError, match="DEFAULT_AGENT_PROVIDER=mock is forbidden"
    ):
        Settings(
            app_env="production",
            auth_required=True,
            auth_allow_guest=False,
            qdrant_mode="server",
            default_agent_provider="mock",
            allow_mock_fallback=False,
            allow_agent_mocks=False,
            enable_debug_api=False,
            rag_debug_enabled=False,
            langgraph_checkpoint_enabled=False,
            langgraph_checkpoint_backend="disabled",
            _env_file=None,
        )


def test_production_fail_closed_without_mock_or_debug() -> None:
    settings = Settings(
        app_env="production",
        auth_required=True,
        auth_allow_guest=False,
        default_agent_provider="local",
        qdrant_mode="server",
        langgraph_checkpoint_enabled=False,
        langgraph_checkpoint_backend="disabled",
        allow_mock_fallback=False,
        allow_agent_mocks=False,
        enable_debug_api=False,
        rag_debug_enabled=False,
        _env_file=None,
    )
    assert settings.allow_mock_fallback is False
    assert settings.enable_debug_api is False


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
