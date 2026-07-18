const { $, all, api, badge, el, initShell, initTabs, renderJson, toast } = XinzhiUI;
const state = { agents: [], actionsEnabled: false, mocksEnabled: false, selected: "" };
function requestPayload(allowMock = false) { return { question: $("#agent-question").value, course_id: $("#agent-course").value, intent: $("#agent-intent").value, allow_mock: allowMock, canonical_input: {}, options: {} }; }
function statusOf(agent) {
  if (!agent.configured) return "not_configured";
  if (agent.mock_ready && agent.lifecycle_status !== "published") return "mock";
  return agent.lifecycle_status === "published" ? "ready" : agent.lifecycle_status || "planned";
}
function matches(agent, filter) { return filter === "all" || (filter === "published" && agent.lifecycle_status === "published") || (filter === "planned" && agent.lifecycle_status === "planned") || (filter === "mock" && agent.mock_ready) || (filter === "not_configured" && !agent.configured); }
function renderRows() {
  const filter = $("#agent-filter").value; const agents = state.agents.filter((item) => matches(item, filter));
  $("#agent-grid").replaceChildren(...(agents.length ? agents.map((item) => {
    const row = el("tr", { tabindex: "0", "data-agent": item.agent_id });
    row.append(el("td", {}, [el("strong", { text: item.display_name || item.agent_id }), el("small", { class: "table-subtitle", text: item.agent_id })]), el("td", {}, badge(statusOf(item))), el("td", { text: item.provider_type || item.provider || "—" }), el("td", {}, badge(item.configured ? "configured" : "not_configured")), el("td", { text: (item.courses || item.supported_courses || []).join(", ") || "—" }), el("td", { text: item.retrieval_policy || "no_rag" }), el("td", { text: item.recent_contract_test?.status || "未运行" }));
    row.addEventListener("click", () => selectAgent(item.agent_id)); row.addEventListener("keydown", (event) => { if (event.key === "Enter") selectAgent(item.agent_id); }); return row;
  }) : [el("tr", {}, el("td", { colspan: "7", class: "empty-state", text: "没有符合条件的 Agent。" }))]));
}
async function selectAgent(id) { state.selected = id; $("#agent-select").value = id; await loadDefinition(); all("[data-agent]").forEach((row) => row.classList.toggle("selected", row.dataset.agent === id)); }
async function loadAgents() {
  try {
    const data = await api("/api/v1/agents", {}, 5000); state.agents = data.agents || []; state.actionsEnabled = Boolean(data.debug_actions_enabled); state.mocksEnabled = Boolean(data.mock_actions_enabled);
    const env = badge(state.actionsEnabled ? (state.mocksEnabled ? "mock" : "ready") : "disabled", state.actionsEnabled ? (state.mocksEnabled ? "Debug · Mock 可用" : "Debug · Mock 关闭") : "只读模式"); env.id = "environment-badge"; $("#environment-badge").replaceWith(env);
    $("#agent-select").replaceChildren(...state.agents.map((item) => el("option", { value: item.agent_id, text: item.display_name || item.agent_id })));
    all("[data-action]").forEach((button) => { button.disabled = !state.actionsEnabled || (button.dataset.action === "mock" && !state.mocksEnabled); });
    renderRows(); if (state.agents.length) await selectAgent(state.selected || state.agents[0].agent_id);
  } catch (error) { $("#agent-grid").replaceChildren(el("tr", {}, el("td", { colspan: "7", class: "field-error", text: `${error.message}。请检查本地 API。` }))); }
}
function summaryNode(data) {
  const capabilities = data.capabilities || {};
  return el("div", { class: "definition-cards" }, [
    el("article", { class: "metric-card" }, [badge(data.enabled ? "ready" : "disabled"), el("strong", { text: data.display_name || data.agent_id }), el("small", { text: data.agent_id || "" })]),
    el("article", { class: "metric-card" }, [badge(data.configured ? "configured" : "not_configured"), el("strong", { text: data.provider?.type || data.provider_type || "Provider" }), el("small", { text: `Parser: ${data.provider?.parser_type || data.parser_type || "—"}` })]),
    el("article", { class: "metric-card" }, [badge(data.lifecycle_status || data.publication_status || "planned"), el("strong", { text: (capabilities.courses || data.courses || []).join(", ") || "未声明课程" }), el("small", { text: (capabilities.intents || data.intents || []).join(", ") || "未声明意图" })]),
  ]);
}
async function loadDefinition() {
  const id = $("#agent-select").value; if (!id) return;
  try {
    const data = await api(`/api/v1/agents/${encodeURIComponent(id)}`); renderJson($("#definition-json"), data); $("#definition-summary").replaceChildren(summaryNode(data));
    const retrieval = data.retrieval_policy || data.retrieval || {}; const fallback = data.fallback || {};
    $("#strategy-summary").replaceChildren(el("div", { class: "definition-cards" }, [el("article", { class: "metric-card" }, [el("strong", { text: retrieval.policy_name || retrieval.name || String(retrieval) || "no_rag" }), el("span", { text: "RetrievalPolicy" })]), el("article", { class: "metric-card" }, [el("strong", { text: fallback.type || "no_fallback" }), el("span", { text: "Fallback" })])]));
  } catch (error) { renderJson($("#definition-json"), { error: error.message }); $("#definition-summary").textContent = error.message; }
}
async function action(name) {
  const id = $("#agent-select").value; const paths = { validate: `/api/v1/debug/agents/${id}/validate`, "dry-run": `/api/v1/agents/${id}/dry-run`, mock: `/api/v1/debug/agents/${id}/mock`, contracts: `/api/v1/debug/agents/${id}/contract-tests` };
  const body = name === "validate" || name === "contracts" ? undefined : JSON.stringify(requestPayload(name === "mock")); $("#agent-error").textContent = "";
  try { const result = await api(paths[name], { method: "POST", headers: { "Content-Type": "application/json" }, body }); renderJson($("#action-json"), result); const resultBadge = badge(result.mock_used ? "mock" : result.status || (result.valid ? "success" : "completed")); resultBadge.id = "result-badge"; $("#result-badge").replaceWith(resultBadge); toast(name === "mock" ? "Mock 运行完成，结果已明确标记" : "调试动作已完成"); if (["validate", "contracts"].includes(name)) await loadAgents(); }
  catch (error) { $("#agent-error").textContent = `${error.message}。请检查配置与输入后重试。`; renderJson($("#action-json"), { error: error.message }); }
}
async function compare() {
  const id = $("#agent-select").value; let sample = null; $("#agent-error").textContent = "";
  try { sample = $("#cloud-sample").value.trim() ? JSON.parse($("#cloud-sample").value) : null; } catch { $("#agent-error").textContent = "Cloud 样例不是合法 JSON"; return; }
  if ($("#allow-cloud").checked && !window.confirm("真实云端调用可能消耗额度，预计等待约 20 秒。确认继续？")) return;
  try { const result = await api(`/api/v1/debug/agents/${id}/compare`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...requestPayload(true), cloud_sample: sample, allow_cloud: $("#allow-cloud").checked }) }); renderJson($("#action-json"), result); toast("结构比较完成"); }
  catch (error) { $("#agent-error").textContent = error.message; }
}
window.addEventListener("DOMContentLoaded", () => {
  initShell({ page: "agents", title: "Agent 管理", description: "工作流注册与契约控制台" }); initTabs();
  $("#agent-filter").addEventListener("change", renderRows); $("#agent-select").addEventListener("change", () => selectAgent($("#agent-select").value));
  all("[data-action]").forEach((button) => button.addEventListener("click", () => action(button.dataset.action))); $("#compare-button").addEventListener("click", compare); loadAgents();
});
