const { $, all, api, badge, el, initShell, renderJson, renderMarkdown, toast } = XinzhiUI;
let execution = null;
let runtimePollTimer = null;
let runtimePollToken = 0;
let runtimePollAttempts = 0;
let runtimeControlBusy = false;
let runtimeControlFeedback = null;
let learningRuntimeStatus = null;
let learningRuntimeStatusRunId = "";
let learningRuntimeStatusToken = 0;
let learningRuntimeControls = null;
let learningRuntimeControlsRunId = "";
let learningRuntimeControlsToken = 0;
const runtimePollStatuses = new Set(["running", "queued", "waiting_input", "waiting_approval", "paused"]);
const runtimePollDelaysMs = [1000, 2000, 4000, 8000, 16000];
const runtimeControlAllowedStatuses = {
  pause: new Set(["created", "queued", "running"]),
  resume: new Set(["paused", "waiting_input"]),
  approve: new Set(["waiting_approval"]),
};
const runtimeStatusLabels = { created: "已创建", queued: "排队中", running: "运行中", waiting_input: "等待输入", waiting_approval: "等待审批", paused: "已暂停", completed: "已完成", succeeded: "成功", failed: "失败", cancelled: "已取消", pending: "待执行", ready: "就绪", partial: "部分完成", skipped: "已跳过", blocked: "已阻塞" };
const runtimeEffectLabels = { not_started: "未开始", in_progress: "进行中", completed: "已完成", unknown: "未知" };
function runtimeStatusKey(status) { return String(status || "").trim().toLowerCase(); }
function runtimeStatusLabel(status) { const key = runtimeStatusKey(status); return runtimeStatusLabels[key] || (status ? String(status) : "未报告"); }
function runtimeStatusTone(status) { const key = runtimeStatusKey(status); return ["completed", "succeeded"].includes(key) ? "success" : ["failed", "cancelled", "blocked"].includes(key) ? "failed" : ["running"].includes(key) ? "running" : ["waiting_input", "waiting_approval", "paused", "partial"].includes(key) ? "partial" : ["ready"].includes(key) ? "ready" : "planned"; }
function runtimeStatusBadge(status) { return badge(runtimeStatusTone(status), runtimeStatusLabel(status)); }
function asRecord(value) { return value && typeof value === "object" && !Array.isArray(value) ? value : {}; }
function runtimeSafePrompt(runtime) {
  const decision = asRecord(runtime?.last_decision);
  const waiting = asRecord(runtime?.waiting_input);
  const candidates = [runtime?.user_prompt, runtime?.input_prompt, waiting.prompt, decision.user_prompt];
  const prompt = candidates.find((value) => typeof value === "string" && value.trim());
  return typeof prompt === "string"
    ? prompt.trim().replace(/[\u0000-\u001f\u007f]/g, "").slice(0, 2_000)
    : "Runtime 已暂停在输入门；请提交补充信息后继续执行。";
}
function runtimeWaitingInputSurface(runtime) {
  if (runtimeStatusKey(runtime?.status) !== "waiting_input") return null;
  const resumable = runtime.resumable === false ? "否" : "是";
  return section(
    "等待输入",
    "Runtime 正在等待用户补充信息。当前只展示经过限制的用户提示，不展示原始请求快照或控制数据。",
    kvSurface("Input checkpoint", [
      ["用户提示", runtimeSafePrompt(runtime)],
      ["state_version", runtime.state_version],
      ["可恢复", resumable],
      ["恢复边界", "提交输入后由后端校验状态版本并恢复 Runtime"],
    ]),
  );
}
function displayValue(value) {
  if (value == null || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.map((item) => displayValue(item)).join("、") : "—";
  if (typeof value === "object") {
    try { return JSON.stringify(value); } catch { return "[不可显示]"; }
  }
  return String(value);
}
function runtimeControlEvent(data) {
  const events = Array.isArray(data.events) ? data.events : [];
  const statuses = new Set(["approval_required", "pause_requested", "resumed", "approved", "rejected", "applied"]);
  return [...events].reverse().find((event) => statuses.has(runtimeStatusKey(event?.data?.status || event?.status || event?.type)));
}
function runtimeHandoff(data, runtime) {
  const final = asRecord(data.final);
  const handoff = asRecord(runtime.handoff || runtime.runtime_handoff || runtime.control_data?.runtime_handoff || data.handoff || data.runtime_handoff);
  const fallbackUsed = handoff.fallback_used ?? handoff.used ?? (handoff.status === "legacy_fallback" ? true : undefined) ?? runtime.fallback_used ?? final.fallback_used;
  const fallbackReason = handoff.fallback_reason || handoff.reason || runtime.fallback_reason || final.fallback_reason;
  return {
    status: handoff.status || handoff.handoff_status || runtime.handoff_status,
    mode: handoff.mode || runtime.launch_decision?.mode,
    runtimeStatus: handoff.runtime_status || runtime.status,
    bypassLegacy: handoff.bypass_legacy_execution ?? handoff.bypass_legacy,
    fallbackUsed,
    fallbackReason,
  };
}
function runtimeStatusNotice(runtime, controlEvent, handoff) {
  const status = runtimeStatusKey(runtime.status);
  const eventStatus = runtimeStatusKey(controlEvent?.data?.status || controlEvent?.status || controlEvent?.type);
  const waitingApproval = status === "waiting_approval" || eventStatus === "approval_required";
  const paused = status === "paused" || eventStatus === "pause_requested" || eventStatus === "rejected";
  const waitingInput = status === "waiting_input";
  const fallback = handoff.fallbackUsed === true;
  if (!waitingApproval && !paused && !waitingInput && !fallback) return null;
  const notice = waitingApproval
    ? { tone: "partial", title: "等待人工审批", text: "Runtime 已停在审批门，后续节点不会继续执行，直到审批状态发生变化。" }
    : paused
      ? { tone: "partial", title: "Runtime 已暂停", text: "当前运行已停在安全边界；恢复前请检查最近控制事件和节点 checkpoint。" }
      : waitingInput
        ? { tone: "partial", title: "等待用户输入", text: "Runtime 需要补充输入后才能继续规划或执行。" }
        : { tone: "failed", title: "已发生执行降级", text: `Runtime handoff 使用了兼容 fallback${handoff.fallbackReason ? `：${handoff.fallbackReason}` : "。"}` };
  return el("div", { class: `runtime-status-notice ${notice.tone}`, role: "status", "aria-live": "polite" }, [
    el("div", { class: "runtime-status-notice-copy" }, [el("strong", { text: notice.title }), el("p", { text: notice.text })]),
    runtimeStatusBadge(runtime.status),
  ]);
}
function runtimeNodeSurface(runtime) {
  const nodes = Array.isArray(runtime.nodes) ? runtime.nodes : [];
  if (!nodes.length) return el("div", { class: "empty-state", text: "本次响应未提供 Runtime node checkpoint。" });
  const counts = nodes.reduce((result, node) => { const key = runtimeStatusKey(node?.status) || "unknown"; result[key] = (result[key] || 0) + 1; return result; }, {});
  const summary = el("div", { class: "runtime-node-summary" }, Object.entries(counts).map(([status, count]) => el("span", { class: "runtime-node-count" }, [runtimeStatusBadge(status), el("strong", { text: count })])));
  const list = el("div", { class: "runtime-node-list" });
  nodes.forEach((node) => list.append(el("article", { class: "runtime-node-row" }, [
    el("div", { class: "runtime-node-heading" }, [el("strong", { text: node.node_id || "未命名节点" }), runtimeStatusBadge(node.status)]),
    el("div", { class: "runtime-node-meta" }, [el("span", { text: `${node.node_type || "node"} · ${node.handler_id || "handler"}` }), el("span", { text: `尝试 ${node.attempt ?? 0}` }), el("span", { text: `Effect ${runtimeEffectLabels[runtimeStatusKey(node.effect_status)] || node.effect_status || "未报告"}` }), node.target_id ? el("span", { text: `Target ${node.target_id}` }) : null, node.iteration != null ? el("span", { text: `迭代 ${node.iteration}` }) : null]),
    node.error_code ? el("p", { class: "runtime-node-error", text: `错误：${node.error_code}` }) : null,
  ])));
  return el("div", {}, [summary, list]);
}
function runtimeControlSurface(runtime, controlEvent) {
  const eventData = controlEvent?.data || {};
  const status = runtimeStatusKey(runtime.status);
  const eventStatus = runtimeStatusKey(eventData.status || controlEvent?.type);
  const description = { pause_requested: "已提交暂停请求，Runtime 会在安全边界处理。", approval_required: "Runtime 正在等待审批门通过。", approved: "审批已通过，等待恢复执行。", rejected: "审批被拒绝，Runtime 保持暂停。", resumed: "已提交恢复请求，等待 Runtime 继续执行。", applied: "新计划已应用，等待 Runtime 继续执行。" }[eventStatus] || { waiting_input: "Runtime 正在等待用户输入。", waiting_approval: "Runtime 正在等待审批门通过。", paused: "Runtime 已暂停，后续节点尚未继续。", running: "Runtime 正在执行。" }[status] || "当前没有暂停或审批等待状态。";
  return kvSurface("暂停 / 审批 / 恢复", [["当前状态", runtimeStatusLabel(status)], ["说明", description], ["最近控制事件", eventData.status || controlEvent?.type || "未报告"], ["proposal_id", eventData.proposal_id], ["受影响节点", eventData.affected_node_ids], ["原因", eventData.reason || eventData.reason_codes], ["state_version", runtime.state_version]]);
}

function setRuntimeControlFeedback(message, tone = "") {
  runtimeControlFeedback = message ? { message, tone } : null;
  const target = $("#runtime-control-feedback");
  if (!target) return;
  target.className = `runtime-control-feedback${tone ? ` ${tone}` : ""}`;
  target.textContent = message || "";
}

function safeRuntimeControlError(error) {
  const status = Number(error?.status);
  if (status === 401) return "操作失败：请先登录。";
  if (status === 403) return "操作失败：当前身份没有执行该控制动作的权限。";
  if (status === 404) return "操作失败：任务不存在或已不可见。";
  if (status === 409) return "操作失败：Runtime 状态已变化，请刷新后重试。";
  return "操作失败：服务暂时无法处理，请稍后重试。";
}

const learningRuntimeControlLabels = {
  approve: "人工审批",
  pause: "暂停",
  resume: "恢复",
  input: "用户输入",
};

function learningRuntimeControlProjection(reference) {
  if (!reference || learningRuntimeControlsRunId !== reference.runId) return null;
  return learningRuntimeControls;
}

function learningRuntimeControlEntry(projection, action) {
  const controls = Array.isArray(projection?.controls) ? projection.controls : [];
  return controls.find((item) => String(item?.action || "") === action) || null;
}

function learningRuntimeControlStateVersion(projection) {
  const stateVersion = Number(projection?.state_version);
  return Number.isSafeInteger(stateVersion) && stateVersion >= 1 ? stateVersion : null;
}

function learningRuntimeApproveAvailable(reference, projection) {
  const entry = learningRuntimeControlEntry(projection, "approve");
  const availableControls = Array.isArray(projection?.available_controls)
    ? projection.available_controls
    : [];
  const status = runtimeStatusKey(projection?.status || reference?.status || reference?.snapshot?.status);
  return status === "waiting_approval"
    && entry?.available === true
    && availableControls.includes("approve")
    && learningRuntimeControlStateVersion(projection) != null;
}

function learningRuntimeControlFetchErrorCode(error) {
  const status = Number(error?.status);
  if (status === 401) return "learning_runtime_controls_unauthorized";
  if (status === 403) return "learning_runtime_controls_forbidden";
  if (status === 404) return "learning_runtime_controls_not_found";
  return "learning_runtime_controls_unavailable";
}

function learningRuntimeControlContractSurface(reference, projection) {
  const status = projection?.status || reference.status || reference.snapshot.status;
  const controls = ["approve", "pause", "resume", "input"].map((action) => {
    const entry = learningRuntimeControlEntry(projection, action);
    const available = entry?.available === true;
    const reasonCode = entry?.reason_code || (projection ? "not_reported" : "learning_runtime_controls_loading");
    const reason = entry?.reason || (projection
      ? "后端未报告该控制动作的可用原因。"
      : "正在读取后端控制能力；在读取完成前不会发送控制请求。");
    const rejected = action !== "approve" ? "不会从此页面发送请求。" : "";
    return el("div", { class: "runtime-control-row" }, [
      el("strong", { text: learningRuntimeControlLabels[action] }),
      badge(available ? "ready" : "blocked", available ? "后端可用" : "禁用 / rejected"),
      el("span", { text: `reason_code: ${reasonCode}` }),
      el("p", { text: `${reason}${rejected ? ` ${rejected}` : ""}` }),
    ]);
  });
  const availableControls = Array.isArray(projection?.available_controls)
    ? projection.available_controls
    : [];
  return el("div", { id: "learning-runtime-control-contract", class: "debug-surface" }, [
    el("h3", { text: "LearningLoop 后端控制能力" }),
    el("p", { text: "控制能力与 reason code 直接来自后端 projection；敏感请求快照不在此处展示。" }),
    kvSurface("Control projection", [
      ["status", status],
      ["state_version", projection?.state_version || reference.snapshot.state_version],
      ["available_controls", availableControls],
      ["control_scope", projection?.control_scope || reference.snapshot.control_scope],
      ["projection_error", projection?.fetch_error_code],
    ]),
    el("div", { class: "runtime-control-list" }, controls),
    el("p", { class: "runtime-control-feedback warning", text: "pause / resume / input 当前由 LearningLoop 后端拒绝或未实现，界面保持 disabled，不会发送请求。" }),
  ]);
}

function renderLearningRuntimeControls(reference) {
  const panel = $("#runtime-controls");
  if (!panel) return;
  const projection = learningRuntimeControlProjection(reference);
  const status = runtimeStatusKey(projection?.status || reference.status || reference.snapshot.status);
  panel.hidden = false;
  panel.dataset.learningRuntime = "true";
  const title = panel.querySelector("#runtime-controls-title");
  if (title) title.textContent = "LearningLoop Operator Control";
  const description = panel.querySelector(".runtime-control-heading p");
  if (description) description.textContent = "仅在后端报告 approve 可用且 Runtime 等待审批时提交审批；其他动作保持 disabled。";
  const state = $("#runtime-control-state");
  if (state) {
    state.textContent = `LearningLoop 状态：${runtimeStatusLabel(status)}`;
    state.dataset.status = status || "unknown";
  }

  const approve = $("#runtime-approve");
  const approveAvailable = learningRuntimeApproveAvailable(reference, projection);
  if (approve) {
    approve.hidden = !approveAvailable;
    approve.disabled = runtimeControlBusy || !approveAvailable;
    approve.setAttribute("aria-disabled", String(approve.disabled));
    approve.title = approveAvailable
      ? `提交 approve（expected_state_version=${learningRuntimeControlStateVersion(projection)}）`
      : "LearningLoop 后端未同时报告 waiting_approval、approve available 和有效 state_version。";
    approve.textContent = "人工审批";
  }

  ["pause", "resume"].forEach((action) => {
    const button = $(`#runtime-${action}`);
    if (!button) return;
    const entry = learningRuntimeControlEntry(projection, action);
    const reasonCode = entry?.reason_code || "learning_runtime_control_rejected";
    button.hidden = false;
    button.disabled = true;
    button.setAttribute("aria-disabled", "true");
    button.title = `${entry?.reason || "LearningLoop 当前不支持此动作。"} reason_code: ${reasonCode}。不会发送请求。`;
    button.textContent = `${learningRuntimeControlLabels[action]}（disabled）`;
  });

  panel.querySelector("#learning-runtime-control-contract")?.remove();
  panel.append(learningRuntimeControlContractSurface(reference, projection));
  const feedback = $("#runtime-control-feedback");
  if (feedback) {
    feedback.className = `runtime-control-feedback${runtimeControlFeedback?.tone ? ` ${runtimeControlFeedback.tone}` : ""}`;
    feedback.textContent = runtimeControlFeedback?.message || "";
  }
}

function renderRuntimeControls(data) {
  const panel = $("#runtime-controls");
  if (!panel) return;
  const learningReference = learningRuntimeReference(data);
  if (learningReference) {
    renderLearningRuntimeControls(learningReference);
    return;
  }
  panel.dataset.learningRuntime = "false";
  panel.querySelector("#learning-runtime-control-contract")?.remove();
  const title = panel.querySelector("#runtime-controls-title");
  if (title) title.textContent = "Runtime 控制面";
  const description = panel.querySelector(".runtime-control-heading p");
  if (description) description.textContent = "仅提交显式的暂停、恢复或人工审批请求；最终权限与状态由后端校验。";
  const taskId = String(data?.task?.id || $("#task-id")?.value || "").trim();
  panel.hidden = !taskId;
  if (!taskId) return;

  const runtime = asRecord(data?.runtime);
  const status = runtimeStatusKey(runtime.status);
  const state = $("#runtime-control-state");
  if (state) {
    state.textContent = status ? `当前状态：${runtimeStatusLabel(status)}` : "未发现 Runtime 状态";
    state.dataset.status = status || "unknown";
  }
  ["pause", "resume", "approve"].forEach((action) => {
    const button = $(`#runtime-${action}`);
    if (!button) return;
    button.hidden = false;
    const applicable = Boolean(runtime.run_id) && runtimeControlAllowedStatuses[action].has(status);
    button.disabled = runtimeControlBusy || !applicable;
    button.setAttribute("aria-disabled", String(button.disabled));
    button.title = runtimeControlBusy
      ? "正在提交 Runtime 控制请求"
      : applicable
        ? "提交后由后端按当前身份和 Runtime 状态校验"
        : "当前 Runtime 状态不支持此动作";
  });
  const feedback = $("#runtime-control-feedback");
  if (feedback) {
    feedback.className = `runtime-control-feedback${runtimeControlFeedback?.tone ? ` ${runtimeControlFeedback.tone}` : ""}`;
    feedback.textContent = runtimeControlFeedback?.message || "";
  }
}

async function refreshExecutionOnce(id) {
  if ($("#task-id")?.value.trim() !== id) return;
  stopRuntimePolling();
  const token = runtimePollToken;
  try {
    const latest = await api(`/api/v1/debug/execution/${encodeURIComponent(id)}`);
    if (token !== runtimePollToken || $("#task-id")?.value.trim() !== id) return;
    renderAll(latest);
    scheduleRuntimePolling(id, latest, token);
  } catch (_error) {
    setRuntimeControlFeedback("请求已提交，但状态刷新失败，请手动重新载入。", "warning");
  }
}

async function executeRuntimeControl(action) {
  if (learningRuntimeReference(execution)) {
    if (action === "approve") return executeLearningRuntimeControl();
    return;
  }
  const id = String(execution?.task?.id || $("#task-id")?.value || "").trim();
  const runtime = asRecord(execution?.runtime);
  const status = runtimeStatusKey(runtime.status);
  if (!id || runtimeControlBusy || !runtime.run_id || !runtimeControlAllowedStatuses[action]?.has(status)) return;

  runtimeControlBusy = true;
  setRuntimeControlFeedback("正在提交 Runtime 控制请求…", "pending");
  renderRuntimeControls(execution);
  try {
    const query = `?runtime_run_id=${encodeURIComponent(runtime.run_id)}`;
    const options = { method: "POST" };
    if (action === "approve") {
      const stateVersion = Number(runtime.state_version);
      const payload = { decision: "approved" };
      if (Number.isInteger(stateVersion) && stateVersion >= 1) payload.expected_state_version = stateVersion;
      options.headers = { "Content-Type": "application/json" };
      options.body = JSON.stringify(payload);
    }
    await api(`/api/v1/tasks/${encodeURIComponent(id)}/${action}${query}`, options);
    const labels = { pause: "暂停请求已提交。", resume: "恢复请求已提交。", approve: "人工审批请求已提交。" };
    setRuntimeControlFeedback(`${labels[action]} 正在刷新 Runtime 状态。`, "success");
  } catch (error) {
    setRuntimeControlFeedback(safeRuntimeControlError(error), "failed");
  } finally {
    await refreshExecutionOnce(id);
    runtimeControlBusy = false;
    if (execution) renderRuntimeControls(execution);
  }
}

async function executeLearningRuntimeControl() {
  const reference = learningRuntimeReference(execution);
  const projection = learningRuntimeControlProjection(reference);
  if (!reference || runtimeControlBusy || !learningRuntimeApproveAvailable(reference, projection)) {
    if (reference && !runtimeControlBusy) {
      setRuntimeControlFeedback("LearningLoop 当前不满足审批条件，未发送请求。", "warning");
      renderLearningRuntimeControls(reference);
    }
    return;
  }
  const expectedStateVersion = learningRuntimeControlStateVersion(projection);
  runtimeControlBusy = true;
  setRuntimeControlFeedback("正在提交 LearningLoop 审批请求…", "pending");
  renderLearningRuntimeControls(reference);
  try {
    await api(`/api/v1/learning/runtime/${encodeURIComponent(reference.runId)}/control`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve", expected_state_version: expectedStateVersion }),
    });
    const [statusRefresh, controlsRefresh] = await Promise.all([
      loadLearningRuntimeStatus(execution, true),
      loadLearningRuntimeControls(execution, true),
    ]);
    if (statusRefresh == null || controlsRefresh == null) {
      setRuntimeControlFeedback("审批已提交，但 LearningLoop 状态刷新不完整，请重新加载。", "warning");
    } else {
      setRuntimeControlFeedback("LearningLoop 审批已提交，状态已刷新。", "success");
    }
  } catch (error) {
    setRuntimeControlFeedback(safeRuntimeControlError(error), "failed");
  } finally {
    runtimeControlBusy = false;
    if (execution) renderRuntimeControls(execution);
  }
}

