const { $, all, api, badge, el, initShell, initTabs, toast } = XinzhiUI;

const roleLabels = { student: "学生", teacher: "教师", researcher: "研究者", operator: "运营", admin: "管理员" };
const statusLabels = { active: "启用", disabled: "停用", locked: "锁定" };
let currentPrincipal = null;

function dateText(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("zh-CN", { dateStyle: "medium", timeStyle: "short" });
}

function metric(label, value, status = "ready") {
  return el("article", { class: "admin-metric" }, [badge(status), el("strong", { text: String(value ?? 0) }), el("span", { text: label })]);
}

function showLogin(message = "") {
  $("#admin-app").hidden = true;
  $("#admin-login").hidden = false;
  $("#admin-login-error").textContent = message;
}

function showApp() {
  $("#admin-login").hidden = true;
  $("#admin-app").hidden = false;
}

function renderOverview(data) {
  $("#admin-metrics").replaceChildren(
    metric("账号总数", data.account_count),
    metric("启用账号", data.active_account_count, "ready"),
    metric("停用账号", data.disabled_account_count, data.disabled_account_count ? "disabled" : "ready"),
    metric("锁定账号", data.locked_account_count, data.locked_account_count ? "warning" : "ready"),
    metric("活跃会话", data.active_session_count),
    metric("审计事件", data.audit_event_count),
  );
}

function renderDistribution(target, values, labels) {
  const entries = Object.entries(values || {});
  const total = entries.reduce((sum, [, value]) => sum + Number(value || 0), 0) || 1;
  if (!entries.length) {
    $(target).replaceChildren(el("p", { class: "empty-state", text: "暂无数据" }));
    return;
  }
  $(target).replaceChildren(...entries.sort((a, b) => b[1] - a[1]).map(([key, value]) => {
    const amount = Number(value || 0);
    return el("div", { class: "distribution-row" }, [
      el("span", { text: labels[key] || key }),
      el("div", { class: "distribution-track" }, el("div", { class: "distribution-fill", style: `width:${Math.max(4, amount / total * 100)}%` })),
      el("strong", { text: String(amount) }),
    ]);
  }));
}

function renderAccountDistribution(items) {
  const roleCounts = {};
  const statusCounts = {};
  items.forEach((item) => {
    roleCounts[item.role] = (roleCounts[item.role] || 0) + 1;
    statusCounts[item.status] = (statusCounts[item.status] || 0) + 1;
  });
  renderDistribution("#account-distribution", roleCounts, roleLabels);
  const statusRows = Object.fromEntries(Object.entries(statusCounts).map(([key, value]) => [`状态 · ${statusLabels[key] || key}`, value]));
  renderDistribution("#account-status-distribution", statusRows, {});
}

function accountActions(account) {
  const nextStatus = account.status === "active" ? "disabled" : "active";
  const action = el("div", { class: "table-actions" });
  action.append(el("button", { type: "button", text: nextStatus === "active" ? "启用" : "停用", onclick: () => updateAccount(account, { status: nextStatus }) }));
  action.append(el("button", { type: "button", text: "重置密码", onclick: () => resetPassword(account) }));
  action.append(el("button", { type: "button", text: "撤销会话", onclick: () => revokeSessions(account) }));
  return action;
}

function renderAccounts(items) {
  if (!items.length) {
    $("#account-table").replaceChildren(el("p", { class: "empty-state", text: "没有符合条件的账号" }));
    return;
  }
  const head = ["账号", "角色", "状态", "最近登录", "创建时间", "操作"];
  const table = el("table", { class: "admin-table" }, [el("thead", {}, el("tr", {}, head.map((item) => el("th", { text: item }))))]);
  const body = el("tbody");
  items.forEach((account) => {
    body.append(el("tr", {}, [
      el("td", {}, [el("strong", { text: account.display_name || account.login }), el("span", { text: account.login })]),
      el("td", { text: roleLabels[account.role] || account.role }),
      el("td", {}, badge(account.status, statusLabels[account.status] || account.status)),
      el("td", { text: dateText(account.last_login_at) }),
      el("td", { text: dateText(account.created_at) }),
      el("td", {}, accountActions(account)),
    ]));
  });
  table.append(body);
  $("#account-table").replaceChildren(table);
}

