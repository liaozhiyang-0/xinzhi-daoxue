def test_root_is_unified_home(client) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert "欢迎使用芯智导学" in response.text
    assert "/student" in response.text
    assert "/demo" in response.text


def test_debug_page_is_single_page_demo(client) -> None:
    response = client.get("/debug")
    assert response.status_code == 200
    assert "芯智导学" in response.text
    assert "演示中心" in response.text
    assert "presentation=1" in response.text
    assert "API Key" not in response.text

    script = client.get("/debug-assets/demo.js")
    assert script.status_code == 200
    assert 'api("/api/v1/scenarios"' in script.text
    assert 'api("/api/v1/scenarios/readiness"' in script.text
    assert "开始场景演示" in script.text
    assert "/api/v1/debug/execution/" in script.text


def test_workspace_serves_only_the_react_workspace(client) -> None:
    page = client.get("/workspace")
    assert page.status_code == 200
    assert '<div id="root"></div>' in page.text
    assert "/react-assets/assets/index-" in page.text
    assert "legacy-workspace-contract" not in page.text
    assert "research-analysis-v2-panel" not in page.text
    assert client.get("/debug-assets/workspace.html").status_code == 404
    assert client.get("/debug-assets/workspace.js").status_code == 404
    assert client.get("/debug-assets/student.html").status_code == 404

    root = __import__("pathlib").Path(__file__).resolve().parents[3]
    composer = (root / "apps/web/src/features/chat/Composer.tsx").read_text(
        encoding="utf-8"
    )
    assert "responseDepth" in composer
    assert "更多选项" not in composer
    assert "researchAnalysis" in composer
