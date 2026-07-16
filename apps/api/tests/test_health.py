def test_root_and_v1_health(client) -> None:
    for path in ("/health", "/api/v1/health"):
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["environment"] == "test"
        assert payload["database"] == "ok"
        assert payload["default_provider"] == "mock"
