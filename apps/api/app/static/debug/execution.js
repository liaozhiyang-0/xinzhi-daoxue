const { $, all, api, el, initShell, renderJson, renderMarkdown, toast } = XinzhiUI;
let execution = null;

function section(title, description, content) { return el("section", { class: "debug-section" }, [el("h2", { text: title }), el("p", { text: description }), content]); }
function jsonSurface(title, value) { const pre = el("pre", { class: "code-view" }); renderJson(pre, value); return el("article", { class: "debug-surface" }, [el("h3", { text: title }), pre]); }
function kvSurface(title, rows) { const dl = el("dl", { class: "kv-list" }); rows.forEach(([key, value]) => dl.append(el("div", { class: "kv-row" }, [el("dt", { text: key }), el("dd", { text: Array.isArray(value) ? value.join("、") || "—" : value ?? "—" })]))); return el("article", { class: "debug-surface" }, [el("h3", { text: title }), dl]); }
function summaryCell(label, value) { return el("div", { class: "summary-cell" }, [el("span", { text: label }), el("strong", { text: value ?? "—" })]); }

function renderSummary(data) {
  const overview = data.overview || {}; const retrieval = data.retrieval || {}; const workflow = data.workflow || {};
  $("#execution-summary").replaceChildren(summaryCell("任务", overview.title || data.task.id), summaryCell("状态", overview.status_label || data.task.status), summaryCell("证据", `${retrieval.used_evidence_ids?.length || 0} / ${retrieval.final_evidence?.length || 0}`), summaryCell("执行方式", overview.provider_label || workflow.provider), summaryCell("总耗时", `${data.performance?.total_ms || 0} ms`));
}

function renderOverview(data) {
  const o = data.overview || {}; const r = data.retrieval || {}; const f = data.final || {};
  const steps = el("div", { class: "debug-surface" }, [el("h3", { text: "任务全貌" })]);
  (o.execution_steps || []).forEach((step, index) => steps.append(el("div", { class: "timeline-item" }, [el("span", { class: "timeline-index", text: index + 1 }), el("div", {}, [el("strong", { text: step.label }), el("p", { text: step.status })])])));
  $("#overview-panel").replaceChildren(section("任务概览", "面向演示与排障的统一任务摘要。", el("div", { class: "debug-grid" }, [kvSurface("结果边界", [["任务 ID", data.task.id], ["课程 / 意图", `${data.task.course_id} / ${data.task.intent}`], ["证据状态", r.evidence_status], ["RAG 模式", r.rag_mode], ["降级", f.fallback_used ? f.fallback_reason || "是" : "否"]]), steps])));
}

function renderRoute(data) { $("#route-panel").replaceChildren(section("为什么选择这个工作流", "展示脱敏后的原始输入、材料提取、候选评分和最终 RouteDecision。", el("div", { class: "debug-grid" }, [jsonSurface("材料提取", data.request?.materials || {}), jsonSurface("候选与选择", data.route), jsonSurface("ExecutionPlan", data.execution_plan), jsonSurface("重路由边界", data.reroute || {})]))); }

function renderRetrieval(data) {
  const r = data.retrieval || {}; const flow = el("div", { class: "evidence-flow" });
  (r.final_evidence || []).forEach((item) => flow.append(el("div", { class: "flow-row" }, [el("strong", { text: item.evidence_id }), el("span", { text: item.title }), el("span", { class: `flow-state ${item.entered_workflow ? "yes" : ""}`, text: item.entered_workflow ? "进入工作流" : "未进入工作流" }), el("span", { class: `flow-state ${item.used_by_answer ? "yes" : ""}`, text: item.used_by_answer ? "实际引用" : item.role === "method_reference" ? "方法参考" : "未引用" })])));
  if (!flow.childElementCount) flow.append(el("div", { class: "empty-state", text: "本次任务没有最终证据。" }));
  $("#retrieval-panel").replaceChildren(section("证据流转对照", "区分原始候选、进入工作流的证据与最终实际引用。", flow), section("候选与策略", "技术候选仅在高级调试中展示。", el("div", { class: "debug-grid" }, [kvSurface("RetrievalPolicy", [["策略", r.policy], ["交互模式", r.rag_mode], ["RAG 状态", r.status], ["证据状态", r.evidence_status]]), jsonSurface("候选 Trace", r.candidate_trace)])));
}

function renderWorkflow(data) { const w = data.workflow || {}; $("#workflow-panel").replaceChildren(section("工作流调用", "只显示脱敏后的执行边界，不返回 Authorization、Secret 或完整 Flow ID。", el("div", { class: "debug-grid" }, [kvSurface("调用状态", [["Provider", w.provider], ["云端状态", w.cloud_status], ["request_id", w.request_id], ["响应状态", w.response_status], ["Parser", w.parser_status], ["Mock", w.mock ? "开发态 Mock" : "否"]]), jsonSurface("输入映射契约", w.input_mapping || []), jsonSurface("规范化输出", w.output || {}), jsonSurface("事件序列", data.events || [])]))); }

