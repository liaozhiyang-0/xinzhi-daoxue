from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("route", "title"),
    [
        ("/", "欢迎使用芯智导学"),
        ("/student", "把目标交给学科智能体"),
        ("/workspace", "把目标交给学科智能体"),
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
    student = "\n".join(
        (
            client.get("/debug-assets/workspace.js").text,
            client.get("/debug-assets/workspace-task-transport.js").text,
        )
    )

    assert "renderMarkdown" in script
    assert "cleanEvidenceExcerpt" in student
    assert "evidenceDisplayExcerpt" in student
    assert "latexStructureSafe" in script
    assert "length > 2400" in script
    assert 'class: "math-latex-fallback", text: latex || "(empty formula)"' in script
    assert "cleanMarkdownImageLinks" in student
    assert "cleanInlineFormulaArtifacts" in student
    assert "cleanRawLatexFragments" in student
    assert (
        '$("#source-summary").textContent = `参考课程资料 '
        '${state.evidence.length}`' in student
    )
    assert "evidenceRelatedImages" in student
    assert "function evidenceExternalUrl(item)" in student
    assert '"外部来源 · 请打开原文核验"' in student
    assert 'text: "打开原文"' in student
    assert 'String(item.source_ref || "").startsWith("kb://")' in student
    assert ".replace(/-{3,}/gu, \" \")" in student
    assert "renderRecoveredMathBlock" in script
    assert "markdownInsideMath" in script
    assert 'text.startsWith("**", index)' in script
    assert 'el("strong"' in script
    assert "document.createTextNode" in script
    assert "safeMarkdownUrl" in script
    assert 'class: "markdown-image"' in script
    assert ".innerHTML" not in student
    assert "new DOMParser().parseFromString" in student
    assert "terminalPollTimer" in student
    assert 'renderMarkdown($("#answer-text")' in student


def test_demo_scenarios_and_presentation_mode_are_explicit(client) -> None:
    page = client.get("/demo?presentation=1")
    script = client.get("/debug-assets/demo.js").text
    shell = client.get("/debug-assets/app-shell.css").text
    scenarios = client.get("/api/v1/scenarios")

    assert page.status_code == 200
    assert scenarios.status_code == 200
    payload = scenarios.json()
    assert len(payload) == 5
    assert "research_data_workbench_v1" not in {item["id"] for item in payload}
    assert 'api("/api/v1/scenarios"' in script
    assert 'api("/api/v1/scenarios/readiness"' in script
    assert "开始场景演示" in script
    assert "mode=solve" not in script
    assert "示例问题" in script
    assert "presentation-mode" in shell
    assert "/api/v1/debug/execution/" in script
    assert "role=${encodeURIComponent(audience)}" not in script
    assert "scenario.roles?.find((role)" not in script
    assert "scenario.demo_cases?.[0]" in script
    assert "expected_output" in script


def test_workspace_shows_six_showcase_examples(client) -> None:
    page = client.get("/workspace")

    assert page.status_code == 200
    assert page.text.count('data-capability=') == 6
    assert 'aria-label="项目展示案例"' in page.text
    assert 'class="composer-agent-track"' not in page.text
    assert 'id="detected-course"' in page.text
    assert 'id="detected-learning-mode"' in page.text
    assert 'placeholder="描述你的学习、教学或研究目标；Shift+Enter 换行"' in page.text
    assert 'id="context-task-question"' not in page.text
    assert 'id="answer-query"' not in page.text
    assert '<select id="course-select"' not in page.text
    assert '<select id="teaching-mode"' not in page.text
    assert 'data-scenario-id=' not in page.text
    assert 'data-capability="data_analysis"' not in page.text
    assert "为什么电容电压不能突变？" not in page.text
    for title in (
        "教师智能备课",
        "作业批改与首错诊断",
        "学生个性化学习路径",
        "科研前沿检索与证据简报",
        "学院知识库治理与课程资产发布",
        "模拟电子技术 · 电路诊断与边界分析",
    ):
        assert title in page.text
    assert 'data-image-src="/debug-assets/question-bank/analog-opamp.jpg"' in page.text
    assert "模电测试集_图2.1.1_运算放大器电路.jpg" in page.text
    assert 'class="prompt-example-image"' not in page.text

    script = client.get("/debug-assets/workspace.js").text
    assert "activeScenarioId = \"\"" in script
    assert "scenario_id: state.activeScenarioId || null" in script
    assert (
        "const attachExampleImage = (button) => materialManager.attachExample(button);"
        in script
    )
    assert (
        'function inferLearningMode(question = "", studentAttempt = "")' in script
    )
    assert "function updateAutoDetection(" in script
    assert "function setTaskQuestionDisplay(taskOrQuestion, task = null)" not in script
    assert 'const requestedCourse = learningFollowUp?.course_id || "AUTO";' in script
    assert 'const requestedIntent = learningFollowUp?.intent || "unknown";' in script
    assert 'function taskQuestion(task)' in script
    assert '["实际提问", taskQuestion(task).slice(0, 800)]' in script


def test_local_analog_question_image_is_served_from_the_question_bank(client) -> None:
    response = client.get("/debug-assets/question-bank/analog-opamp.jpg")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert len(response.content) > 1_000


def test_workspace_uses_unified_member_identity_and_admin_boundary(client) -> None:
    script = client.get("/debug-assets/workspace.js").text

    assert "effectiveWorkspaceRole(identity)" in script
    assert "user_role: state.userRole" in script
    assert "loadScenarioRolePolicy" not in script
    assert 'return role === "admin" ? "admin" : "student";' in script


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
    assert "--with-cloud" not in preflight
    assert "api_secret" not in preflight.casefold()
    assert '"start"' in startup
    assert "xzd.ps1" in startup
    assert "team_launcher.py" in (root / "xzd.ps1").read_text(encoding="utf-8")


def test_workspace_clears_previous_answer_while_next_task_runs() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "apps/api/app/static/debug/workspace.js").read_text(
        encoding="utf-8"
    )

    assert 'renderMarkdown($("#answer-text"), "");' in script
    assert '$("#answer-notices").replaceChildren();' in script
    assert "renderEvidence([], {});" in script


