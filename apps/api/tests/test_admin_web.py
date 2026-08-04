from __future__ import annotations

from fastapi.testclient import TestClient


def test_admin_and_login_pages_are_available(client: TestClient) -> None:
    admin = client.get("/admin")
    assert admin.status_code == 200
    assert admin.headers["cache-control"] == "no-store, max-age=0"
    assert "/debug-assets/admin.css" in admin.text
    assert "admin.css?v=20260804-feature-switch-v2" in admin.text
    assert "/debug-assets/admin.js" in admin.text
    assert "admin.js?v=20260804-feature-switch-v2" in admin.text
    assert 'data-admin-module-target="settings"' in admin.text
    assert 'id="admin-feature-settings"' in admin.text

    login = client.get("/login?next=/admin")
    assert login.status_code == 200
    assert "/debug-assets/login.js" in login.text
    assert "登录账号" in login.text


def test_admin_api_is_not_open_to_anonymous_users(client: TestClient) -> None:
    response = client.get("/api/v1/admin/overview")
    assert response.status_code == 401


def test_admin_feature_switch_contract(client: TestClient) -> None:
    script = client.get("/debug-assets/admin.js")

    assert script.status_code == 200
    assert "/api/v1/admin/settings/features" in script.text
    assert "loadAdminFeatureSettings" in script.text
    assert "updateFeatureSetting" in script.text
    assert 'class: "feature-toggle-button"' in script.text
    assert 'aria-pressed' in script.text
