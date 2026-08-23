def test_root_and_v1_health_expose_mock_and_model_runtime_separately(client) -> None:
    for path in ("/health", "/api/v1/health"):
        response = client.get(path, headers={"X-Request-ID": "req-test"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["database"] == "ok"
        assert payload["requested_provider"] == "mock"
        assert payload["active_provider"] == "mock"
        assert payload["provider_mode"] == "mock"
        assert "xingchen" not in response.text.casefold()
        assert payload["provider_mode"] == "mock"
        assert set(payload) == {
            "status",
            "environment",
            "database",
            "redis",
            "minio",
            "requested_provider",
            "active_provider",
            "provider_mode",
            "version",
            "runtime_identity",
            "configuration_status",
            "configuration_warnings",
            "model_runtime",
            "external_retrieval",
            "task_queue",
        }
        assert payload["runtime_identity"]["solver_ct_baseline"] == (
            "SOLVER_CT_v1.0_frozen"
        )
        assert payload["configuration_status"] == "degraded"
        assert "active_agent_provider_mock" in payload["configuration_warnings"]
        assert "model_provider_unconfigured" in payload["configuration_warnings"]
        assert payload["model_runtime"]["real_provider_configured"] is False
        assert isinstance(payload["task_queue"], dict)
        assert payload["external_retrieval"]["configured"] is True
        assert payload["external_retrieval"]["cache"]["enabled"] is True
        assert response.headers["X-Request-ID"] == "req-test"