def test_workspace_new_session_reenables_task_controls() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "apps/api/app/static/debug/workspace.js").read_text(
        encoding="utf-8"
    )
    reset_start = script.index("function resetConversation()")
    reset_end = script.index("async function newSession()", reset_start)

    assert "setBusy(false);" in script[reset_start:reset_end]


def test_workspace_new_session_clears_capability_intent_override() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "apps/api/app/static/debug/workspace.js").read_text(
        encoding="utf-8"
    )
    reset_start = script.index("function resetConversation()")
    reset_end = script.index("async function newSession()", reset_start)

    assert 'state.intentOverride = "";' in script[reset_start:reset_end]
    assert "updateResearchAnalysisPanel();" in script[reset_start:reset_end]


def test_workspace_new_session_clears_learning_follow_up_context() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "apps/api/app/static/debug/workspace.js").read_text(
        encoding="utf-8"
    )
    reset_start = script.index("function resetConversation()")
    reset_end = script.index("async function newSession()", reset_start)

    assert "pendingLearningFollowUp = null;" in script[reset_start:reset_end]


def test_workspace_new_session_clears_draft_question_and_course() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "apps/api/app/static/debug/workspace.js").read_text(
        encoding="utf-8"
    )
    reset_start = script.index("function resetConversation()")
    reset_end = script.index("async function newSession()", reset_start)
    reset = script[reset_start:reset_end]

    assert 'state.activeCourse = "AUTO";' in reset
    assert 'localStorage.removeItem("xinzhi_student_course");' in reset
    assert 'questionInput.value = "";' in reset
    assert 'courseSelect.value = "AUTO";' in reset