function runtimeBudgetPair(budget, usedKey, maxKey) {
  const used = budget[usedKey]; const max = budget[maxKey];
  if (used == null && max == null) return "—";
  const usedValue = used ?? 0; const maxValue = max ?? "未设置";
  const remaining = Number.isFinite(Number(usedValue)) && Number.isFinite(Number(maxValue)) ? Math.max(0, Number(maxValue) - Number(usedValue)) : null;
  return `${displayValue(usedValue)} / ${displayValue(maxValue)}${remaining == null ? "" : `（剩余 ${remaining}）`}`;
}
function runtimeBudgetSurface(runtime) {
  const budget = asRecord(runtime.budget);
  const childConsumption = asRecord(budget.child_consumption);
  return kvSurface("Runtime Budget", [
    ["迭代（当前 / 上限）", `${displayValue(runtime.iteration ?? 0)} / ${displayValue(budget.max_iterations)}`],
    ["模型调用（已用 / 上限）", runtimeBudgetPair(budget, "model_calls", "max_model_calls")],
    ["工具调用（已用 / 上限）", runtimeBudgetPair(budget, "tool_calls", "max_tool_calls")],
    ["子 Agent（已用 / 上限）", runtimeBudgetPair(budget, "subagent_runs", "max_subagent_runs")],
    ["截止时间", budget.deadline],
    ["子运行消耗记录", Object.keys(childConsumption).length ? `${Object.keys(childConsumption).length} 条` : "—"],
  ]);
}
function runtimeHandoffSurface(handoff) {
  return kvSurface("Handoff / Fallback", [
    ["handoff 状态", handoff.status],
    ["启动 / 兼容模式", handoff.mode],
    ["Runtime 状态", runtimeStatusLabel(handoff.runtimeStatus)],
    ["是否绕过 Legacy", handoff.bypassLegacy == null ? undefined : (handoff.bypassLegacy ? "是" : "否")],
    ["是否发生 fallback", handoff.fallbackUsed == null ? undefined : (handoff.fallbackUsed ? "是" : "否")],
    ["fallback 原因", handoff.fallbackReason],
  ]);
}
function runtimeChildrenSurface(runtime) {
  const children = Array.isArray(runtime.children) ? runtime.children : [];
  if (!children.length) return el("div", { class: "empty-state", text: "本次 Runtime 没有记录子运行。" });
  const list = el("div", { class: "runtime-child-list" });
  children.forEach((child) => list.append(el("article", { class: "runtime-child-row" }, [
    el("div", { class: "runtime-node-heading" }, [el("strong", { text: child.run_id || "未命名子运行" }), runtimeStatusBadge(child.status)]),
    el("div", { class: "runtime-node-meta" }, [el("span", { text: child.run_kind || "child" }), child.agent_id ? el("span", { text: `Agent ${child.agent_id}` }) : null, child.parent_node_id ? el("span", { text: `父节点 ${child.parent_node_id}` }) : null, child.plan_id ? el("span", { text: `Plan ${child.plan_id}` }) : null, child.state_version != null ? el("span", { text: `state ${child.state_version}` }) : null]),
  ])));
  return list;
}
function learningRuntimeReference(data) {
  const runtime = asRecord(data?.runtime);
  const inline = data?.learning_runtime;
  const learning = asRecord(inline);
  const runKind = String(learning.run_kind || data?.runtime_kind || runtime.run_kind || "").trim();
  const controlScope = learning.control_scope || data?.control_scope || runtime.control_scope;
  const isLearningLoop = inline != null || data?.runtime_run_id || controlScope === "learning_loop" || ["teaching_interaction", "learning_progress"].includes(runKind);
  if (!isLearningLoop) return null;
  const runId = learning.runtime_run_id || learning.run_id || data?.runtime_run_id || runtime.runtime_run_id || (runKind ? runtime.run_id : "");
  if (!runId) return null;
  const status = learning.status || learning.runtime_status || data?.runtime_status || runtime.status;
  const snapshot = asRecord(data?.learning_runtime_status || inline || (controlScope === "learning_loop" ? runtime : {}));
  return { runId: String(runId), runKind, status, snapshot };
}
function learningRuntimeStatusSurfaceLegacy(reference) {
  const snapshot = learningRuntimeStatusRunId === reference.runId && learningRuntimeStatus
    ? learningRuntimeStatus
    : reference.snapshot;
  const controls = Array.isArray(snapshot.available_controls) ? snapshot.available_controls : undefined;
  return section("LearningLoop Runtime (read-only)", "只读取 LearningLoop Runtime 状态；可用控制动作仅按后端返回展示，不在此页面执行控制。", kvSurface("Runtime status contract", [
    ["runtime_id", snapshot.runtime_id || snapshot.runtime_run_id || snapshot.run_id || reference.runId],
    ["status", snapshot.status || snapshot.runtime_status || reference.status],
    ["control_scope", snapshot.control_scope],
    ["available_controls", controls],
  ]));
}
function learningRuntimeNodeStatusSurface(nodes) {
  const statuses = Array.isArray(nodes)
    ? nodes.filter((node) => node && typeof node === "object" && !Array.isArray(node))
    : [];
  if (!statuses.length) {
    return el("div", { class: "empty-state", text: "No LearningLoop node status reported." });
  }
  const list = el("div", { class: "runtime-node-list" });
  statuses.forEach((node) => {
    const nodeId = typeof node.node_id === "string" && node.node_id.trim()
      ? node.node_id
      : "Unnamed node";
    const status = node.status == null ? "unknown" : node.status;
    const effectStatus = node.effect_status == null ? "unknown" : node.effect_status;
    const attempt = Number.isFinite(Number(node.attempt)) ? Number(node.attempt) : 0;
    const errorCode = typeof node.error_code === "string" && node.error_code.trim()
      ? node.error_code
      : "";
    list.append(el("article", { class: "runtime-node-row" }, [
      el("div", { class: "runtime-node-heading" }, [
        el("strong", { text: nodeId }),
        runtimeStatusBadge(status),
      ]),
      el("div", { class: "runtime-node-meta" }, [
        el("span", { text: `Effect ${runtimeEffectLabels[runtimeStatusKey(effectStatus)] || effectStatus}` }),
        el("span", { text: `Attempt ${attempt}` }),
      ]),
      errorCode ? el("p", { class: "runtime-node-error", text: `Error code: ${errorCode}` }) : null,
    ]));
  });
  return list;
}

