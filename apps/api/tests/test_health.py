def test_root_and_v1_health_show_only_mock(client) -> None:
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
            "external_retrieval",
            "task_queue",
        }
        assert isinstance(payload["task_queue"], dict)
        assert payload["external_retrieval"]["configured"] is True
        assert payload["external_retrieval"]["cache"]["enabled"] is True
        assert response.headers["X-Request-ID"] == "req-test"