def test_workspace_external_evidence_normalizes_runtime_items_and_deduplicates(
) -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "apps/api/app/static/debug/workspace.js").read_text(
        encoding="utf-8"
    )

    assert "function externalEvidenceUrl(item)" in script
    assert "item.canonical_url" in script
    assert "https://doi.org/" in script
    assert "https://arxiv.org/abs/" in script
    assert "function normalizedExternalItems(items)" in script
    assert "function externalEvidenceIdentityKeys(item)" in script
    assert "external_search_view" in script
    assert "retrieval.length ? retrieval : view" in script
    assert "doi:${doi}" in script
    assert "arxiv:${arxiv}" in script
    assert "content_excerpt" in script
    assert "function externalEvidenceDateLabel(item)" in script
    assert "if (!keys.length)" in script
    assert "source:${sourceRef}" in script
    assert "item.updated_at || item.published_at" in script
    assert "new Date(raw)" in script


def test_workspace_distinguishes_local_and_external_evidence_actions() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "apps/api/app/static/debug/workspace.js").read_text(
        encoding="utf-8"
    )

    card_start = script.index("function evidenceCard(item)")
    card_end = script.index("function focusEvidence", card_start)
    card = script[card_start:card_end]
    assert 'String(item.source_ref || "").startsWith("kb://")' in card
    assert '"本地只读资料"' in card
    assert '"外部来源 · 请打开原文核验"' in card
    assert 'text: "无法打开原文"' in card
    assert 'target: "_blank"' in card
    assert 'rel: "noopener noreferrer"' in card
    assert "openEvidenceDocument(item)" in card


def test_workspace_reports_external_evidence_count_in_answer_info() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "apps/api/app/static/debug/workspace.js").read_text(
        encoding="utf-8"
    )

    assert (
        "externalEvidenceCount = externalItemsForDisplay("
        "result.structured_result).length"
        in script
    )
    assert 'externalEvidenceCount ? "外部证据" : "资料使用"' in script


def test_workspace_cancelled_task_is_not_presented_as_completed() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "apps/api/app/static/debug/workspace.js").read_text(
        encoding="utf-8"
    )

    assert 'task?.status === "cancelled"' in script
    assert 'status_label: "已停止"' in script
    assert 'answer_quality_status: "cancelled"' in script
    assert "不会把空结果当作有效答案" in script


def test_workspace_history_restore_shows_pending_state_for_running_task() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "apps/api/app/static/debug/workspace.js").read_text(
        encoding="utf-8"
    )
    restore_start = script.index("const resumableStatuses")
    restore_end = script.index("if (restoredTask", restore_start)
    restore = script[restore_start:restore_end]

    assert "markAnswerPending();" in restore
    assert "waitForTask(latestTask.id, requestSequence)" in restore


def test_workspace_history_uses_session_tasks_when_assistant_message_lags() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "apps/api/app/static/debug/workspace.js").read_text(
        encoding="utf-8"
    )

    assert "sessions/${sessionId}/tasks?limit=50" in script
    assert "latestSummary?.id" in script
    assert "latestSessionTask = await api(ownedTaskUrl(latestSummary.id))" in script
    assert "restoredTask = latestSessionTask" in script


def test_runtime_evidence_is_reported_as_completed_retrieval() -> None:
    root = Path(__file__).resolve().parents[3]
    presentation = (root / "apps/api/app/services/task_presentation.py").read_text(
        encoding="utf-8"
    )
    assert (
        '"status": "completed" if bundle or runtime_evidence else "skipped"'
        in presentation
    )


def test_workspace_does_not_present_completed_empty_answers_as_success() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "apps/api/app/static/debug/workspace.js").read_text(
        encoding="utf-8"
    )
    assert "function taskHasRenderableAnswer" in script
    assert 'status_label: "结果异常"' in script
    assert "结果需要复核" in script


def test_workspace_restores_runtime_controls_after_checkpoint_reload() -> None:
    root = Path(__file__).resolve().parents[3]
    script = (root / "apps/api/app/static/debug/workspace.js").read_text(
        encoding="utf-8"
    )

    assert "function renderRuntimeCheckpoint(task)" in script
    assert '"waiting_review"' in script
    assert "renderRuntimeCheckpoint(latestTask);" in script
    assert "function observeResumedRuntimeTask(taskId)" in script
    assert 'if (["resume", "approve", "input"].includes(action))' in script
    assert "function decodeHtmlEntities(value)" in script
    assert "decodeHtmlEntities(item.abstract" in script
