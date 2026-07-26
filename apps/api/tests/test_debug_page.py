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
    assert "课程知识问答" in script.text
    assert "教案设计" in script.text
    assert "数据分析" in script.text
    assert "/api/v1/debug/execution/" in script.text