function learningRuntimeStatusSurface(reference) {
  const snapshot = learningRuntimeStatusRunId === reference.runId && learningRuntimeStatus
    ? learningRuntimeStatus
    : asRecord(reference.snapshot);
  const controls = Array.isArray(snapshot.available_controls) ? snapshot.available_controls : undefined;
  const status = snapshot.status || snapshot.runtime_status || reference.status;
  return section(
    "LearningLoop Runtime (read-only)",
    "Read-only LearningLoop Runtime status. Controls are displayed from the backend contract only; this page never executes a LearningLoop control action.",
    el("div", { class: "debug-grid" }, [
      kvSurface("Runtime status contract", [
        ["runtime_id", snapshot.runtime_id || snapshot.runtime_run_id || snapshot.run_id || reference.runId],
        ["run_kind", snapshot.run_kind || reference.runKind],
        ["status", status],
        ["goal", snapshot.goal],
        ["success_criteria", snapshot.success_criteria],
        ["state_version", snapshot.state_version],
        ["resumable", snapshot.resumable],
        ["approval_required", snapshot.approval_required],
        ["control_scope", snapshot.control_scope],
        ["available_controls", controls],
      ]),
      el("article", { class: "debug-surface" }, [
        el("h3", { text: "Node statuses" }),
        learningRuntimeNodeStatusSurface(snapshot.node_statuses),
      ]),
    ]),
  );
}