function renderSessions(items) {
  if (!items.length) {
    $("#session-table").replaceChildren(el("p", { class: "empty-state", text: "当前没有活跃会话" }));
    return;
  }
  const table = el("table", { class: "admin-table" }, [el("thead", {}, el("tr", {}, ["账号", "来源", "创建时间", "刷新有效期", "操作"].map((item) => el("th", { text: item }))))]);
  const body = el("tbody");
  items.forEach((session) => {
    body.append(el("tr", {}, [
      el("td", {}, [el("strong", { text: session.login }), el("span", { text: session.account_id })]),
      el("td", {}, [el("strong", { text: session.ip_address || "未知来源" }), el("span", { text: session.user_agent || "未知设备" })]),
      el("td", { text: dateText(session.created_at) }),
      el("td", { text: dateText(session.refresh_expires_at) }),
      el("td", {}, el("div", { class: "table-actions" }, el("button", { type: "button", text: "撤销", onclick: async () => {
        if (!window.confirm("确认撤销这个会话？")) return;
        try { await api(`/api/v1/admin/sessions/${encodeURIComponent(session.id)}`, { method: "DELETE" }); toast("会话已撤销"); await loadDashboard(); }
        catch (error) { toast(error.message, "failed"); }
      } }))),
    ]));
  });
  table.append(body);
  $("#session-table").replaceChildren(table);
}

function renderAudit(items) {
  if (!items.length) {
    $("#audit-table").replaceChildren(el("p", { class: "empty-state", text: "暂无审计事件" }));
    return;
  }
  const table = el("table", { class: "admin-table" }, [el("thead", {}, el("tr", {}, ["时间", "动作", "操作者", "目标", "详情"].map((item) => el("th", { text: item }))))]);
  const body = el("tbody");
  items.forEach((item) => {
    body.append(el("tr", {}, [
      el("td", { text: dateText(item.created_at) }),
      el("td", { text: item.action }),
      el("td", { text: item.actor_account_id || "系统" }),
      el("td", { text: [item.target_type, item.target_id].filter(Boolean).join(" / ") || "—" }),
      el("td", { text: JSON.stringify(item.details || {}) }),
    ]));
  });
  table.append(body);
  $("#audit-table").replaceChildren(table);
}

async function loadAccounts() {
  const form = new FormData($("#account-filters"));
  const params = new URLSearchParams({ limit: "200" });
  ["search", "role", "status"].forEach((key) => { if (form.get(key)) params.set(key, form.get(key)); });
  const [filtered, all] = await Promise.all([
    api(`/api/v1/admin/accounts?${params}`),
    api("/api/v1/admin/accounts?limit=200"),
  ]);
  renderAccounts(filtered.items || []);
  renderAccountDistribution(all.items || []);
}

async function loadDashboard() {
  try {
    const [overview, sessions, audit] = await Promise.all([
      api("/api/v1/admin/overview"),
      api("/api/v1/admin/sessions?active_only=true"),
      api("/api/v1/admin/audit-logs?limit=100"),
    ]);
    renderOverview(overview);
    renderSessions(sessions);
    renderAudit(audit);
    const auditCounts = {};
    audit.forEach((item) => { auditCounts[item.action] = (auditCounts[item.action] || 0) + 1; });
    renderDistribution("#audit-distribution", auditCounts, {});
    await loadAccounts();
  } catch (error) {
    if (error.status === 401 || error.status === 403) { showLogin(error.status === 403 ? "当前账号没有管理员权限" : "请先登录管理员账号"); return; }
    toast(error.message, "failed");
  }
}

