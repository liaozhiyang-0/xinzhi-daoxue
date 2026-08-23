from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
REACT_ROOT = ROOT / "apps" / "web" / "src"


def source(relative: str) -> str:
    return (REACT_ROOT / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("route", "title"),
    [
        ("/", "欢迎使用芯智导学"),
        ("/workspace", "React Workspace"),
        ("/debug/rag", "多模态 RAG 调试"),
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
    if route == "/workspace":
        assert '<div id="root"></div>' in response.text
        assert "/react-assets/assets/index-" in response.text
        assert "legacy-workspace-contract" not in response.text
        return
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
    assert 'href: "/debug/execution"' in script
    assert 'href: "/debug/agents"' in script
    assert 'href: "/system"' in script
    assert 'href: "/admin"' in script
    assert 'href: "/demo"' in script
    assert "--bg-primary" in tokens
    assert '[data-theme="dark"]' in tokens


def test_ui_api_retries_after_access_token_expiry(client) -> None:
    script = client.get("/debug-assets/ui-core.js").text

    assert "refreshAccessSession" in script
    assert 'fetch("/api/v1/auth/refresh"' in script
    assert "response.status === 401" in script
    assert "allowRefresh" in script
    assert '!path.startsWith("/api/v1/auth/")' in script


def test_markdown_renderer_uses_text_nodes_not_untrusted_html(client) -> None:
    ui_core = client.get("/debug-assets/ui-core.js").text
    markdown = source("components/MarkdownRenderer.tsx")
    result = source("components/StructuredResult.tsx")

    assert "renderMarkdown" in ui_core
    assert "react-markdown" in markdown
    assert "rehype-katex" in markdown
    assert "evidence_view" in result
    assert "document.createTextNode" in ui_core
    assert "safeMarkdownUrl" in ui_core
    assert ".innerHTML" not in markdown
    assert ".innerHTML" not in result


def test_demo_scenarios_and_presentation_mode_are_explicit(client) -> None:
    page = client.get("/demo?presentation=1")
    script = client.get("/debug-assets/demo.js").text
    shell = client.get("/debug-assets/app-shell.css").text
    scenarios = client.get("/api/v1/scenarios")

    assert page.status_code == 200
    assert scenarios.status_code == 200
    payload = scenarios.json()
    expected_showcase_ids = {
        "faculty_course_copilot_v1",
        "assessment_diagnosis_v1",
        "student_learning_path_v1",
        "research_frontier_radar_v1",
        "department_knowledge_governance_v1",
        "academic_visual_problem_solver_v1",
    }
    assert expected_showcase_ids.issubset({item["id"] for item in payload})
    assert "research_data_workbench_v1" not in {item["id"] for item in payload}
    assert 'api("/api/v1/scenarios"' in script
    assert 'api("/api/v1/scenarios/readiness"' in script
    assert "开始场景演示" in script
    assert "presentation-mode" in shell


def test_workspace_shows_six_showcase_examples(client) -> None:
    page = client.get("/workspace")
    scenarios = source("demo/scenarios.ts")
    app = source("app/App.tsx")
    picker = source("components/ScenarioPicker.tsx")
    composer = source("features/chat/Composer.tsx")

    assert page.status_code == 200
    assert '<div id="root"></div>' in page.text
    assert scenarios.count('caseId: "') == 6
    assert scenarios.count("exampleInput:\n") == 6
    assert "ScenarioPicker" in app
    assert 'aria-label="六个示范场景"' in picker
    assert "responseDepth" in composer
    assert "更多选项" not in composer


def test_local_analog_question_image_is_served_from_the_question_bank(client) -> None:
    response = client.get("/debug-assets/question-bank/analog-opamp.jpg")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert len(response.content) > 1_000


def test_case6_demo_image_is_available_to_the_workspace(client) -> None:
    response = client.get("/demo-assets/case6-opamp.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 1_000


def test_workspace_uses_unified_member_identity_and_admin_boundary(client) -> None:
    app = source("app/App.tsx")
    contracts = source("workspace-contracts.ts")

    assert "userRole" in app
    assert "user_role" in contracts
    assert "loadScenarioRolePolicy" not in app
    assert '"admin"' in app


def test_system_page_only_reads_lightweight_status_endpoints(client) -> None:
    script = client.get("/debug-assets/system.js").text
    assert "/api/v1/health" in script
    assert "/api/v1/debug/rag/status" in script
    assert "/api/v1/agents" in script
    assert "/api/v1/tasks" not in script
    assert "/api/v1/debug/rag/run" not in script


def test_demo_assets_and_preflight_script_exist() -> None:
    assert (ROOT / "apps/api/app/static/debug/assets/demo-circuit.svg").is_file()
    preflight = (ROOT / "scripts/demo_cli.py").read_text(encoding="utf-8")
    startup = (ROOT / "scripts/start_demo.ps1").read_text(encoding="utf-8")
    assert "--with-cloud" not in preflight
    assert "api_secret" not in preflight.casefold()
    assert '"start"' in startup
    assert "xzd.ps1" in startup
    assert "team_launcher.py" in (ROOT / "xzd.ps1").read_text(encoding="utf-8")


def test_workspace_clears_previous_answer_while_next_task_runs() -> None:
    app = source("app/App.tsx")
    assert "setMessages([])" in app
    assert "setTask(null)" in app
    assert "setEvents([])" in app


def test_workspace_new_session_reenables_task_controls() -> None:
    app = source("app/App.tsx")
    assert "setTask(null)" in app
    assert (
        'disabled={Boolean(task && !["completed", "failed", "cancelled"].includes('
        'task.status)))}'
        in app
    )


def test_workspace_new_session_clears_capability_intent_override() -> None:
    app = source("app/App.tsx")
    assert "selectedScenarioId" in app
    assert "setSelectedScenarioId" in app
    assert "selectedScenario?.intent" in app


def test_workspace_new_session_clears_learning_follow_up_context() -> None:
    contracts = source("workspace-contracts.ts")
    assert "learningFollowUp" in contracts
    assert "source_task_id" in contracts
    assert "learning_action" in contracts


def test_workspace_new_session_clears_draft_question_and_course() -> None:
    app = source("app/App.tsx")
    composer = source("features/chat/Composer.tsx")
    assert "setActiveSession" in app
    assert "courseId" in app
    assert "setText(" in composer


def test_workspace_external_evidence_normalizes_runtime_items_and_deduplicates(
) -> None:
    result = source("components/StructuredResult.tsx")
    context = source("features/workspace/WorkspaceContextPane.tsx")
    assert "evidence_view" in result
    assert "filter((item)" in result
    assert "filter((item)" in context
    assert "evidence-grid" in result


def test_workspace_distinguishes_local_and_external_evidence_actions() -> None:
    result = source("components/StructuredResult.tsx")
    context = source("features/workspace/WorkspaceContextPane.tsx")
    assert "证据与依据" in result
    assert "资料依据" in context
    assert "context-evidence" in context


def test_workspace_reports_external_evidence_count_in_answer_info() -> None:
    result = source("components/StructuredResult.tsx")
    assert "evidence_view" in result
    assert "evidence.length" in result


def test_workspace_cancelled_task_is_not_presented_as_completed() -> None:
    app = source("app/App.tsx")
    status = source("components/TaskStatus.tsx")
    assert '"cancelled"' in app
    assert 'cancelled: "已取消"' in status
    assert "completed" in status


def test_shared_status_badge_keeps_cancelled_separate_from_failed() -> None:
    status = source("components/TaskStatus.tsx")
    css = source("styles/app.css")
    execution = source("components/ExecutionTrace.tsx")
    admin = (ROOT / "apps/api/app/static/debug/admin.js").read_text(encoding="utf-8")
    assert 'cancelled: "已取消"' in status
    assert "task-status-" in css
    assert '"task.cancelled"' in execution
    assert 'cancelled: "已停止"' in admin


def test_system_and_admin_pages_do_not_equate_mock_runtime_with_real_model() -> None:
    system = (ROOT / "apps/api/app/static/debug/system.js").read_text(encoding="utf-8")
    admin = (ROOT / "apps/api/app/static/debug/admin.js").read_text(encoding="utf-8")
    page = (ROOT / "apps/api/app/static/debug/system.html").read_text(encoding="utf-8")
    assert "health.model_runtime" in system
    assert "真实模型未配置" in system
    assert "health.model_runtime" in admin
    assert "真实模型未配置" in admin
    assert "system.js?v=20260822-real-model-status-v1" in page


def test_workspace_history_restore_shows_pending_state_for_running_task() -> None:
    app = source("app/App.tsx")
    result = source("components/StructuredResult.tsx")
    assert "listSessionMessages" in app
    assert "getTask(task.id)" in app
    assert "任务正在执行" in result


def test_workspace_history_uses_session_tasks_when_assistant_message_lags() -> None:
    app = source("app/App.tsx")
    sessions = source("api/sessions.ts")
    assert "listSessionMessages" in app
    assert "listSessions" in sessions
    assert "getSessionSummary" in app


def test_runtime_evidence_is_reported_as_completed_retrieval() -> None:
    presentation = (ROOT / "apps/api/app/services/task_presentation.py").read_text(
        encoding="utf-8"
    )
    assert (
        '"status": "completed" if bundle or runtime_evidence else "skipped"'
        in presentation
    )


def test_workspace_does_not_present_completed_empty_answers_as_success() -> None:
    result = source("components/StructuredResult.tsx")
    assert "当前没有可展示的核心结论" in result
    assert "requiresReview" in result
    assert "结果需要人工复核" in result


def test_workspace_uses_one_stable_provider_timeout_fallback_message() -> None:
    app = source("app/App.tsx")
    assert "formatApiError" in app
    assert "未知错误" in app


def test_workspace_restores_runtime_controls_after_checkpoint_reload() -> None:
    app = source("app/App.tsx")
    context = source("features/workspace/WorkspaceContextPane.tsx")
    result = source("components/StructuredResult.tsx")
    assert "getTaskRuntimeControls" in app
    assert "runtimeProjection" in app
    assert "等待人工复核" in result
    assert "任务详情" in context


def test_workspace_does_not_label_runtime_checkpoints_as_slow_model_response() -> None:
    transport = source("task-transport.ts")
    trace = source("components/ExecutionTrace.tsx")
    assert "renderLongWaitNotice" in transport
    assert "waiting_review" in trace
    assert "waiting_user" in trace


def test_workspace_archives_previous_answer_before_initializing_pending_task() -> None:
    app = source("app/App.tsx")
    assert "createTask(payload)" in app
    assert "setTask(created)" in app
    assert "setMessages((current) => [...current" in app


def test_workspace_clears_runtime_controls_when_stop_is_requested() -> None:
    app = source("app/App.tsx")
    assert "cancelTask(task.id)" in app
    assert "setRuntimeControls({})" in app
    assert "setRuntimeProjection(null)" in app


def test_workspace_session_reset_invalidates_old_runtime_control_requests() -> None:
    app = source("app/App.tsx")
    assert "setTask(null)" in app
    assert "if (!task?.id)" in app
    assert "setRuntimeControls({})" in app
    assert "setRuntimeProjection(null)" in app
