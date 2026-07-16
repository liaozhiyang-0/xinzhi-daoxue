def test_root_and_v1_health_show_only_mock(client) -> None:
    for path in ("/health", "/api/v1/health"):
        response = client.get(path, headers={"X-Request-ID": "req-test"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["database"] == "ok"
        assert payload["requested_provider"] == "mock"
        assert payload["active_provider"] == "mock"
        assert payload["provider_mode"] == "only_mock"
        assert payload["xingchen_publication_status"] == "not_published"
        assert payload["xingchen_runtime_available"] is False
        assert response.headers["X-Request-ID"] == "req-test"