function loadLearningRuntimeStatus(data, force = false) {
  const reference = learningRuntimeReference(data);
  if (!reference) {
    learningRuntimeStatus = null;
    learningRuntimeStatusRunId = "";
    learningRuntimeStatusToken += 1;
    return Promise.resolve(null);
  }
  const inlineContract = reference.snapshot.control_scope && Array.isArray(reference.snapshot.available_controls);
  if (inlineContract && !force) {
    learningRuntimeStatus = reference.snapshot;
    learningRuntimeStatusRunId = reference.runId;
    return Promise.resolve(learningRuntimeStatus);
  }
  if (!force && learningRuntimeStatusRunId === reference.runId && learningRuntimeStatus) {
    return Promise.resolve(learningRuntimeStatus);
  }
  learningRuntimeStatusRunId = reference.runId;
  learningRuntimeStatus = {
    ...reference.snapshot,
    run_id: reference.runId,
    status: reference.snapshot.status || reference.status,
    control_scope: reference.snapshot.control_scope || "not_reported",
    available_controls: Array.isArray(reference.snapshot.available_controls) ? reference.snapshot.available_controls : undefined,
  };
  const token = ++learningRuntimeStatusToken;
  return api(`/api/v1/learning/runtime/${encodeURIComponent(reference.runId)}`)
    .then((snapshot) => {
      if (token !== learningRuntimeStatusToken || learningRuntimeStatusRunId !== reference.runId) return null;
      learningRuntimeStatus = asRecord(snapshot);
      renderRuntime(execution || data);
      return learningRuntimeStatus;
    })
    .catch(() => {
      if (token !== learningRuntimeStatusToken || learningRuntimeStatusRunId !== reference.runId) return null;
      renderRuntime(execution || data);
      return null;
    });
}

