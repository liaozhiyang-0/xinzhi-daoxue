const { $, api, badge, el, initShell } = XinzhiUI;

function metric(title, value, note, status = "ready") {
  return el("article", { class: "metric-card" }, [badge(status), el("strong", { text: value }), el("span", { text: title }), el("small", { text: note })]);
}

function getCount(data, ...keys) {
  for (const key of keys) if (Number.isFinite(Number(data?.[key]))) return Number(data[key]);
  return "—";
}

async function loadStatus(force = false) {
  $("#status-notice").replaceChildren();
  $("#service-grid").replaceChildren(el("div", { class: "loading-state", text: "正在读取轻量状态…" }));
  const ttl = force ? 0 : 10000;
  const [healthResult, ragResult, agentResult] = await Promise.allSettled([
    api("/api/v1/health", {}, ttl), api("/api/v1/debug/rag/status", {}, ttl), api("/api/v1/agents", {}, ttl),
  ]);
  const health = healthResult.status === "fulfilled" ? healthResult.value : {};
  const rag = ragResult.status === "fulfilled" ? ragResult.value : {};
  const agents = agentResult.status === "fulfilled" ? agentResult.value : {};
  const failures = [healthResult, ragResult, agentResult].filter((item) => item.status === "rejected");
  if (failures.length) $("#status-notice").append(el("div", { class: "notice warning", text: `部分状态无法获取（${failures.length}/3）；页面其余区域仍可使用。` }));
  const registry = agents.agents || [];
  const provider = rag.provider || rag.provider_status || {};
  const models = rag.models || rag.model_status || {};
  $("#service-grid").replaceChildren(
    metric("FastAPI", health.status === "ok" ? "可用" : "无法确认", health.version || "统一任务 API", health.status === "ok" ? "ready" : "failed"),
    metric("Xingchen Provider", provider.status || rag.cloud_status || "按请求检查", "不会在页面加载时调用云端", provider.status || "unknown"),
    metric("Qdrant", rag.qdrant?.status || rag.vector_store?.status || "按需检查", "本地向量存储", rag.qdrant?.status || rag.vector_store?.status || "unknown"),
    metric("LEARN", registry.some((item) => item.agent_id?.includes("LEARN") && item.configured) ? "已配置" : "未配置", "知识问答工作流", registry.some((item) => item.agent_id?.includes("LEARN") && item.configured) ? "ready" : "not_configured"),
    metric("SOLVER_CT", registry.some((item) => item.agent_id?.includes("SOLVER_CT") && item.configured) ? "已配置" : "未配置", "电路理论解题工作流", registry.some((item) => item.agent_id?.includes("SOLVER_CT") && item.configured) ? "ready" : "not_configured"),
    metric("本地模型", models.loaded ? "已加载" : "按需加载", "页面加载不会触发 Embedding 或 Reranker", models.loaded ? "ready" : "planned"),
  );
  $("#data-grid").replaceChildren(
    metric("文本 Points", String(getCount(rag, "text_points", "text_count")), "当前索引统计"),
    metric("图片 Points", String(getCount(rag, "image_points", "image_count")), "当前索引统计"),
    metric("已注册 Agent", String(registry.length), "配置驱动注册表"),
    metric("已发布 Agent", String(registry.filter((item) => item.lifecycle_status === "published" || item.published).length), "可进入正式路由"),
    metric("开发中 Agent", String(registry.filter((item) => item.lifecycle_status === "planned" || item.mock_ready).length), "仅 Debug 中可见", "planned"),
    metric("索引版本", rag.index_version || "未报告", "索引变化时缓存自动失效", rag.index_version ? "ready" : "unknown"),
  );
  $("#runtime-note").textContent = failures.length ? "状态数据不完整；请先检查 FastAPI 与本地依赖，再按需进入调试页。" : "轻量状态读取完成。大型模型保持懒加载，云端调用保持未触发。";
}

window.addEventListener("DOMContentLoaded", () => {
  initShell({ page: "system", title: "系统状态", description: "轻量健康检查与运行概览" });
  $("#refresh-status").addEventListener("click", () => loadStatus(true));
  loadStatus();
});
