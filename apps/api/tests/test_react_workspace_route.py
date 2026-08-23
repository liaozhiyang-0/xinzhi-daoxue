from __future__ import annotations


def test_react_workspace_is_default_with_explicit_legacy_rollback(
    client,
) -> None:
    legacy = client.get("/workspace")
    rollback = client.get("/workspace-legacy")
    react = client.get("/workspace-react")

    assert legacy.status_code == 200
    assert "React" in legacy.text
    assert rollback.status_code == 200
    assert "workspace.js" in rollback.text
    assert react.status_code == 200
    assert "text/html" in react.headers.get("content-type", "")
    assert "React" in react.text
