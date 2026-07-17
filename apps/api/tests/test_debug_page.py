def test_root_redirects_to_demo(client) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/debug"


def test_debug_page_is_single_page_demo(client) -> None:
    response = client.get("/debug")
    assert response.status_code == 200
    assert "芯智导学" in response.text
    assert "文字题" in response.text
    assert "图片题" in response.text
    assert "识别后的题目摘要" in response.text
    assert "API Key" not in response.text

    script = client.get("/debug-assets/app.js")
    assert script.status_code == 200
    assert "URL.createObjectURL" in script.text
    assert "submitButton.disabled" in script.text
    assert 'new EventSource(`/api/v1/tasks/${id}/stream`)' in script.text