function loadLearningRuntimeControls(data, force = false) {
  const reference = learningRuntimeReference(data);
  if (!reference) {
    learningRuntimeControls = null;
    learningRuntimeControlsRunId = "";
    learningRuntimeControlsToken += 1;
    return Promise.resolve(null);
  }
  if (!force && learningRuntimeControlsRunId === reference.runId && learningRuntimeControls) {
    return Promise.resolve(learningRuntimeControls);
  }
  learningRuntimeControlsRunId = reference.runId;
  learningRuntimeControls = null;
  const token = ++learningRuntimeControlsToken;
  return api(`/api/v1/learning/runtime/${encodeURIComponent(reference.runId)}/controls`)
    .then((projection) => {
      if (token !== learningRuntimeControlsToken || learningRuntimeControlsRunId !== reference.runId) return null;
      learningRuntimeControls = asRecord(projection);
      renderRuntime(execution || data);
      return learningRuntimeControls;
    })
    .catch((error) => {
      if (token !== learningRuntimeControlsToken || learningRuntimeControlsRunId !== reference.runId) return null;
      learningRuntimeControls = {
        run_id: reference.runId,
        status: reference.status || reference.snapshot.status,
        state_version: reference.snapshot.state_version,
        controls: [],
        available_controls: [],
        fetch_error_code: learningRuntimeControlFetchErrorCode(error),
      };
      renderRuntime(execution || data);
      return null;
    });
}
function renderRuntime(data) {
  const runtime = data.runtime || {};
  const nodes = Array.isArray(runtime.nodes) ? runtime.nodes : [];
  const learningReference = learningRuntimeReference(data);
  const goalContract = runtime.goal_contract || {};
  const controlEvent = runtimeControlEvent(data);
  const handoff = runtimeHandoff(data, runtime);
  const waitingInputSurface = runtimeWaitingInputSurface(runtime);
  renderRuntimeControls(data);
  const hasRuntime = Boolean(runtime.run_id || runtime.status || runtime.goal || nodes.length || learningReference);
  if (!hasRuntime) {
    $("#runtime-panel").replaceChildren(section("Agent Runtime", "本次任务没有返回 Runtime checkpoint；保留现有 Legacy 执行数据。", el("div", { class: "empty-state", text: "未发现 Runtime run、Goal 或 node 状态。" })));
    return;
  }
  $("#runtime-panel").replaceChildren(
    runtimeStatusNotice(runtime, controlEvent, handoff),
    section("Runtime 状态", "展示持久化 Runtime 的运行阶段、控制门和版本信息；缺失字段按未报告处理。", el("div", { class: "debug-grid" }, [
      kvSurface("运行身份", [["Run ID", runtime.run_id], ["Run kind", runtime.run_kind], ["状态", runtimeStatusLabel(runtime.status)], ["迭代", runtime.iteration], ["state_version", runtime.state_version], ["终止原因", runtime.terminal_reason]]),
      runtimeControlSurface(runtime, controlEvent),
    ])),
    ...(waitingInputSurface ? [waitingInputSurface] : []),
    ...(learningReference ? [learningRuntimeStatusSurface(learningReference)] : []),
    section("Goal / Plan", "只展示 Runtime 已持久化的目标契约与计划身份，不推断未返回的计划节点依赖。", el("div", { class: "debug-grid" }, [
      kvSurface("Goal 契约", [["目标", runtime.goal || goalContract.objective], ["Goal 版本", runtime.goal_version || goalContract.version], ["成功标准", goalContract.success_criteria], ["所需能力", goalContract.required_capabilities], ["来源", goalContract.source]]),
      kvSurface("Plan 身份", [["Plan ID", runtime.plan_id], ["版本", runtime.plan_version], ["节点 checkpoint", nodes.length], ["子运行", Array.isArray(runtime.children) ? runtime.children.length : 0], ["启动模式", runtime.launch_decision?.mode], ["启动原因", runtime.launch_decision?.reason]]),
    ])),
    section("预算与交接", "展示 Runtime 的硬预算以及 Runtime → Legacy 的交接结果；字段不存在时明确显示未报告。", el("div", { class: "debug-grid" }, [runtimeBudgetSurface(runtime), runtimeHandoffSurface(handoff)])),
    section("Node 状态", "按 Runtime checkpoint 展示每个节点的状态、尝试次数和副作用状态。", runtimeNodeSurface(runtime)),
    section("子运行", "展示 Runtime 已记录的子运行状态及其父节点关系。", runtimeChildrenSurface(runtime)),
  );
}

