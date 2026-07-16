def test_debug_page_is_local_mock_tool(client) -> None:
    response = client.get("/debug")
    assert response.status_code == 200
    assert "本地调试台" in response.text
    assert "不是讯飞星辰真实输出" in response.text
    assert "API Key" not in response.text
