const { $, all, api, badge, el, initShell, renderMarkdown, toast } = XinzhiUI;
const params = new URLSearchParams(location.search);
const state = {
  mode: params.get("mode") === "solve" ? "solve" : "learn",
  sessionId: localStorage.getItem("xinzhi_student_session") || "",
  userId: localStorage.getItem("xinzhi_student_user") || `student_${crypto.randomUUID()}`,
  taskId: "", activeCourse: params.get("course") || localStorage.getItem("xinzhi_student_course") || "CT",
  lastQuestion: "", lastAnswer: "",
  activeTaskWait: null,
  runSequence: 0,
};
let runtimeTaskControls = null;
let runtimeTaskControlsRequest = 0;
let runtimeTaskControlsBusy = false;
const runtimeTaskStatusLabels = {
  created: "已创建",
  queued: "等待执行",
  running: "正在执行",
  paused: "已暂停",
  waiting_input: "等待补充信息",
  waiting_approval: "等待人工审批",
  completed: "已完成",
  failed: "执行失败",
  cancelled: "已取消",
};
localStorage.setItem("xinzhi_student_user", state.userId);

function ensureRuntimeTaskControlsMarkup() {
  if (document.querySelector("#student-runtime-controls")) return;
  const sourceDetails = document.querySelector("#source-details");
  if (!sourceDetails) return;
  const panel = document.createElement("section");
  panel.id = "student-runtime-controls";
  panel.className = "student-runtime-controls";
  panel.hidden = true;
  panel.setAttribute("aria-labelledby", "student-runtime-controls-title");
  panel.innerHTML = `<header><div><span class="eyebrow">Agent Runtime</span><h3 id="student-runtime-controls-title">任务需要继续操作</h3></div><span id="student-runtime-status" class="runtime-task-status" role="status">正在读取状态</span></header><p id="student-runtime-controls-message">控制能力由服务端 Runtime checkpoint 决定。</p><div class="student-runtime-actions"><button id="student-runtime-pause" class="button secondary" type="button" hidden>暂停</button><button id="student-runtime-resume" class="button secondary" type="button" hidden>恢复</button><button id="student-runtime-approve" class="button" type="button" hidden>提交审批</button><button id="student-runtime-reject-proposal" class="text-button" type="button" hidden>拒绝恢复计划</button></div><form id="student-runtime-input-form" class="student-runtime-input" hidden><label for="student-runtime-input">请补充必要信息</label><textarea id="student-runtime-input" maxlength="4000" rows="3" placeholder="请勿填写密码、密钥或其他敏感信息。"></textarea><div><button id="student-runtime-submit-input" class="button" type="submit">提交并继续</button></div></form>`;
  sourceDetails.before(panel);
}

