from __future__ import annotations


def test_legacy_workspace_is_default_with_react_entry_quarantined(
    client,
) -> None:
    workspace = client.get("/workspace")
    legacy = client.get("/workspace-legacy")
    react = client.get("/workspace-react", follow_redirects=False)

    for response in (workspace, legacy):
        assert response.status_code == 200
        assert 'class="workspace-page"' in response.text
        assert 'id="student-form"' in response.text
        assert "/debug-assets/workspace.js" in response.text
        assert "/react-assets/assets/index-" not in response.text
    assert react.status_code == 307
    assert react.headers["location"] == "/workspace"