function renderCitation(data) { const answer = el("div", { class: "answer-preview markdown-view" }); renderMarkdown(answer, data.final?.answer || ""); $("#citation-panel").replaceChildren(section("结果校验", "按工作流类型分别执行确定性校验；引用校验仅用于 grounded generation。", el("div", { class: "debug-grid" }, [jsonSurface("AgentResultValidator", data.validation), jsonSurface("CitationValidator", data.citation), jsonSurface("最终边界", { citations: data.final?.citations, warnings: data.final?.warnings, fallback_used: data.final?.fallback_used, fallback_reason: data.final?.fallback_reason })])), section("最终回答", "调试预览与学生端使用同一安全 Markdown 渲染器。", answer)); }

function renderPerformance(data) { const perf = data.performance || {}; const context = perf.context || {}; const max = Math.max(1, ...(perf.waterfall || []).map((item) => Number(item.duration_ms) || 0)); const chart = el("div", { class: "waterfall" }); (perf.waterfall || []).forEach((item) => chart.append(el("div", { class: "waterfall-row" }, [el("span", { text: item.label }), el("div", { class: "waterfall-track" }, el("div", { class: "waterfall-bar", style: `width:${Math.max(1, (Number(item.duration_ms) || 0) / max * 100)}%` })), el("strong", { text: `${item.duration_ms || 0} ms` })]))); const budget = el("p", { text: `上下文估算 ${context.estimated_tokens || 0} / ${context.budget_tokens || 0} token；消息 ${context.message_count || 0}；缓存 ${context.cache_hit ? "命中" : "未命中"}（${context.cache_backend || "none"}）` }); $("#performance-panel").replaceChildren(section("执行时间与上下文预算", `总耗时 ${perf.total_ms || 0} ms；token 为保守估算值。`, el("div", {}, [budget, chart]))); }

function renderAll(data) { execution = data; renderSummary(data); renderOverview(data); renderRoute(data); renderRetrieval(data); renderWorkflow(data); renderCitation(data); renderPerformance(data); $("#execution-console").hidden = false; }

async function loadMetrics() {
  try {
    const data = await api("/api/v1/debug/execution/metrics/summary?limit=100");
    const slowest = (data.slowest_runs || []).slice(0, 5).map((item) => ({ task_id: item.task_id, latency_ms: item.latency_ms, agent_id: item.agent_id, status: item.status }));
    $("#execution-metrics").replaceChildren(
      el("h2", { text: "最近执行概览" }),
      el("div", { class: "execution-summary" }, [summaryCell("执行数", data.count), summaryCell("Provider 调用", data.provider_call_count), summaryCell("Token", `${data.input_tokens || 0} / ${data.output_tokens || 0}`), summaryCell("降级", data.fallback_count), summaryCell("检索成功率", data.retrieval_success_rate == null ? "无样本" : `${(data.retrieval_success_rate * 100).toFixed(1)}%`)]),
      el("div", { class: "debug-grid" }, [jsonSurface("分布与失败原因", data.distributions || {}), jsonSurface("慢任务排序", slowest)]),
    );
  } catch (error) { $("#execution-metrics").replaceChildren(el("h2", { text: "最近执行概览" }), el("p", { text: `指标暂不可用：${error.message}` })); }
}

async function loadExecution() {
  const id = $("#task-id").value.trim(); if (!id) { $("#execution-notice").replaceChildren(el("div", { class: "notice warning", text: "请先输入一个真实任务 ID。" })); return; }
  $("#load-execution").disabled = true; $("#execution-notice").replaceChildren(el("div", { class: "loading-state", text: "正在载入统一执行链…" }));
  try { const data = await api(`/api/v1/debug/execution/${encodeURIComponent(id)}`); renderAll(data); $("#execution-notice").replaceChildren(); localStorage.setItem("xinzhi_last_task", id); }
  catch (error) { $("#execution-notice").replaceChildren(el("div", { class: "error-state", text: error.message })); }
  finally { $("#load-execution").disabled = false; }
}

window.addEventListener("DOMContentLoaded", () => {
  initShell({ page: "execution", title: "执行调试", description: "路由、RAG、工作流、引用与性能" });
  loadMetrics();
  const query = new URLSearchParams(location.search); $("#task-id").value = query.get("task_id") || localStorage.getItem("xinzhi_last_task") || "";
  all("[data-tab-target]").forEach((button) => button.addEventListener("click", () => { all("[data-tab-target]").forEach((item) => item.classList.toggle("active", item === button)); all("[data-tab-panel]").forEach((panel) => { panel.hidden = panel.dataset.tabPanel !== button.dataset.tabTarget; }); }));
  $("#load-execution").addEventListener("click", loadExecution); $("#task-id").addEventListener("keydown", (event) => { if (event.key === "Enter") loadExecution(); });
  if (location.pathname === "/debug/rag") document.querySelector('[data-tab-target="retrieval"]').click();
  if ($("#task-id").value) loadExecution();
});
