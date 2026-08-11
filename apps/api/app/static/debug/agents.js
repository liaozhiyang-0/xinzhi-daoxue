const { $, all, api, badge, el, initShell, initTabs, renderJson, toast } = XinzhiUI;
const state = { agents: [], runtimeCapabilities: [], actionsEnabled: false, mocksEnabled: false, selected: "" };
const runtimeReadinessLabels = { blocked: "已阻塞", default_ready: "默认就绪", canary_ready: "Canary 就绪", shadow_ready: "Shadow 就绪", runtime_implemented: "已实现", explicit_goal_only: "仅显式 Goal", legacy_only: "仅 Legacy" };
function runtimeReadinessTone(status) { return status === "blocked" ? "failed" : ["default_ready", "canary_ready", "shadow_ready", "runtime_implemented"].includes(status) ? "ready" : status === "explicit_goal_only" ? "partial" : "planned"; }
function runtimeReadinessBadge(readiness = {}) { const status = readiness.status || "unknown"; return badge(runtimeReadinessTone(status), runtimeReadinessLabels[status] || "未报告"); }
function readinessTextItems(value) {
  const values = Array.isArray(value) ? value : value == null ? [] : [value];
  return values.map((item) => {
    if (typeof item === "string") return item.trim();
    if (!item || typeof item !== "object") return "";
    return [item.message, item.text, item.description, item.label].find((candidate) => typeof candidate === "string" && candidate.trim())?.trim() || "";
  }).filter(Boolean);
}
function safeRuntimeReadinessText(value, fallback = "未提供") {
  if (typeof value !== "string" && typeof value !== "number") return fallback;
  const text = String(value).trim().replace(/[\u0000-\u001f\u007f]/g, "");
  if (!text || text.length > 160 || /(?:secret|token|password|credential|api[_-]?key|bearer|sk-[a-z0-9]|(?:[a-z]:\\|\\\\|\/))\S*/i.test(text)) return fallback;
  return text;
}
function safeRuntimeReadinessItems(value) {
  return readinessTextItems(value).map((item) => safeRuntimeReadinessText(item, "")).filter(Boolean);
}
const semanticEvidenceReasons = new Set([
  "semantic_evidence_missing",
  "semantic_decision_not_pass",
  "semantic_evidence_identity_mismatch",
  "semantic_evidence_suite_id_mismatch",
  "semantic_evidence_case_id_mismatch",
  "semantic_evidence_agent_version_mismatch",
  "semantic_evidence_runtime_plan_version_mismatch",
]);
function runtimePublicationEvidence(readiness = {}) {
  const blockers = safeRuntimeReadinessItems(readiness.blockers);
  const reason = safeRuntimeReadinessText(readiness.canary_reason, "");
  const reasons = [reason, ...blockers].filter(Boolean);
  const semanticBlocked = reasons.some((item) => semanticEvidenceReasons.has(item) || item.startsWith("semantic_"));
  const structuralReported = typeof readiness.structural_release_eligible === "boolean";
  const semanticReported = typeof readiness.semantic_release_eligible === "boolean" || typeof readiness.semantic_evidence_eligible === "boolean";
  const structuralReady = structuralReported
    ? readiness.structural_release_eligible === true
    : readiness.canary_release_eligible === true || semanticBlocked;
  const explicitSemanticReady = semanticReported
    ? readiness.semantic_release_eligible === true || readiness.semantic_evidence_eligible === true
    : readiness.canary_release_eligible === true;
  const semanticReady = explicitSemanticReady && !semanticBlocked;
  return {
    blockers,
    reason,
    structuralReady,
    semanticReady,
    semanticBlocked,
    structuralLabel: structuralReady ? "结构证据已就绪" : "结构证据未就绪",
    semanticLabel: semanticReady ? "语义证据已就绪" : "语义证据未就绪",
  };
}
function runtimePublicationEvidenceSummary(readiness = {}) {
  const evidence = runtimePublicationEvidence(readiness);
  return evidence.structuralReady && evidence.semanticReady ? "发布证据已就绪" : "发布证据未就绪";
}
function runtimeReadinessActionHints(readiness, status) {
  const backendActions = readinessTextItems(readiness.recommended_actions ?? readiness.next_actions ?? readiness.next_action);
  const statusHint = {
    blocked: "当前 Runtime 被阻塞；请先处理下方原因，页面不会自动执行任何操作。",
    canary_ready: "当前已具备 Canary 条件，可按受控发布流程继续；页面不会自动执行发布。",
    default_ready: "当前已具备默认 Runtime 条件，可按既有发布流程使用；页面不会自动执行变更。",
  }[status];
  return statusHint ? [statusHint, ...backendActions] : backendActions;
}
function runtimeReadinessNextSteps(readiness, blockers) {
  const status = readiness.status || "unknown";
  const actions = runtimeReadinessActionHints(readiness, status);
  const actionList = actions.length
    ? el("ul", { class: "runtime-readiness-action-list" }, actions.map((item) => el("li", { text: item })))
    : el("p", { class: "runtime-readiness-note", text: "后端未提供下一步建议。" });
  const blocked = status === "blocked";
  const blockerList = blockers.length
    ? el("ul", { class: "runtime-readiness-blocker-list" }, blockers.map((item) => el("li", { text: item })))
    : el("p", { class: "runtime-readiness-note", text: blocked ? "Runtime 报告为阻塞，但未提供具体原因。" : "当前没有报告阻塞原因。" });
  return el("section", { class: `runtime-readiness-actions${blocked ? " is-blocked" : ""}` }, [
    el("div", { class: "runtime-readiness-actions-heading" }, [
      el("h3", { text: blocked ? "阻塞与下一步" : "推荐操作 / 下一步" }),
      runtimeReadinessBadge(readiness),
    ]),
    blocked ? el("div", { class: "runtime-readiness-blockers" }, [el("strong", { text: "阻塞原因" }), blockerList]) : null,
    el("div", { class: "runtime-readiness-recommendations" }, [el("strong", { text: "操作提示" }), actionList]),
  ].filter(Boolean));
}
const runtimeCapabilityFields = ["capability_id", "domain", "runtime_id", "version", "status"];
function safeRuntimeCapabilityText(value, fallback = "未提供") {
  if (typeof value !== "string" && typeof value !== "number") return fallback;
  const text = String(value).trim().replace(/[\u0000-\u001f\u007f]/g, "");
  if (!text || text.length > 160 || /(?:secret|token|password|credential|api[_-]?key|bearer|sk-[a-z0-9]|(?:[a-z]:\\|\\\\|\/))\S*/i.test(text)) return fallback;
  return text;
}
function safeRuntimeCapabilityList(value) {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === "object" && !Array.isArray(item)) : [];
}
const runtimeCapabilityDomains = { task_agent: "task_agent（任务 Agent）", learning_loop: "learning_loop（学习闭环）" };
function runtimeCapabilityDomainGroups(value) {
  const groups = { task_agent: [], learning_loop: [] };
  safeRuntimeCapabilityList(value).forEach((capability) => {
    const domain = typeof capability.domain === "string" ? capability.domain.trim() : "";
    if (Object.prototype.hasOwnProperty.call(groups, domain)) groups[domain].push(capability);
  });
  return groups;
}
function runtimeCapabilityKey(capability) {
  return [capability.domain, capability.capability_id, capability.runtime_id, capability.version].map((value) => safeRuntimeCapabilityText(value, "")).join("\u001f");
}
function runtimeCapabilitiesFromAgentPayload(payload, agents) {
  const direct = [payload?.capabilities, payload?.runtime_readiness?.capabilities].find((value) => safeRuntimeCapabilityList(value).length);
  const candidates = direct || agents.flatMap((agent) => [
    ...safeRuntimeCapabilityList(agent?.runtime_capabilities),
    ...safeRuntimeCapabilityList(agent?.runtime_readiness?.runtime_capabilities),
  ]);
  const seen = new Set();
  return safeRuntimeCapabilityList(candidates).filter((capability) => {
    const key = runtimeCapabilityKey(capability);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
function runtimeCapabilityActions(capability) {
  const actions = Array.isArray(capability.supported_actions) ? capability.supported_actions : [];
  return actions.map((action) => safeRuntimeCapabilityText(action, "")).filter(Boolean);
}
function runtimeCapabilityControl(capability) {
  const controls = [["暂停", capability.supports_pause], ["恢复", capability.supports_resume], ["审批", capability.supports_approval], ["输入", capability.supports_input]];
  return controls.filter(([, enabled]) => enabled === true).map(([label]) => label);
}
function runtimeCapabilityEvidence(capability) {
  const blockers = Array.isArray(capability.blockers)
    ? safeRuntimeReadinessItems(capability.blockers)
    : null;
  const structuralReported = typeof capability.structural_release_eligible === "boolean";
  const semanticReported = typeof capability.semantic_release_eligible === "boolean";
  const canaryReported = typeof capability.canary_release_eligible === "boolean";
  return {
    status: safeRuntimeCapabilityText(capability.status, "未报告"),
    structuralReported,
    structuralReleaseEligible: capability.structural_release_eligible === true,
    semanticReported,
    semanticReleaseEligible: capability.semantic_release_eligible === true,
    canaryReported,
    canaryReleaseEligible: capability.canary_release_eligible === true,
    canaryLabel: canaryReported
      ? capability.canary_release_eligible ? "通过" : "未通过"
      : "未报告",
    reason: safeRuntimeCapabilityText(capability.canary_reason, "未报告"),
    blockersLabel: blockers === null ? "未报告" : blockers.join("、") || "无",
  };
}
function runtimeCapabilityEvidenceDetails(capability) {
  const evidence = runtimeCapabilityEvidence(capability);
  return [
    el("small", { text: `结构证据：${evidence.structuralReported ? evidence.structuralReleaseEligible ? "通过" : "未通过" : "未报告"}` }),
    el("small", { text: `语义证据：${evidence.semanticReported ? evidence.semanticReleaseEligible ? "通过" : "未通过" : "未报告"}` }),
    el("small", { text: `执行状态：${evidence.status}` }),
    el("small", { text: `Canary 发布资格：${evidence.canaryLabel}；原因：${evidence.reason}` }),
    el("small", { text: `发布阻塞项：${evidence.blockersLabel}` }),
  ];
}
function runtimeCapabilityEvidenceBadges(capability) {
  const evidence = runtimeCapabilityEvidence(capability);
  return [
    badge(evidence.status === "未报告" ? "unknown" : evidence.status, `执行状态：${evidence.status}`),
    badge(evidence.canaryReleaseEligible ? "ready" : evidence.canaryReported ? "failed" : "planned", `Canary：${evidence.canaryLabel}`),
  ];
}
function runtimeCapabilitiesDetails(value) {
  const capabilities = safeRuntimeCapabilityList(value);
  if (!capabilities.length) return el("p", { class: "runtime-readiness-note", text: "未提供 Runtime capability 描述。" });
  return el("section", { class: "runtime-capabilities" }, [
    el("div", { class: "runtime-readiness-actions-heading" }, [el("h3", { text: `Runtime capabilities（${capabilities.length}）` }), badge("ready", "能力清单")]),
    el("div", { class: "definition-cards" }, capabilities.map((capability) => {
      const actions = runtimeCapabilityActions(capability);
      const controls = runtimeCapabilityControl(capability);
      const evidence = runtimeCapabilityEvidence(capability);
      const contract = safeRuntimeCapabilityText(capability.result_contract, "已提供");
      const scope = safeRuntimeCapabilityText(capability.control_scope, "未提供");
      return el("article", { class: "metric-card runtime-capability-card" }, [
        el("strong", { text: safeRuntimeCapabilityText(capability.capability_id) }),
        el("div", { class: "runtime-capability-evidence" }, runtimeCapabilityEvidenceBadges(capability)),
        el("small", { text: `domain / runtime / version：${runtimeCapabilityFields.slice(1, 4).map((field) => safeRuntimeCapabilityText(capability[field])).join(" / ")}` }),
        el("small", { text: `启用：${capability.enabled === true ? "是" : "否/未提供"}；状态：${evidence.status}；动作：${actions.join(", ") || "未提供"}` }),
        ...runtimeCapabilityEvidenceDetails(capability),
        el("small", { text: `控制：${controls.join("、") || "无"}；结果契约：${contract}；控制范围：${scope}` }),
      ]);
    })),
  ]);
}
function runtimeCapabilityDomainDetails(value) {
  const groups = runtimeCapabilityDomainGroups(value);
  return el("section", { class: "runtime-capabilities runtime-capabilities-by-domain" }, [
    el("div", { class: "runtime-readiness-actions-heading" }, [el("h3", { text: "跨入口 Runtime capabilities" }), badge("ready", "按 domain")]),
    ...Object.entries(runtimeCapabilityDomains).map(([domain, label]) => {
      const capabilities = groups[domain];
      return el("section", { class: "runtime-capability-domain", "data-capability-domain": domain }, [
        el("h4", { text: label }),
        capabilities.length
          ? el("div", { class: "definition-cards" }, capabilities.map((capability) => {
            const actions = runtimeCapabilityActions(capability);
            return el("article", { class: "metric-card runtime-capability-card" }, [
              el("strong", { text: safeRuntimeCapabilityText(capability.capability_id) }),
              el("div", { class: "runtime-capability-evidence" }, runtimeCapabilityEvidenceBadges(capability)),
              el("small", { text: `runtime / version：${safeRuntimeCapabilityText(capability.runtime_id)} / ${safeRuntimeCapabilityText(capability.version)}` }),
              ...runtimeCapabilityEvidenceDetails(capability),
              el("small", { text: `control_scope：${safeRuntimeCapabilityText(capability.control_scope)}；supported_actions：${actions.join(", ") || "未提供"}` }),
            ]);
          }))
          : el("p", { class: "runtime-readiness-note", text: "未提供该 domain 的 Runtime capability 描述。" }),
      ]);
    }),
  ]);
}
function runtimeReadinessDetails(readiness) {
  if (!readiness || !Object.keys(readiness).length) return el("p", { class: "empty-state", text: "当前 Agent 未提供 Runtime readiness 字段。" });
  const evidence = runtimePublicationEvidence(readiness);
  const configuredMode = safeRuntimeReadinessText(readiness.configured_launch_mode);
  const effectiveMode = safeRuntimeReadinessText(readiness.effective_launch_mode);
  const launchSource = safeRuntimeReadinessText(readiness.launch_source, "未知来源");
  const launchReason = safeRuntimeReadinessText(readiness.launch_reason);
  const canaryReason = evidence.reason || "无 Canary 原因";
  return el("div", { class: "runtime-readiness-details" }, [
    el("section", { class: "runtime-publication-evidence", "data-evidence-state": evidence.semanticReady ? "ready" : "not_ready" }, [
      el("div", { class: "runtime-readiness-actions-heading" }, [
        el("h3", { text: "发布证据状态（只读）" }),
        badge(evidence.semanticReady ? "ready" : "planned", runtimePublicationEvidenceSummary(readiness)),
      ]),
      el("div", { class: "definition-cards" }, [
        el("article", { class: "metric-card runtime-publication-evidence-card" }, [
          badge(evidence.structuralReady ? "ready" : "planned", evidence.structuralLabel),
          el("strong", { text: evidence.structuralReady ? "结构门禁通过" : "结构证据未就绪" }),
          el("small", { text: "来源：canary_release_eligible" }),
        ]),
        el("article", { class: "metric-card runtime-publication-evidence-card" }, [
          badge(evidence.semanticReady ? "ready" : "planned", evidence.semanticLabel),
          el("strong", { text: evidence.semanticReady ? "独立语义证据通过" : "语义证据未就绪" }),
          el("small", { text: evidence.semanticBlocked ? canaryReason : "未提供独立语义通过字段，保持保守状态" }),
        ]),
        el("article", { class: "metric-card runtime-publication-evidence-card" }, [
          badge(readiness.canary_release_eligible === true ? "ready" : "planned", readiness.canary_release_eligible === true ? "Canary 资格通过" : "Canary 资格未通过"),
          el("strong", { text: canaryReason || "未提供" }),
          el("small", { text: "来源：canary_reason" }),
        ]),
      ]),
      el("p", { class: "runtime-readiness-note", text: `配置发布模式：${configuredMode}；生效发布模式：${effectiveMode}；来源：${launchSource}；原因：${launchReason}` }),
      el("div", { class: "runtime-readiness-blockers" }, [
        el("strong", { text: evidence.blockers.length ? "发布阻塞项" : "发布阻塞项：无" }),
        evidence.blockers.length
          ? el("ul", { class: "runtime-readiness-blocker-list" }, evidence.blockers.map((item) => el("li", { text: item })))
          : null,
      ].filter(Boolean)),
    ]),
    el("div", { class: "definition-cards" }, [
      el("article", { class: "metric-card" }, [runtimeReadinessBadge(readiness), el("strong", { text: readiness.effective_launch_mode || "未声明" }), el("small", { text: `生效模式 · ${readiness.launch_source || "未知来源"}` })]),
      el("article", { class: "metric-card" }, [badge(readiness.runtime_plan_available ? "ready" : "planned", readiness.runtime_plan_available ? "Runtime Plan 可用" : "Runtime Plan 缺失"), el("strong", { text: String(readiness.runtime_services?.length || 0) }), el("small", { text: "Runtime 服务" })]),
      el("article", { class: "metric-card" }, [badge(readiness.canary_release_eligible ? "ready" : "planned", readiness.canary_release_eligible ? "Canary 通过" : "Canary 未通过"), el("strong", { text: readiness.launch_reason || "未提供" }), el("small", { text: readiness.canary_reason || "无 Canary 原因" })]),
    ]),
    el("p", { class: "runtime-readiness-note", text: `运行选项：${(readiness.runtime_option_keys || []).join(", ") || "未声明"}；显式 Goal Runtime：${readiness.explicit_goal_runtime_available ? "可用" : "不可用"}` }),
     runtimeCapabilityDomainDetails(state.runtimeCapabilities),
     runtimeCapabilitiesDetails(readiness.runtime_capabilities),
     runtimeReadinessNextSteps(readiness, evidence.blockers),
  ]);
}
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
    row.append(el("td", {}, [el("strong", { text: item.display_name || item.agent_id }), el("small", { class: "table-subtitle", text: item.agent_id })]), el("td", {}, badge(statusOf(item))), el("td", { text: item.provider_type || item.provider || "—" }), el("td", {}, badge(item.configured ? "configured" : "not_configured")), el("td", { text: (item.courses || item.supported_courses || []).join(", ") || "—" }), el("td", { text: item.retrieval_policy || "no_rag" }), el("td", { text: item.recent_contract_test?.status || "未运行" }), el("td", {}, [runtimeReadinessBadge(item.runtime_readiness), el("small", { class: "table-subtitle", text: runtimePublicationEvidenceSummary(item.runtime_readiness) }), el("small", { class: "table-subtitle", text: item.runtime_readiness?.blockers?.length ? "有阻塞" : item.runtime_readiness?.effective_launch_mode || "—" })]));
    row.addEventListener("click", () => selectAgent(item.agent_id)); row.addEventListener("keydown", (event) => { if (event.key === "Enter") selectAgent(item.agent_id); }); return row;
  }) : [el("tr", {}, el("td", { colspan: "8", class: "empty-state", text: "没有符合条件的 Agent。" }))]));
}
async function selectAgent(id) { state.selected = id; $("#agent-select").value = id; await loadDefinition(); all("[data-agent]").forEach((row) => row.classList.toggle("selected", row.dataset.agent === id)); }
async function loadAgents() {
  try {
    const data = await api("/api/v1/agents", {}, 5000); state.agents = data.agents || []; state.runtimeCapabilities = runtimeCapabilitiesFromAgentPayload(data, state.agents); state.actionsEnabled = Boolean(data.debug_actions_enabled); state.mocksEnabled = Boolean(data.mock_actions_enabled);
    const env = badge(state.actionsEnabled ? (state.mocksEnabled ? "mock" : "ready") : "disabled", state.actionsEnabled ? (state.mocksEnabled ? "Debug · Mock 可用" : "Debug · Mock 关闭") : "只读模式"); env.id = "environment-badge"; $("#environment-badge").replaceWith(env);
    $("#agent-select").replaceChildren(...state.agents.map((item) => el("option", { value: item.agent_id, text: item.display_name || item.agent_id })));
    all("[data-action]").forEach((button) => { button.disabled = !state.actionsEnabled || (button.dataset.action === "mock" && !state.mocksEnabled); });
    renderRows(); if (state.agents.length) await selectAgent(state.selected || state.agents[0].agent_id);
  } catch (error) { $("#agent-grid").replaceChildren(el("tr", {}, el("td", { colspan: "8", class: "field-error", text: `${error.message}。请检查本地 API。` }))); }
}
function summaryNode(data, readiness) {
  const capabilities = data.capabilities || {};
  return el("div", { class: "definition-cards" }, [
    el("article", { class: "metric-card" }, [badge(data.enabled ? "ready" : "disabled"), el("strong", { text: data.display_name || data.agent_id }), el("small", { text: data.agent_id || "" })]),
    el("article", { class: "metric-card" }, [badge(data.configured ? "configured" : "not_configured"), el("strong", { text: data.provider?.type || data.provider_type || "Provider" }), el("small", { text: `Parser: ${data.provider?.parser_type || data.parser_type || "—"}` })]),
    el("article", { class: "metric-card" }, [badge(data.lifecycle_status || data.publication_status || "planned"), el("strong", { text: (capabilities.courses || data.courses || []).join(", ") || "未声明课程" }), el("small", { text: (capabilities.intents || data.intents || []).join(", ") || "未声明意图" })]),
    el("article", { class: "metric-card" }, [runtimeReadinessBadge(readiness), el("strong", { text: readiness?.effective_launch_mode || "未报告" }), el("small", { text: "Agent Runtime" })]),
  ]);
}
async function loadDefinition() {
  const id = $("#agent-select").value; if (!id) return;
  try {
    const data = await api(`/api/v1/agents/${encodeURIComponent(id)}`); const readiness = state.agents.find((item) => item.agent_id === id)?.runtime_readiness; renderJson($("#definition-json"), data); $("#definition-summary").replaceChildren(summaryNode(data, readiness)); $("#runtime-readiness-summary").replaceChildren(runtimeReadinessDetails(readiness));
    const retrieval = data.retrieval_policy || data.retrieval || {}; const fallback = data.fallback || {};
    $("#strategy-summary").replaceChildren(el("div", { class: "definition-cards" }, [el("article", { class: "metric-card" }, [el("strong", { text: retrieval.policy_name || retrieval.name || String(retrieval) || "no_rag" }), el("span", { text: "RetrievalPolicy" })]), el("article", { class: "metric-card" }, [el("strong", { text: fallback.type || "no_fallback" }), el("span", { text: "Fallback" })])]));
  } catch (error) { renderJson($("#definition-json"), { error: error.message }); $("#definition-summary").textContent = error.message; $("#runtime-readiness-summary").textContent = "Runtime readiness 暂不可用"; }
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