function section(title, description, content) { return el("section", { class: "debug-section" }, [el("h2", { text: title }), el("p", { text: description }), content]); }
function jsonSurface(title, value) { const pre = el("pre", { class: "code-view" }); renderJson(pre, value); return el("article", { class: "debug-surface" }, [el("h3", { text: title }), pre]); }
function kvSurface(title, rows) { const dl = el("dl", { class: "kv-list" }); rows.forEach(([key, value]) => dl.append(el("div", { class: "kv-row" }, [el("dt", { text: key }), el("dd", { text: Array.isArray(value) ? value.join("、") || "—" : value ?? "—" })]))); return el("article", { class: "debug-surface" }, [el("h3", { text: title }), dl]); }
function summaryCell(label, value) { return el("div", { class: "summary-cell" }, [el("span", { text: label }), el("strong", { text: value ?? "—" })]); }

function renderSummary(data) {
  const overview = data.overview || {}; const retrieval = data.retrieval || {}; const workflow = data.workflow || {}; const runtime = data.runtime || {};
  $("#execution-summary").replaceChildren(summaryCell("任务", overview.title || data.task.id), summaryCell("状态", overview.status_label || data.task.status), summaryCell("Runtime", runtimeStatusLabel(runtime.status)), summaryCell("证据", `${retrieval.used_evidence_ids?.length || 0} / ${retrieval.final_evidence?.length || 0}`), summaryCell("执行方式", overview.provider_label || workflow.provider), summaryCell("总耗时", `${data.performance?.total_ms || 0} ms`));
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

function renderAll(data) { execution = data; renderSummary(data); renderOverview(data); renderRuntime(data); loadLearningRuntimeStatus(data); loadLearningRuntimeControls(data); renderRoute(data); renderRetrieval(data); renderWorkflow(data); renderCitation(data); renderPerformance(data); $("#execution-console").hidden = false; }

function stopRuntimePolling() {
  runtimePollToken += 1;
  if (runtimePollTimer) window.clearTimeout(runtimePollTimer);
  runtimePollTimer = null;
  runtimePollAttempts = 0;
}

function runtimeNeedsPolling(data) {
  return runtimePollStatuses.has(runtimeStatusKey(data?.runtime?.status));
}

function scheduleRuntimePolling(id, data, token) {
  if (token !== runtimePollToken || !runtimeNeedsPolling(data) || runtimePollAttempts >= runtimePollDelaysMs.length) return;
  const delay = runtimePollDelaysMs[runtimePollAttempts];
  runtimePollTimer = window.setTimeout(async () => {
    runtimePollTimer = null;
    if (token !== runtimePollToken) return;
    runtimePollAttempts += 1;
    try {
      const latest = await api(`/api/v1/debug/execution/${encodeURIComponent(id)}`);
      if (token !== runtimePollToken) return;
      renderAll(latest);
      if (runtimeNeedsPolling(latest)) scheduleRuntimePolling(id, latest, token);
      else stopRuntimePolling();
    } catch (error) {
      if (token === runtimePollToken) scheduleRuntimePolling(id, data, token);
    }
  }, delay);
}

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
  stopRuntimePolling();
  const requestToken = runtimePollToken;
  const id = $("#task-id").value.trim(); if (!id) { $("#execution-notice").replaceChildren(el("div", { class: "notice warning", text: "请先输入一个真实任务 ID。" })); return; }
  $("#load-execution").disabled = true; $("#execution-notice").replaceChildren(el("div", { class: "loading-state", text: "正在载入统一执行链…" }));
  try { const data = await api(`/api/v1/debug/execution/${encodeURIComponent(id)}`); if (requestToken !== runtimePollToken) return; renderAll(data); $("#execution-notice").replaceChildren(); localStorage.setItem("xinzhi_last_task", id); scheduleRuntimePolling(id, data, requestToken); }
  catch (error) { $("#execution-notice").replaceChildren(el("div", { class: "error-state", text: error.message })); }
  finally { $("#load-execution").disabled = false; }
}

window.addEventListener("DOMContentLoaded", () => {
  initShell({ page: "execution", title: "执行调试", description: "路由、RAG、工作流、引用与性能" });
  loadMetrics();
  const query = new URLSearchParams(location.search); $("#task-id").value = query.get("task_id") || localStorage.getItem("xinzhi_last_task") || "";
  all("[data-tab-target]").forEach((button) => button.addEventListener("click", () => { all("[data-tab-target]").forEach((item) => item.classList.toggle("active", item === button)); all("[data-tab-panel]").forEach((panel) => { panel.hidden = panel.dataset.tabPanel !== button.dataset.tabTarget; }); }));
  $("#load-execution").addEventListener("click", loadExecution); $("#task-id").addEventListener("keydown", (event) => { if (event.key === "Enter") loadExecution(); });
  all("[data-runtime-action]").forEach((button) => button.addEventListener("click", () => executeRuntimeControl(button.dataset.runtimeAction)));
  if (location.pathname === "/debug/rag") document.querySelector('[data-tab-target="retrieval"]').click();
  if ($("#task-id").value) loadExecution();
});