function selectedCourse() { const value = $("#course-select").value; return value === "AUTO" ? state.activeCourse : value; }
async function ensureSession(force = false) {
  if (state.sessionId && !force) return state.sessionId;
  const session = await api("/api/v1/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: state.userId, course_id: selectedCourse(), title: "学生学习会话" }) });
  state.sessionId = session.id; localStorage.setItem("xinzhi_student_session", session.id); return session.id;
}
function setMode(mode) {
  state.mode = mode;
  all("[data-mode]").forEach((item) => item.classList.toggle("active", item.dataset.mode === mode));
  $("#image-label").hidden = mode !== "solve";
  $("#question-input").placeholder = mode === "solve" ? "输入完整电路题，或上传一张清晰题目图片" : "输入课程问题；Shift+Enter 换行";
  updateShell();
}
function updateShell() {
  const course = selectedCourse();
  const name = { CT: "电路理论", AE: "模拟电子技术", DE: "数字电子技术" }[course] || "自动识别";
  const top = $(".topbar-context"); if (top) top.textContent = `${state.mode === "solve" ? "电路解题" : "知识问答"} · ${name}`;
}
function addMessage(text, kind = "user") {
  $("#welcome").hidden = true;
  $("#messages").append(el("article", { class: `conversation-message ${kind}` }, [el("span", { class: "message-role", text: kind === "user" ? "你" : "系统" }), el("p", { text })]));
}
function imageUrl(uri) {
  if (!String(uri).startsWith("kb-image://")) return "";
  const rest = uri.slice(11); const slash = rest.indexOf("/"); if (slash < 0) return "";
  return `/api/v1/knowledge/images/${encodeURIComponent(rest.slice(0, slash))}/${rest.slice(slash + 1).split("/").map(encodeURIComponent).join("/")}`;
}
function externalSourceUrl(item) {
  const direct = String(item?.url || item?.canonical_url || item?.source_ref || "").trim();
  if (/^https?:\/\//i.test(direct)) return direct;
  const doi = String(item?.doi || direct.match(/^(?:doi:)?(10\.\d{4,9}\/\S+)$/i)?.[1] || "")
    .replace(/^https?:\/\/doi\.org\//i, "")
    .replace(/^doi:/i, "");
  if (doi) return `https://doi.org/${encodeURIComponent(doi)}`;
  const arxiv = String(item?.arxiv_id || direct.match(/^arxiv:(.+)$/i)?.[1] || "")
    .replace(/^https?:\/\/arxiv\.org\/(?:abs|pdf)\//i, "")
    .replace(/^arxiv:/i, "")
    .replace(/\.pdf$/i, "");
  return arxiv ? `https://arxiv.org/abs/${encodeURIComponent(arxiv)}` : "";
}
function studentSourceIdentityKeys(item) {
  const keys = [];
  const evidenceId = String(item?.evidence_id || "").trim().toLowerCase();
  if (evidenceId) keys.push(`evidence:${evidenceId}`);
  const sourceRef = String(item?.source_ref || item?.source_uri || "").trim().toLowerCase();
  if (sourceRef) keys.push(`source:${sourceRef}`);
  const url = String(externalSourceUrl(item) || "")
    .trim()
    .toLowerCase()
    .replace(/#.*$/, "")
    .replace(/\/$/, "");
  if (url) keys.push(`url:${url}`);
  if (sourceRef && !url) keys.push(`source:${sourceRef}`);
  if (!keys.length) {
    const title = String(item?.title || "").trim().toLowerCase().replace(/\s+/g, " ");
    if (title) keys.push(`title:${title}`);
  }
  return keys;
}
function mergeStudentSources(...groups) {
  const seen = new Set();
  return groups.flatMap((group) => Array.isArray(group) ? group : []).filter((item) => {
    if (!item || typeof item !== "object") return false;
    const keys = studentSourceIdentityKeys(item);
    if (!keys.length || keys.some((key) => seen.has(key))) return false;
    keys.forEach((key) => seen.add(key));
    return true;
  });
}
function sourceCard(hit, course) {
  const card = el("article", { class: "source-card" });
  const sourceRef = String(hit.source_ref || hit.source_uri || "").trim();
  const isLocal = sourceRef.startsWith("kb://");
  const externalUrl = isLocal ? "" : externalSourceUrl(hit);
  const provider = String(hit.provider || "").trim().toLowerCase();
  const isMock = hit.metadata?.mock === true || provider === "mock" || provider === "development_mock";
  const sourceType = isLocal
    ? "本地课程资料"
    : isMock
      ? "开发态 Mock · 非真实来源"
      : externalUrl
        ? "外部来源 · 请打开原文核验"
        : "来源路径不可用";
  const heading = el("div", { class: "source-card-heading" }, [
    el("strong", { text: hit.title || hit.chapter || "课程资料" }),
    badge("ready", isLocal ? (hit.course_id || course || "课程") : (hit.source_type || "外部来源")),
  ]);
  const excerpt = el("div", { class: "source-card-excerpt" });
  renderMarkdown(excerpt, hit.snippet || hit.content_excerpt || hit.text_preview || hit.content || hit.chapter || "已用于本次回答的课程证据。", { preserveRaw: true });
  card.append(heading, excerpt, el("small", { class: isMock ? "source-provenance mock" : "source-provenance", text: sourceType }));
  const meta = [hit.chapter, hit.content_type].filter(Boolean).join(" · "); if (meta) card.append(el("small", { text: meta }));
  if (externalUrl) {
    card.append(el("a", { class: "source-open", href: externalUrl, target: "_blank", rel: "noopener noreferrer", text: "打开原文" }));
  } else if (sourceRef) {
    card.append(el("code", { class: "source-ref", text: sourceRef }));
  } else {
    card.append(el("small", { text: "无法打开原文" }));
  }
  return card;
}
function renderResult(task) {
  const result = task.result_content || {}; const structured = result.structured_result || {}; const knowledge = structured.knowledge || {}; const hits = Array.isArray(knowledge.hits) ? knowledge.hits : result.citations || [];
  const externalItems = Array.isArray(structured.external_retrieval?.items) ? structured.external_retrieval.items : [];
  const sources = mergeStudentSources(hits, externalItems);
  state.lastAnswer = result.math_content?.markdown || result.structured_result?.math_content?.markdown || result.answer || task.error_message || "未返回回答";
  $("#answer-panel").hidden = false; $("#answer-agent").textContent = task.agent_id || "统一运行框架";
  const taskStatus = String(task.status || "").toLowerCase();
  const statusBadge = badge(taskStatus === "completed" ? (result.fallback_used ? "degraded" : "success") : taskStatus === "cancelled" ? "cancelled" : "failed", taskStatus === "completed" ? (result.fallback_used ? "降级完成" : "已完成") : taskStatus === "cancelled" ? "已停止" : "未完成");
  statusBadge.id = "answer-status"; $("#answer-status").replaceWith(statusBadge);
  const courseName = { CT: "电路理论", AE: "模拟电子技术", DE: "数字电子技术" }[task.course_id || selectedCourse()] || task.course_id || "课程";
  $("#answer-route").textContent = `${state.mode === "solve" ? "电路解题" : "知识问答"} · ${courseName}`;
  renderMarkdown($("#answer-text"), state.lastAnswer);
  const notices = [];
  if (result.provider === "mock" || result.mock_used) notices.push({ status: "mock", text: "当前为开发态 Mock 结果，不代表正式云端工作流输出。" });
  if (result.fallback_used) notices.push({ status: "degraded", text: `云端服务暂不可用，本次回答由本地知识库生成。${result.fallback_reason ? ` 原因：${result.fallback_reason}` : ""}` });
  (result.warnings || []).filter((item) => !String(item).includes("mock_result")).forEach((item) => notices.push({ status: "warning", text: item }));
  $("#answer-notices").replaceChildren(...notices.map((item) => el("div", { class: `notice ${item.status}`, text: item.text })));
  $("#source-summary").textContent = `资料依据 ${sources.length}`;
  $("#source-list").replaceChildren(...(sources.length ? sources.map((hit) => sourceCard(hit, task.course_id)) : [el("div", { class: "empty-state", text: "本次回答没有可展示的资料依据。" })]));
  const images = $("#show-images").checked ? (result.related_images || []) : [];
  $("#related-images").replaceChildren(...images.map((item) => { const src = imageUrl(item.resource_uri); return src ? el("figure", { class: "image-thumbnail" }, [el("img", { src, alt: item.caption || "相关教材图片", loading: "lazy" }), el("figcaption", { text: item.caption || "相关教材图片" })]) : null; }).filter(Boolean));
  $("#answer-panel").scrollIntoView({ behavior: "smooth", block: "nearest" });
}
function runtimeTaskControlEntry(action) {
  const controls = Array.isArray(runtimeTaskControls?.controls)
    ? runtimeTaskControls.controls
    : [];
  return controls.find((item) => item?.action === action) || null;
}
function runtimeApprovalAllowed() {
  return false;
}

function runtimeTaskControlAvailable(action) {
  if (action === "approve" || action === "reject") {
    return runtimeApprovalAllowed();
  }
  return runtimeTaskControlEntry(action)?.available === true;
}
function runtimeTaskControlMessage(projection) {
  if (String(projection?.status || "").toLowerCase() === "waiting_approval") {
    return "Teacher or administrator approval is required; the task will continue from its checkpoint after review.";
  }
  if (!projection?.runtime_run_id) return "当前任务尚未进入可控制的 Runtime。";
  if (projection.control_scope === "runtime_plan_proposal" && projection.plan_proposal?.proposal_id) {
    return "Runtime 生成了恢复计划，需要明确应用或拒绝后才能继续。";
  }
  const available = ["pause", "resume", "approve", "input"].filter(runtimeTaskControlAvailable);
  if (available.length) return "可用操作由服务端 checkpoint 和任务状态决定；提交后会从同一运行断点继续。";
  const blocked = ["pause", "resume", "approve", "input"].map(runtimeTaskControlEntry).find((item) => item?.reason);
  return blocked?.reason || "当前 Runtime 状态没有可执行的人工控制操作。";
}
function renderRuntimeTaskControls() {
  const panel = $("#student-runtime-controls");
  if (!panel) return;
  const projection = runtimeTaskControls;
  const hasRuntime = Boolean(projection?.runtime_run_id);
  panel.hidden = !hasRuntime;
  if (!hasRuntime) return;
  $("#answer-panel").hidden = false;
  $("#answer-agent").textContent = projection.agent_id || "统一运行框架";
  $("#answer-status").textContent = runtimeTaskStatusLabels[String(projection.status || "").toLowerCase()] || "状态待确认";
  $("#student-runtime-status").textContent = runtimeTaskStatusLabels[String(projection.status || "").toLowerCase()] || "状态待确认";
  $("#student-runtime-controls-message").textContent = runtimeTaskControlMessage(projection);
  const proposalPending = Boolean(projection.control_scope === "runtime_plan_proposal" && projection.plan_proposal?.proposal_id);
  ["pause", "resume", "approve"].forEach((action) => {
    const button = $(`#student-runtime-${action}`);
    if (!button) return;
    const entry = runtimeTaskControlEntry(action);
    const available = proposalPending && action === "approve"
      ? runtimeApprovalAllowed()
      : runtimeTaskControlAvailable(action);
    button.hidden = !available;
    button.disabled = runtimeTaskControlsBusy || !available;
    if (proposalPending && action === "approve") button.textContent = "应用恢复计划";
    button.title = available ? "" : `${entry?.reason_code || "runtime_control_unavailable"}: ${entry?.reason || "当前状态不可用"}`;
  });
  const reject = $("#student-runtime-reject-proposal");
  if (reject) {
    reject.hidden = !proposalPending || !runtimeApprovalAllowed();
    reject.disabled = runtimeTaskControlsBusy || !proposalPending || !runtimeApprovalAllowed();
  }
  const inputAvailable = runtimeTaskControlAvailable("input");
  $("#student-runtime-input-form").hidden = !inputAvailable;
  $("#student-runtime-submit-input").disabled = runtimeTaskControlsBusy || !inputAvailable;
}
async function refreshRuntimeTaskControls(taskId = state.taskId) {
  if (!taskId) {
    runtimeTaskControls = null;
    renderRuntimeTaskControls();
    return null;
  }
  const requestSequence = runtimeTaskControlsRequest + 1;
  runtimeTaskControlsRequest = requestSequence;
  try {
    const projection = await api(`/api/v1/tasks/${encodeURIComponent(taskId)}/runtime-controls`);
    if (requestSequence !== runtimeTaskControlsRequest) return null;
    runtimeTaskControls = projection;
    renderRuntimeTaskControls();
    return projection;
  } catch (_error) {
    if (requestSequence !== runtimeTaskControlsRequest) return null;
    runtimeTaskControls = null;
    renderRuntimeTaskControls();
    return null;
  }
}
function runtimeTaskControlUrl(action) {
  const taskId = encodeURIComponent(state.taskId || "");
  const runId = String(runtimeTaskControls?.runtime_run_id || "").trim();
  if (runtimeTaskControls?.control_scope === "runtime_plan_proposal" && runtimeTaskControls?.plan_proposal?.proposal_id) {
    return `/api/v1/tasks/${taskId}/runtime-plan-proposals/${encodeURIComponent(runtimeTaskControls.plan_proposal.proposal_id)}/decision`;
  }
  return `/api/v1/tasks/${taskId}/${action}${runId ? `?runtime_run_id=${encodeURIComponent(runId)}` : ""}`;
}
async function submitRuntimeTaskControl(action, payload = null) {
  if (!state.taskId || !runtimeTaskControlAvailable(action)) return;
  runtimeTaskControlsBusy = true;
  renderRuntimeTaskControls();
  try {
    const planProposalControl = runtimeTaskControls?.control_scope === "runtime_plan_proposal";
    const options = { method: "POST", headers: { "Content-Type": "application/json" } };
    if (planProposalControl) {
      options.body = JSON.stringify({
        decision: action === "approve" ? "approved" : "rejected",
        reason: payload?.reason || "",
        expected_state_version: runtimeTaskControls?.plan_proposal?.state_version,
      });
    } else if (action === "input") {
      options.body = JSON.stringify({
        expected_state_version: runtimeTaskControls?.state_version,
        data: payload || {},
      });
    } else if (payload) {
      options.body = JSON.stringify(payload);
    }
    await api(runtimeTaskControlUrl(action), options);
    if (action === "input") $("#student-runtime-input").value = "";
    await refreshRuntimeTaskControls(state.taskId);
  } catch (error) {
    $("#student-runtime-controls-message").textContent = Number(error?.status) === 403
      ? "当前身份无权执行此审批操作，请交由教师或责任人处理。"
      : Number(error?.status) === 409
        ? "Runtime 状态已变化，正在重新读取最新状态。"
        : error?.message || "Runtime 控制操作未完成。";
    await refreshRuntimeTaskControls(state.taskId);
  } finally {
    runtimeTaskControlsBusy = false;
    renderRuntimeTaskControls();
  }
}
async function submitRuntimeTaskInput(event) {
  event.preventDefault();
  const text = $("#student-runtime-input").value.trim();
  if (!text) {
    $("#student-runtime-input").focus();
    return;
  }
  await submitRuntimeTaskControl("input", { text });
}

async function uploadImage() {
  const file = $("#image-input").files[0]; if (!file) return null;
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) throw new Error("仅支持 JPG、PNG 或 WebP 图片");
  if (file.size > 8 * 1024 * 1024) throw new Error("图片不能超过 8MB");
  const form = new FormData(); form.append("upload", file); form.append("purpose", "student_solver_image");
  return api("/api/v1/files", { method: "POST", body: form });
}
function attachmentRef(file) { return { file_id: file.id, filename: file.filename, content_type: file.content_type, size_bytes: file.size_bytes, storage_key: file.storage_key, checksum_sha256: file.checksum_sha256 }; }
async function waitForTask(id) {
  return new Promise((resolve, reject) => {
    let settled = false; let pollTimer = null; const events = new EventSource(`/api/v1/tasks/${id}/stream`);
    let waitHandle = null;
    const cleanup = () => {
      events.close();
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      if (state.activeTaskWait === waitHandle) state.activeTaskWait = null;
    };
    const cancel = () => { if (settled) return; settled = true; cleanup(); resolve(null); };
    waitHandle = { cancel };
    state.activeTaskWait = waitHandle;
    const finish = async () => {
      if (settled) return;
      try {
        const task = await api(`/api/v1/tasks/${id}`);
        void refreshRuntimeTaskControls(id);
        if (["completed", "failed", "cancelled"].includes(task.status)) {
          settled = true; cleanup(); resolve(task);
        }
      } catch (error) { settled = true; cleanup(); reject(error); }
    };
    void refreshRuntimeTaskControls(id);
    ["task.completed", "task.failed", "task.cancelled"].forEach((name) => events.addEventListener(name, finish));
    events.addEventListener("agent.started", () => { addMessage("已完成路由，正在生成回答…", "system"); void refreshRuntimeTaskControls(id); });
    events.addEventListener("agent.progress", () => { void refreshRuntimeTaskControls(id); });
    events.onerror = () => {
      if (settled || pollTimer) return;
      // Keep EventSource open so the browser retries and sends Last-Event-ID;
      // polling reconciles the public Runtime controls while reconnecting.
      void refreshRuntimeTaskControls(id);
      pollTimer = setInterval(finish, 900);
    };
  });
}
async function submit(event) {
  event.preventDefault(); $("#form-error").textContent = "";
  const requestSequence = state.runSequence + 1;
  state.runSequence = requestSequence;
  const question = $("#question-input").value.trim(); const course = selectedCourse();
  if (state.mode === "solve" && course !== "CT") { $("#form-error").textContent = "该课程完整解题工作流尚未开放"; return; }
  if (!question && !$("#image-input").files[0]) { $("#form-error").textContent = "请输入题目或上传图片"; return; }
  state.lastQuestion = question; $("#send-button").disabled = true; $("#stop-button").disabled = false;
  try {
    await ensureSession(); state.activeCourse = course; localStorage.setItem("xinzhi_student_course", course); if (question) addMessage(question);
    const file = state.mode === "solve" ? await uploadImage() : null;
    const payload = { session_id: state.sessionId, user_id: state.userId, user_role: "student", scene: state.mode === "solve" ? "solving" : "learning", course_id: course, intent: state.mode === "solve" ? "solve_problem" : "general_qa", canonical_input: { text: question }, attachments: file ? [attachmentRef(file)] : [], context_refs: [], options: { request_id: `student_${crypto.randomUUID()}`, response_depth: $("#depth-select").value } };
    const task = await api("/api/v1/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    state.taskId = task.id; addMessage("请求已提交，本地检索与专业工作流正在处理…", "system"); const finishedTask = await waitForTask(task.id); if (state.runSequence !== requestSequence) return; if (finishedTask) renderResult(finishedTask);
    $("#question-input").value = ""; clearImage();
  } catch (error) { if (state.runSequence === requestSequence) $("#form-error").textContent = `${error.message}。请检查本地服务后重试。`; }
  finally { if (state.runSequence === requestSequence) { state.taskId = ""; $("#send-button").disabled = false; $("#stop-button").disabled = true; } }
}
function clearImage() { $("#image-input").value = ""; $("#image-preview").hidden = true; $("#preview-image").removeAttribute("src"); $("#image-name").textContent = ""; }
function applyParams() {
  if (params.get("course")) $("#course-select").value = params.get("course");
  if (params.get("prompt")) $("#question-input").value = params.get("prompt");
  if (params.get("image") === "1") setMode("solve");
}
window.addEventListener("DOMContentLoaded", () => {
  ensureRuntimeTaskControlsMarkup();
  initShell({ page: "student", title: "智能学习", description: "课程问答与电路理论解题", context: "知识问答 · 电路理论" }); applyParams(); setMode(state.mode);
  all("[data-mode]").forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
  all("[data-prompt]").forEach((button) => button.addEventListener("click", () => { $("#question-input").value = button.dataset.prompt; $("#course-select").value = button.dataset.course; state.activeCourse = button.dataset.course; if (button.dataset.promptMode) setMode(button.dataset.promptMode); updateShell(); $("#question-input").focus(); }));
  $("#student-form").addEventListener("submit", submit);
  $("#question-input").addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("#student-form").requestSubmit(); } });
  $("#course-select").addEventListener("change", () => { if ($("#course-select").value !== "AUTO") state.activeCourse = $("#course-select").value; updateShell(); });
  $("#image-input").addEventListener("change", (event) => { const file = event.target.files[0]; if (!file) return clearImage(); $("#image-name").textContent = file.name; $("#preview-image").src = URL.createObjectURL(file); $("#image-preview").hidden = false; });
  $("#remove-image").addEventListener("click", clearImage);
  $("#stop-button").addEventListener("click", async () => { if (state.taskId) await api(`/api/v1/tasks/${state.taskId}/cancel`, { method: "POST" }); });
  $("#student-runtime-pause").addEventListener("click", () => submitRuntimeTaskControl("pause"));
  $("#student-runtime-resume").addEventListener("click", () => submitRuntimeTaskControl("resume"));
  $("#student-runtime-approve").addEventListener("click", () => submitRuntimeTaskControl("approve", {
    expected_state_version: runtimeTaskControls?.state_version,
  }));
  $("#student-runtime-reject-proposal").addEventListener("click", () => submitRuntimeTaskControl("reject", { reason: "student_rejected_runtime_plan_proposal" }));
  $("#student-runtime-input-form").addEventListener("submit", submitRuntimeTaskInput);
  $("#new-session").addEventListener("click", () => { state.activeTaskWait?.cancel(); state.runSequence += 1; state.sessionId = ""; state.taskId = ""; runtimeTaskControlsRequest += 1; runtimeTaskControls = null; renderRuntimeTaskControls(); localStorage.removeItem("xinzhi_student_session"); $("#messages").replaceChildren(); $("#answer-panel").hidden = true; $("#welcome").hidden = false; toast("已新建本地会话"); });
  $("#toggle-sources").addEventListener("click", () => { $("#source-details").open = !$("#source-details").open; });
  $("#copy-answer").addEventListener("click", async () => { await navigator.clipboard.writeText(state.lastAnswer); toast("回答已复制"); });
  $("#follow-up").addEventListener("click", () => { $("#question-input").focus(); $("#question-input").placeholder = "继续追问这一回答…"; });
  $("#reask").addEventListener("click", () => { $("#question-input").value = state.lastQuestion; $("#question-input").focus(); });
});