async function updateAccount(account, changes) {
  try {
    await api(`/api/v1/admin/accounts/${encodeURIComponent(account.id)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes) });
    toast("账号已更新");
    await loadDashboard();
  } catch (error) { toast(error.message, "failed"); }
}

async function resetPassword(account) {
  const password = window.prompt(`为 ${account.login} 设置新密码（至少 12 个字符）`);
  if (!password) return;
  if (password.length < 12) { toast("密码至少需要 12 个字符", "failed"); return; }
  try {
    await api(`/api/v1/admin/accounts/${encodeURIComponent(account.id)}/reset-password`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password }) });
    toast("密码已重置，原有会话已撤销");
    await loadDashboard();
  } catch (error) { toast(error.message, "failed"); }
}

async function revokeSessions(account) {
  if (!window.confirm(`确认撤销 ${account.login} 的全部会话？`)) return;
  try {
    const result = await api(`/api/v1/admin/accounts/${encodeURIComponent(account.id)}/revoke-sessions`, { method: "POST" });
    toast(`已撤销 ${result.revoked_count} 个会话`);
    await loadDashboard();
  } catch (error) { toast(error.message, "failed"); }
}

const managementModules = new Map();
const loadedManagementModules = new Set();

function registerManagementModule(id, loader) {
  managementModules.set(id, loader);
}

function taskStatusLabel(status) {
  return {
    created: "已创建", queued: "排队中", running: "运行中", waiting_user: "等待用户",
    waiting_review: "等待审核", completed: "已完成", failed: "失败", cancelled: "已取消",
  }[status] || status || "未知";
}

function renderTaskSummary(data) {
  $("#admin-task-summary").replaceChildren(
    metric("任务总数", data.total),
    metric("活跃任务", data.active, data.active ? "running" : "ready"),
    metric("已完成", data.completed, "success"),
    metric("失败任务", data.failed, data.failed ? "failed" : "ready"),
  );
}

function renderAdminTasks(items) {
  if (!items.length) {
    $("#admin-task-table").replaceChildren(el("p", { class: "empty-state", text: "暂无符合条件的任务" }));
    return;
  }
  const headings = ["任务", "用户", "课程 / 意图", "Agent", "状态", "创建时间", "操作"];
  const table = el("table", { class: "admin-table" }, [el("thead", {}, el("tr", {}, headings.map((item) => el("th", { text: item }))))]);
  const body = el("tbody");
  items.forEach((task) => {
    const view = el("button", { type: "button", text: "查看详情", onclick: () => loadAdminTaskDetail(task.id) });
    const trace = el("a", { class: "text-button", href: `/debug/execution?task_id=${encodeURIComponent(task.id)}`, text: "执行链" });
    body.append(el("tr", {}, [
      el("td", {}, [el("strong", { text: task.id }), el("span", { text: task.provider })]),
      el("td", {}, [el("strong", { text: task.display_name || task.login || "游客 / 外部用户" }), el("span", { text: task.user_id })]),
      el("td", {}, [el("strong", { text: task.course_id }), el("span", { text: task.intent })]),
      el("td", { text: task.agent_id }),
      el("td", {}, badge(task.status, taskStatusLabel(task.status))),
      el("td", { text: dateText(task.created_at) }),
      el("td", {}, el("div", { class: "table-actions" }, [view, trace])),
    ]));
  });
  table.append(body);
  $("#admin-task-table").replaceChildren(table);
}

async function appendAdminTaskApproval(target, taskId) {
  const action = el("button", {
    class: "button primary",
    type: "button",
    text: "\u63d0\u4ea4\u5ba1\u6279",
    onclick: () => approveAdminTask(taskId),
  });
  target.querySelector(".section-heading")?.append(action);
}

async function approveAdminTask(taskId) {
  const target = $("#admin-task-detail");
  const confirm = el("div", { class: "notice warning", role: "alert" }, [
    el("span", { text: "\u8bf7\u518d\u6b21\u70b9\u51fb\u4ee5\u786e\u8ba4\u5ba1\u6279\uff1b\u4efb\u52a1\u5c06\u4ece\u65ad\u70b9\u7ee7\u7eed\u6267\u884c\u3002" }),
    el("button", { class: "button primary", type: "button", text: "\u786e\u8ba4\u5ba1\u6279", onclick: () => submitAdminTaskApproval(taskId, confirm) }),
    el("button", { class: "text-button", type: "button", text: "\u53d6\u6d88", onclick: () => confirm.remove() }),
  ]);
  target.prepend(confirm);
}

async function submitAdminTaskApproval(taskId, confirmation) {
  confirmation.querySelectorAll("button").forEach((button) => { button.disabled = true; });
  try {
    const task = await api(`/api/v1/tasks/${encodeURIComponent(taskId)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    toast(`\u5ba1\u6279\u5df2\u63d0\u4ea4\uff0c\u5f53\u524d\u72b6\u6001\uff1a${task.status}`);
    await loadAdminTasks();
    await loadAdminTaskDetail(taskId);
  } catch (error) {
    toast(error.message || "\u5ba1\u6279\u5931\u8d25", "failed");
    confirmation.remove();
    await loadAdminTaskDetail(taskId);
  }
}

async function loadAdminTaskDetail(taskId) {
  const target = $("#admin-task-detail");
  target.hidden = false;
  target.replaceChildren(el("p", { class: "loading-state", text: "正在读取任务执行链…" }));
  try {
    const data = await api(`/api/v1/debug/execution/${encodeURIComponent(taskId)}`);
    target.replaceChildren(el("div", { class: "section-heading" }, [el("h3", { text: `任务详情 · ${taskId}` }), el("button", { class: "text-button", type: "button", text: "关闭", onclick: () => { target.hidden = true; } })]), el("pre", { class: "code-view", text: JSON.stringify(data, null, 2) }));
    const rawDetail = target.querySelector("pre.code-view");
    rawDetail?.remove();
    const taskSummary = data.task || {};
    const runtimeSummary = data.runtime || {};
    const eventSummary = Array.isArray(data.events) ? data.events : [];
    const evidenceCount = Array.isArray(data.retrieval?.final_evidence)
      ? data.retrieval.final_evidence.length
      : 0;
    const eventNumbers = eventSummary.map((item) => Number(item.sequence));
    const eventOrderOk = eventNumbers.every((value, index) => value === index + 1);
    const summary = el("div", { class: "admin-task-summary" }, [
      el("p", { text: `状态：${taskSummary.status || "unknown"} · ${taskSummary.course_id || ""} / ${taskSummary.intent || ""}` }),
      el("p", { text: `Agent：${taskSummary.agent_id || ""} · Runtime：${runtimeSummary.plan_version || "未进入 Runtime"}` }),
      el("p", { text: `证据 ${evidenceCount} 条 · 事件 ${eventSummary.length} 条 · 序号连续：${eventOrderOk ? "是" : "否"}` }),
    ]);
    target.append(summary, el("button", {
      class: "text-button",
      type: "button",
      text: "查看完整执行链",
      onclick: () => target.append(el("pre", { class: "code-view", text: JSON.stringify(data, null, 2) })),
    }));
    if (currentPrincipal?.role === "admin" && data.task?.status === "waiting_review") {
      await appendAdminTaskApproval(target, taskId);
    }
  } catch (error) {
    target.replaceChildren(el("p", { class: "error-state", text: error.message }));
  }
}

async function loadAdminTasks() {
  const form = new FormData($("#admin-task-filters"));
  const params = new URLSearchParams({ limit: "100" });
  ["search", "status", "course_id", "agent_id"].forEach((key) => { if (form.get(key)) params.set(key, form.get(key)); });
  const [summary, result] = await Promise.all([
    api("/api/v1/admin/task-summary"),
    api(`/api/v1/admin/tasks?${params.toString()}`),
  ]);
  renderTaskSummary(summary);
  renderAdminTasks(result.items || []);
}

const fileStatusLabels = { pending: "等待解析", processing: "解析中", ready: "已就绪", partial: "部分完成", failed: "失败" };

function renderAdminFileSummary(data) {
  $("#admin-file-summary").replaceChildren(
    metric("文件总数", data.total), metric("解析中", data.processing, data.processing ? "running" : "ready"),
    metric("已就绪", data.ready, "success"), metric("部分完成", data.partial, data.partial ? "warning" : "ready"),
    metric("解析失败", data.failed, data.failed ? "failed" : "ready"), metric("存储空间", `${(Number(data.total_bytes || 0) / 1024 / 1024).toFixed(1)} MB`),
  );
}

function renderAdminFiles(items) {
  if (!items.length) { $("#admin-file-table").replaceChildren(el("p", { class: "empty-state", text: "暂无符合条件的文件" })); return; }
  const headings = ["文件", "类型", "解析状态", "页数", "关联任务", "创建时间", "操作"];
  const table = el("table", { class: "admin-table" }, [el("thead", {}, el("tr", {}, headings.map((item) => el("th", { text: item }))))]);
  const body = el("tbody");
  items.forEach((file) => {
    const detail = el("button", { type: "button", text: "查看", onclick: async () => {
      const target = $("#admin-file-detail"); target.hidden = false; target.replaceChildren(el("pre", { class: "code-view", text: JSON.stringify(file, null, 2) }));
    } });
    body.append(el("tr", {}, [
      el("td", {}, [el("strong", { text: file.filename }), el("span", { text: file.id })]),
      el("td", {}, [el("strong", { text: file.content_type }), el("span", { text: `${Math.max(1, Math.round(file.size_bytes / 1024))} KB` })]),
      el("td", {}, badge(file.ingestion_status, fileStatusLabels[file.ingestion_status] || file.ingestion_status)),
      el("td", { text: String(file.page_count || "—") }), el("td", { text: file.task_id || "—" }),
      el("td", { text: dateText(file.created_at) }), el("td", {}, detail),
    ]));
  });
  table.append(body); $("#admin-file-table").replaceChildren(table);
}

async function loadAdminFiles() {
  const form = new FormData($("#admin-file-filters")); const params = new URLSearchParams({ limit: "200" });
  ["search", "ingestion_status", "content_type"].forEach((key) => { if (form.get(key)) params.set(key, form.get(key)); });
  const [summary, result] = await Promise.all([api("/api/v1/admin/file-summary"), api(`/api/v1/admin/files?${params.toString()}`)]);
  renderAdminFileSummary(summary); renderAdminFiles(result.items || []);
}

function renderAdminAgentDetail(target, data) {
  target.hidden = false;
  target.replaceChildren(el("div", { class: "section-heading" }, [el("h3", { text: `${data.display_name || data.agent_id} · 定义详情` }), el("button", { class: "text-button", type: "button", text: "关闭", onclick: () => { target.hidden = true; } })]), el("pre", { class: "code-view", text: JSON.stringify(data, null, 2) }));
}

function renderAdminAgents(items) {
  const configured = items.filter((item) => item.configured).length;
  const published = items.filter((item) => item.lifecycle_status === "published").length;
  const mockReady = items.filter((item) => item.mock_ready).length;
  $("#admin-agent-summary").replaceChildren(metric("注册 Agent", items.length), metric("已配置", configured, configured ? "ready" : "planned"), metric("已发布", published, published ? "success" : "planned"), metric("Mock 就绪", mockReady, mockReady ? "ready" : "planned"));
  if (!items.length) {
    $("#admin-agent-table").replaceChildren(el("p", { class: "empty-state", text: "暂无 Agent 注册信息" }));
    return;
  }
  const headings = ["Agent", "生命周期", "Provider", "配置", "课程", "最近契约测试", "操作"];
  const table = el("table", { class: "admin-table" }, [el("thead", {}, el("tr", {}, headings.map((item) => el("th", { text: item }))))]);
  const body = el("tbody");
  items.forEach((item) => {
    const detail = el("button", { type: "button", text: "查看", onclick: async () => { try { renderAdminAgentDetail($("#admin-agent-detail"), await api(`/api/v1/agents/${encodeURIComponent(item.agent_id)}`)); } catch (error) { toast(error.message, "failed"); } } });
    const validate = el("button", { type: "button", text: "验证", onclick: async () => { try { await api(`/api/v1/debug/agents/${encodeURIComponent(item.agent_id)}/validate`, { method: "POST" }); toast("Agent 配置验证完成"); await loadAdminAgents(); } catch (error) { toast(error.message, "failed"); } } });
    body.append(el("tr", {}, [
      el("td", {}, [el("strong", { text: item.display_name || item.agent_id }), el("span", { text: item.agent_id })]),
      el("td", {}, badge(item.lifecycle_status, item.lifecycle_status)),
      el("td", { text: item.provider || "-" }),
      el("td", {}, [badge(item.configured ? "ready" : "planned", item.configured ? "已配置" : "未配置"), el("span", { text: item.flow_configured ? "Flow 已配置" : "Flow 未配置" })]),
      el("td", { text: (item.course_ids || []).join("、") || "-" }),
      el("td", { text: item.recent_contract_test?.status || "未运行" }),
      el("td", {}, el("div", { class: "table-actions" }, [detail, validate])),
    ]));
  });
  table.append(body);
  $("#admin-agent-table").replaceChildren(table);
}

async function loadAdminAgents() {
  const data = await api("/api/v1/agents");
  renderAdminAgents(data.agents || []);
}

function serviceCard(label, value, note, status = "ready") {
  return el("article", { class: "admin-service-card" }, [badge(status, value), el("strong", { text: label }), el("span", { text: value }), el("p", { text: note })]);
}

async function loadAdminSystem() {
  $("#admin-system-notice").replaceChildren();
  const results = await Promise.allSettled([
    api("/api/v1/health"),
    api("/api/v1/debug/rag/status"),
    api("/api/v1/agents"),
  ]);
  const health = results[0].status === "fulfilled" ? results[0].value : {};
  const rag = results[1].status === "fulfilled" ? results[1].value : {};
  const agents = results[2].status === "fulfilled" ? results[2].value : {};
  const failures = results.filter((item) => item.status === "rejected").length;
  if (failures) $("#admin-system-notice").replaceChildren(el("div", { class: "notice warning", text: `部分状态暂时无法读取（${failures}/3）` }));
  const registry = agents.agents || [];
  $("#admin-system-metrics").replaceChildren(metric("API", health.status === "ok" ? "正常" : "异常", health.status === "ok" ? "ready" : "failed"), metric("数据库", health.database || "未知", health.database === "ok" ? "ready" : "failed"), metric("Provider", rag.provider || health.active_provider || "未知", rag.provider_available ? "ready" : "planned"), metric("RAG", rag.rag_enabled ? "已启用" : "未启用", rag.rag_enabled ? "ready" : "planned"), metric("Agent", String(registry.length), registry.length ? "ready" : "unknown"));
  $("#admin-system-services").replaceChildren(
    serviceCard("API 服务", health.version || "当前服务", health.status === "ok" ? "可正常响应管理请求" : "请检查服务日志", health.status === "ok" ? "ready" : "failed"),
    serviceCard("数据库", health.database || "未知", "登录、账号、任务和审计数据依赖", health.database === "ok" ? "ready" : "failed"),
    serviceCard("RAG 检索", rag.rag_enabled ? "已启用" : "未启用", "状态查询不会触发模型预热", rag.rag_enabled ? "ready" : "planned"),
    serviceCard("模型 Provider", rag.provider || health.active_provider || "按请求检查", rag.provider_available ? "当前可用" : "未配置或不可用", rag.provider_available ? "ready" : "planned"),
  );
}

async function updateFeatureSetting(item, toggle) {
  const enabled = toggle.getAttribute("aria-pressed") !== "true";
  toggle.disabled = true;
  try {
    await api(`/api/v1/admin/settings/features/${encodeURIComponent(item.key)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    toast(`${item.label}已${enabled ? "开启" : "关闭"}`);
    await loadAdminFeatureSettings();
  } catch (error) {
    toast(error.message, "failed");
  } finally {
    if (toggle.isConnected) toggle.disabled = false;
  }
}

function renderFeatureSettings(items) {
  const root = $("#admin-feature-settings");
  if (!items.length) {
    root.replaceChildren(el("p", { class: "empty-state", text: "暂无可配置功能" }));
    return;
  }
  root.replaceChildren(...items.map((item) => {
    const enabled = Boolean(item.enabled);
    const toggle = el("button", {
      type: "button",
      class: "feature-toggle-button",
      "data-feature-key": item.key,
      "aria-pressed": String(enabled),
      "aria-label": `切换${item.label}，当前${enabled ? "已开启" : "已关闭"}`,
      text: enabled ? "已开启" : "已关闭",
    });
    toggle.addEventListener("click", () => updateFeatureSetting(item, toggle));
    return el("article", { class: "admin-service-card" }, [
      el("strong", { text: item.label }),
      el("p", { text: item.description }),
      el("div", { class: "feature-toggle" }, [toggle, el("span", { text: enabled ? "允许使用" : "暂不使用" })]),
      el("small", { text: item.updated_at ? `最近更新：${dateText(item.updated_at)}` : "当前使用默认配置：开启" }),
    ]);
  }));
}

async function loadAdminFeatureSettings() {
  const items = await api("/api/v1/admin/settings/features");
  renderFeatureSettings(items || []);
}

function selectManagementModule(id) {
  const target = managementModules.has(id) ? id : "overview";
  all("[data-admin-module]").forEach((section) => { section.hidden = section.dataset.adminModule !== target; });
  all("[data-admin-module-target]").forEach((button) => { button.classList.toggle("active", button.dataset.adminModuleTarget === target); });
  if (!loadedManagementModules.has(target)) {
    loadedManagementModules.add(target);
    const loader = managementModules.get(target);
    if (loader) loader().catch((error) => toast(error.message, "failed"));
  }
}

function initManagementModules() {
  registerManagementModule("overview", async () => {});
  registerManagementModule("tasks", loadAdminTasks);
  registerManagementModule("files", loadAdminFiles);
  registerManagementModule("agents", loadAdminAgents);
  registerManagementModule("settings", loadAdminFeatureSettings);
  registerManagementModule("system", loadAdminSystem);
  all("[data-admin-module-target]").forEach((button) => button.addEventListener("click", () => selectManagementModule(button.dataset.adminModuleTarget)));
  $("#admin-task-filters").addEventListener("submit", (event) => { event.preventDefault(); loadAdminTasks().catch((error) => toast(error.message, "failed")); });
  $("#admin-file-filters").addEventListener("submit", (event) => { event.preventDefault(); loadAdminFiles().catch((error) => toast(error.message, "failed")); });
  $("#admin-file-refresh").addEventListener("click", () => loadAdminFiles().catch((error) => toast(error.message, "failed")));
  $("#admin-agent-refresh").addEventListener("click", () => loadAdminAgents().catch((error) => toast(error.message, "failed")));
  $("#admin-settings-refresh").addEventListener("click", () => loadAdminFeatureSettings().catch((error) => toast(error.message, "failed")));
  $("#admin-system-refresh").addEventListener("click", () => loadAdminSystem().catch((error) => toast(error.message, "failed")));
  selectManagementModule("overview");
}

async function createAccount(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    await api("/api/v1/admin/accounts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
    $("#account-dialog").close();
    form.reset();
    toast("账号已创建");
    await loadDashboard();
  } catch (error) { $("#account-form-error").textContent = error.message; }
}

async function login(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());
  $("#admin-login-error").textContent = "登录中…";
  try {
    await api("/api/v1/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
    await bootstrap();
  } catch (error) { $("#admin-login-error").textContent = error.message; }
}

async function bootstrap() {
  try {
    currentPrincipal = await api("/api/v1/auth/me");
    if (currentPrincipal.role !== "admin") { showLogin("当前账号没有管理员权限"); return; }
    $("#admin-identity").textContent = `${currentPrincipal.display_name} · 管理员`;
    showApp();
    await loadDashboard();
  } catch (error) {
    showLogin(error.status === 403 ? "当前账号没有管理员权限" : "请先登录管理员账号");
  }
}

window.addEventListener("DOMContentLoaded", () => {
  initShell({ page: "admin", title: "管理总览", description: "账号、会话与审计控制台" });
  initTabs();
  $("#admin-login-form").addEventListener("submit", login);
  $("#account-form").addEventListener("submit", (event) => { if (event.submitter?.value === "create") createAccount(event); });
  $("#account-filters").addEventListener("submit", (event) => { event.preventDefault(); loadAccounts().catch((error) => toast(error.message, "failed")); });
  $("#open-create-account").addEventListener("click", () => { $("#account-form-error").textContent = ""; $("#account-dialog").showModal(); });
  $("#admin-refresh").addEventListener("click", () => loadDashboard());
  initManagementModules();
  $("#admin-logout").addEventListener("click", async () => { await api("/api/v1/auth/logout", { method: "POST" }).catch(() => {}); currentPrincipal = null; showLogin("已退出登录"); });
  bootstrap();
});
