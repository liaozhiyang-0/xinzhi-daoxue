const { $, api, badge, el, initShell } = XinzhiUI;

function metric(title, value, note, status = "ready") {
  return el("article", { class: "metric-card" }, [badge(status), el("strong", { text: value }), el("span", { text: title }), el("p", { text: note })]);
}

function countValue(data, ...keys) {
  for (const key of keys) if (Number.isFinite(Number(data?.[key]))) return Number(data[key]);
  return 0;
}

function renderBars(target, rows) {
  const total = Math.max(1, ...rows.map((item) => item.value));
  $(target).replaceChildren(...rows.map((item) => el("div", { class: "system-bar-row" }, [
    el("div", { class: "system-bar-heading" }, [el("span", { text: item.label }), badge(item.status, item.statusLabel)]),
    el("div", { class: "system-bar-track" }, el("div", { class: "system-bar-fill", style: `width:${Math.max(5, item.value / total * 100)}%` })),
    el("p", { text: item.note }),
  ])));
}

function renderHealthChart(health, rag) {
  const providerReady = Boolean(rag.provider_available || rag.provider_status === "ready");
  const ragReady = Boolean(rag.rag_enabled);
  renderBars("#runtime-health-chart", [
    { label: "FastAPI", value: health.status === "ok" ? 100 : 20, status: health.status === "ok" ? "ready" : "failed", statusLabel: health.status === "ok" ? "正常" : "异常", note: health.version || "统一 API 服务" },
    { label: "模型 Provider", value: providerReady ? 100 : 35, status: providerReady ? "ready" : "planned", statusLabel: providerReady ? "可用" : "待配置", note: rag.provider || "按请求检查" },
    { label: "本地 RAG", value: ragReady ? 100 : 25, status: ragReady ? "ready" : "planned", statusLabel: ragReady ? "启用" : "未启用", note: "文本、图片与引用检索" },
  ]);
}

function renderAgentChart(items) {
  const configured = items.filter((item) => item.configured).length;
  const published = items.filter((item) => item.lifecycle_status === "published" || item.published).length;
  const planned = items.filter((item) => item.lifecycle_status === "planned" || item.mock_ready).length;
  renderBars("#agent-lifecycle-chart", [
    { label: "已注册", value: items.length, status: items.length ? "ready" : "unknown", statusLabel: `${items.length} 个`, note: "当前 Agent 注册表" },
    { label: "已配置", value: configured, status: configured ? "ready" : "planned", statusLabel: `${configured} 个`, note: "具备完整运行配置" },
    { label: "已发布", value: published, status: published ? "success" : "planned", statusLabel: `${published} 个`, note: "允许进入正式路由" },
    { label: "开发中", value: planned, status: planned ? "planned" : "ready", statusLabel: `${planned} 个`, note: "仅用于开发验证或 Mock" },
  ]);
}

async function loadStatus(force = false) {
  $("#status-notice").replaceChildren();
  $("#service-grid").replaceChildren(el("div", { class: "loading-state", text: "正在读取运行状态…" }));
  const ttl = force ? 0 : 10000;
  const [healthResult, ragResult, agentResult] = await Promise.allSettled([
    api("/api/v1/health", {}, ttl),
    api("/api/v1/debug/rag/status", {}, ttl),
    api("/api/v1/agents", {}, ttl),
  ]);
  const health = healthResult.status === "fulfilled" ? healthResult.value : {};
  const rag = ragResult.status === "fulfilled" ? ragResult.value : {};
  const agents = agentResult.status === "fulfilled" ? agentResult.value : {};
  const registry = agents.agents || [];
  const failures = [healthResult, ragResult, agentResult].filter((item) => item.status === "rejected");
  if (failures.length) $("#status-notice").append(el("div", { class: "notice warning", text: `部分状态暂时无法获取（${failures.length}/3），其余区域仍可使用。` }));

  $("#service-grid").replaceChildren(
    metric("FastAPI", health.status === "ok" ? "可用" : "无法确认", health.version || "统一任务 API", health.status === "ok" ? "ready" : "failed"),
    metric("模型 Provider", rag.provider || "按请求检查", rag.provider_available ? "当前可用" : "未配置时保持本地运行", rag.provider_available ? "ready" : "planned"),
    metric("本地 RAG", rag.rag_enabled ? "已启用" : "未启用", "知识检索与引用校验", rag.rag_enabled ? "ready" : "planned"),
    metric("Agent 注册", String(registry.length), "配置驱动的工作流注册表", registry.length ? "ready" : "unknown"),
  );
  $("#data-grid").replaceChildren(
    metric("文本 Points", String(countValue(rag, "text_points", "text_count")), "当前文本索引统计"),
    metric("图片 Points", String(countValue(rag, "image_points", "image_count")), "当前图片索引统计"),
    metric("已配置 Agent", String(registry.filter((item) => item.configured).length), "具备完整运行配置"),
    metric("已发布 Agent", String(registry.filter((item) => item.lifecycle_status === "published" || item.published).length), "可进入正式路由"),
  );
  renderHealthChart(health, rag);
  renderAgentChart(registry);
  $("#runtime-note").textContent = failures.length ? "状态数据不完整，请先检查 FastAPI 与本地依赖，再按需进入调试页面。" : "轻量状态读取完成。大型模型保持按需加载，云端调用未被此页面触发。";
}

window.addEventListener("DOMContentLoaded", () => {
  initShell({ page: "system", title: "系统状态", description: "服务健康、知识库与 Agent 运行概览" });
  $("#refresh-status").addEventListener("click", () => loadStatus(true));
  loadStatus();
});
