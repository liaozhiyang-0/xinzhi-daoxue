from __future__ import annotations


def test_react_workspace_is_default_with_explicit_legacy_rollback(
    client,
) -> None:
    legacy = client.get("/workspace")
    rollback = client.get("/workspace-legacy", follow_redirects=False)
    react = client.get("/workspace-react", follow_redirects=False)

    assert legacy.status_code == 200
    assert "React" in legacy.text
    assert rollback.status_code == 307
    assert rollback.headers["location"] == "/workspace"
    assert react.status_code == 307
    assert react.headers["location"] == "/workspace"
