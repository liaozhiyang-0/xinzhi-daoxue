from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("route", "title"),
    [
        ("/", "欢迎使用芯智导学"),
        ("/student", "今天想学习什么"),
        ("/workspace", "今天想学习什么"),
        ("/debug/rag", "统一执行调试"),
        ("/debug/execution", "统一执行调试"),
        ("/debug/agents", "Agent 管理"),
        ("/system", "系统状态"),
        ("/demo", "演示中心"),
        ("/debug", "演示中心"),
    ],
)
def test_unified_routes_share_app_shell(client, route: str, title: str) -> None:
    response = client.get(route, follow_redirects=False)
    assert response.status_code == 200
    assert title in response.text
    assert 'id="app-sidebar"' in response.text
    assert 'id="app-topbar"' in response.text
    assert "/debug-assets/design-tokens.css" in response.text
    assert "/debug-assets/ui-core.js" in response.text


def test_theme_status_and_navigation_are_centralized(client) -> None:
    script = client.get("/debug-assets/ui-core.js").text
    tokens = client.get("/debug-assets/design-tokens.css").text

    assert 'localStorage.getItem("xinzhi_theme")' in script
    assert 'matchMedia("(prefers-color-scheme: dark)")' in script
    assert "开发模拟" in script
    assert "降级运行" in script
    assert 'href: "/workspace"' in script
    assert 'href: "/debug/execution"' not in script
    assert 'href: "/debug/agents"' not in script
    assert 'href: "/system"' not in script
    assert 'href: "/admin"' in script
    assert 'href: "/demo"' in script
    assert "--bg-primary" in tokens
    assert '[data-theme="dark"]' in tokens


def test_markdown_renderer_uses_text_nodes_not_untrusted_html(client) -> None:
    script = client.get("/debug-assets/ui-core.js").text
    student = client.get("/debug-assets/workspace.js").text

    assert "renderMarkdown" in script
    assert "document.createTextNode" in script
    assert "safeMarkdownUrl" in script
    assert 'class: "markdown-image"' in script
    assert ".innerHTML" not in student
    assert 'renderMarkdown($("#answer-text")' in student


def test_demo_scenarios_and_presentation_mode_are_explicit(client) -> None:
    page = client.get("/demo?presentation=1")
    script = client.get("/debug-assets/demo.js").text
    shell = client.get("/debug-assets/app-shell.css").text

    assert page.status_code == 200
    for scene in (
        "课程知识问答",
        "教案设计",
        "作业批改",
        "学术写作",
        "数据分析",
        "边界与一次重路由",
    ):
        assert scene in script
    assert "mode=solve" not in script
    assert "预计时间" in script
    assert "presentation-mode" in shell
    assert "/api/v1/debug/execution/" in script


def test_system_page_only_reads_lightweight_status_endpoints(client) -> None:
    script = client.get("/debug-assets/system.js").text
    assert "/api/v1/health" in script
    assert "/api/v1/debug/rag/status" in script
    assert "/api/v1/agents" in script
    assert "/api/v1/tasks" not in script
    assert "/api/v1/debug/rag/run" not in script


def test_demo_assets_and_preflight_script_exist() -> None:
    root = Path(__file__).resolve().parents[3]
    assert (root / "apps/api/app/static/debug/assets/demo-circuit.svg").is_file()
    preflight = (root / "scripts/demo_cli.py").read_text(encoding="utf-8")
    startup = (root / "scripts/start_demo.ps1").read_text(encoding="utf-8")
    assert "--with-cloud" in preflight
    assert "api_secret" not in preflight.casefold()
    assert '"start"' in startup
    assert "xzd.ps1" in startup
    assert "team_launcher.py" in (root / "xzd.ps1").read_text(encoding="utf-8")
