const { $, all, api, el, initShell, renderMarkdown, toast } = XinzhiUI;
const params = new URLSearchParams(location.search);
const courseLabels = { CT: "电路理论", AE: "模拟电子技术", DE: "数字电子技术" };
const taskLabels = { explain_concept: "知识问答", general_qa: "知识问答", solve_problem: "电路解题", lesson_prep: "教案设计", assignment_review: "作业批改", academic_writing: "学术写作", data_analysis: "数据分析" };
const intentLabels = { unknown: "自动识别", explain_concept: "概念解释", general_qa: "知识问答", solve_problem: "电路分析", lesson_prep: "教案设计", assignment_review: "作业初审", academic_writing: "学术写作", data_analysis: "数据分析" };
const ragLabels = { grounded_generation: "课程资料支撑", method_reference: "方法参考", reference_only: "资料参考", user_sources_only: "用户材料", data_context_only: "数据上下文", no_rag: "无需课程检索" };
const state = {
  sessionId: localStorage.getItem("xinzhi_student_session") || "",
  userId: localStorage.getItem("xinzhi_student_user") || `student_${crypto.randomUUID()}`,
  taskId: "",
  activeCourse: params.get("course") || localStorage.getItem("xinzhi_student_course") || "AUTO",
  lastQuestion: "",
  lastAnswer: "",
  evidence: [],
  currentTask: null,
  archivedTaskIds: new Set(),
};
localStorage.setItem("xinzhi_student_user", state.userId);

function selectedCourse() {
  return $("#course-select").value;
}

async function ensureSession(force = false) {
  if (state.sessionId && !force) return state.sessionId;
  const session = await api("/api/v1/sessions", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: state.userId, course_id: state.activeCourse === "AUTO" ? "CT" : state.activeCourse, title: "统一任务会话" }),
  });
  state.sessionId = session.id;
  localStorage.setItem("xinzhi_student_session", session.id);
  return session.id;
}

function updateShell() {
  const course = selectedCourse();
  const top = $(".topbar-context");
  if (top) top.textContent = `自动调度 · ${courseLabels[course] || "课程自动识别"}`;
}

function scrollConversationToEnd(behavior = "smooth") {
  const conversation = $("#conversation");
  requestAnimationFrame(() => conversation.scrollTo({ top: conversation.scrollHeight, behavior }));
}

function addMessage(text, kind = "user", taskId = "") {
  $("#welcome").hidden = true;
  const attrs = { class: `conversation-message ${kind}` };
  if (taskId) attrs["data-task-id"] = taskId;
  $("#messages").append(el("article", attrs, [
    el("span", { class: "message-role", text: kind === "user" ? "你" : "进度" }),
    el("p", { text }),
  ]));
  scrollConversationToEnd();
}

function taskQuestion(task) {
  if (task?.question) return task.question;
  const canonical = task?.input_content?.canonical_input || {};
  return canonical.text || canonical.question || canonical.problem || canonical.query || "已提交材料任务";
}

function resultForTask(task) {
  if (task?.result_content) return task.result_content;
  return {
    provider: task?.provider || "local",
    answer: task?.answer || task?.error_message || "",
    fallback_used: Boolean(task?.fallback_used),
    fallback_reason: task?.fallback_reason || "",
    structured_result: {},
  };
}

function presentationFor(task, result) {
  const structured = result.structured_result || {};
  const summary = structured.execution_summary || {};
  const raw = structured.presentation || legacyPresentation(task, result);
  const fallback = Boolean(summary.fallback || result.fallback_used);
  if (!fallback) return raw;
  const reason = summary.fallback_reason || result.fallback_reason || "";
  const count = Number(summary.evidence_count || 0);
  const messages = {
    cloud_opt_out: "已按本地优先策略处理，本次未调用星辰工作流。",
    xingchen_response_parse_error: "云端结果格式校验未通过，本次已切换到本地安全后备结果。",
    provider_timeout: "云端响应超时，本次已切换到本地安全后备结果。",
    xingchen_timeout: "云端响应超时，本次已切换到本地安全后备结果。",
    not_configured: "该云端能力尚未配置，本次已切换到本地安全后备结果。",
  };
  return {
    ...raw,
    provider_label: "本地安全后备",
    fallback_message: messages[reason] || "云端主能力本次未完成，已切换到本地安全后备结果。",
    source_summary: count ? `已检索 ${count} 条课程资料` : raw.source_summary,
    evidence_message: count ? "资料检索已完成，但后备结果未将其声明为直接生成依据" : raw.evidence_message,
  };
}

function displayAnswer(task, result) {
  const structured = result.structured_result || {};
  const mathContent = result.math_content || structured.math_content;
  const answer = mathContent?.markdown || result.answer || task.error_message || "未返回回答";
  if (answer === "云端工作流暂不可用，已返回本地结构化模板。") {
    return [
      "## 历史任务说明",
      "",
      "> 该任务执行于本次修复之前，旧版本只保存了降级占位文本，并未生成实际教案。",
      "",
      "请点击“重新提问”使用新版的本地可编辑教案框架；已检索资料仍可在右侧查看。",
    ].join("\n");
  }
  return answer;
}

function archiveTaskAnswer(task) {
  if (!task?.id || state.archivedTaskIds.has(task.id)) return;
  const result = resultForTask(task);
  const answer = displayAnswer(task, result);
  const presentation = presentationFor(task, result);
  const body = el("div", { class: "message-body" }, [
    el("span", { class: "message-meta", text: `${presentation.title || "任务结果"} · ${presentation.status_label || task.status}` }),
    el("div", { class: "markdown-view" }),
  ]);
  renderMarkdown(body.lastElementChild, answer);
  $("#messages").append(el("article", { class: "conversation-message assistant", "data-task-id": task.id }, [
    el("span", { class: "message-role", text: "芯智导学" }), body,
  ]));
  state.archivedTaskIds.add(task.id);
}

function archiveCurrentAnswer() {
  if (!state.currentTask || $("#answer-panel").hidden) return;
  archiveTaskAnswer(state.currentTask);
  $("#answer-panel").hidden = true;
}

function imageUrl(uri) {
  if (!String(uri).startsWith("kb-image://")) return "";
  const rest = uri.slice(11); const slash = rest.indexOf("/");
  if (slash < 0) return "";
  return `/api/v1/knowledge/images/${encodeURIComponent(rest.slice(0, slash))}/${rest.slice(slash + 1).split("/").map(encodeURIComponent).join("/")}`;
}

function setContextOpen(open = true) {
  document.body.classList.toggle("context-closed", !open);
  $("#toggle-context").setAttribute("aria-expanded", String(open));
}

function selectContextTab(name) {
  all("[data-context-tab]").forEach((button) => button.classList.toggle("active", button.dataset.contextTab === name));
  all("[data-context-view]").forEach((view) => {
    const active = view.dataset.contextView === name;
    view.hidden = !active; view.classList.toggle("active", active);
  });
  setContextOpen(true);
}

function openImage(src, caption) {
  if (!src) return;
  $("#dialog-image").src = src; $("#dialog-caption").textContent = caption || "课程资料图片";
  $("#image-dialog").showModal();
}

function evidenceCard(item) {
  const role = item.role === "method_reference" ? "方法参考" : item.used_by_answer ? "已引用" : item.entered_workflow ? "进入上下文" : "补充阅读";
  const card = el("button", { type: "button", class: "evidence-card", "data-evidence-id": item.evidence_id });
  card.append(
    el("div", { class: "evidence-card-header" }, [el("span", { class: "evidence-id", text: item.evidence_id }), el("span", { class: "evidence-role", text: role })]),
    el("h3", { text: item.title || item.chapter || "课程资料" }),
    el("small", { text: [courseLabels[item.course_id] || item.course_name, item.chapter, item.content_type].filter(Boolean).join(" · ") }),
    el("p", { text: item.summary || "本条资料没有可展示摘要。" }),
  );
  const images = (item.related_images || []).map((image) => ({ image, src: imageUrl(image.resource_uri) })).filter((entry) => entry.src);
  if (images.length) {
    const row = el("div", { class: "evidence-images" });
    images.forEach(({ image, src }) => row.append(el("button", { type: "button", onclick: (event) => { event.stopPropagation(); openImage(src, image.caption || item.title); } }, el("img", { src, loading: "lazy", alt: image.caption || item.title }))));
    card.append(row);
  }
  card.addEventListener("click", () => focusEvidence(item.evidence_id));
  return card;
}

function focusEvidence(id) {
  selectContextTab("evidence");
  all("[data-evidence-id]").forEach((card) => card.classList.toggle("active", card.dataset.evidenceId === id));
  const active = $(`[data-evidence-id="${CSS.escape(id)}"]`);
  active?.scrollIntoView({ behavior: "smooth", block: "center" });
}

function renderEvidence(items, presentation) {
  state.evidence = items || [];
  $("#context-evidence").replaceChildren(...(state.evidence.length ? state.evidence.map(evidenceCard) : [el("div", { class: "context-empty" }, [el("strong", { text: "本次没有可展示的课程依据" }), el("p", { text: presentation?.evidence_message || "系统不会把未使用的候选资料显示为回答依据。" })]) ]));
}

function renderProcess(steps = []) {
  const list = el("div", { class: "process-list" });
  (steps.length ? steps : [{ label: "等待任务执行", status: "skipped" }]).forEach((step) => list.append(el("div", { class: `process-step ${step.status || "completed"}` }, [el("span", { class: "process-dot" }), el("div", {}, [el("strong", { text: step.label }), el("span", { text: ({ completed: "已完成", passed: "验证通过", failed: "需要检查", fallback: "已降级", skipped: "本次未执行" })[step.status] || step.status })])])));
  $("#context-process").replaceChildren(list);
}

function renderInfo(task, result, summary, presentation, renderMs = 0) {
  const collaboration = result.provider === "local_agent" ? "内部 Agent 协作" : result.provider === "local" ? "本地知识增强" : result.provider === "mock" ? "开发演示" : "智能协作";
  const rows = [
    ["完成能力", presentation.title || summary.agent_label || "智能任务"],
    ["协作方式", collaboration],
    ["课程", courseLabels[task.course_id] || task.course_id],
    ["任务类型", intentLabels[task.intent] || "自动识别"],
    ["知识增强", ragLabels[summary.rag_mode] || "按需启用"],
    ["资料使用", `${summary.used_evidence_count || 0} / ${summary.evidence_count || 0} 条`],
    ["结果检查", summary.citation_status === "passed" ? "通过" : summary.citation_status === "failed" ? "需要复核" : "已完成结构检查"],
    ["后备能力", summary.fallback ? "已启用" : "未启用"],
    ["检索耗时", `${(summary.timings?.retrieval_ms || 0)} ms`],
    ["生成耗时", `${(summary.timings?.model_ms || summary.timings?.cloud_ms || 0)} ms`],
    ["总耗时", `${(summary.timings?.total_ms || result.metrics?.latency_ms || 0)} ms`],
    ["前端渲染", `${renderMs.toFixed(1)} ms`],
  ];
  const dl = el("dl", { class: "info-list" });
  rows.forEach(([key, value]) => dl.append(el("div", { class: "info-row" }, [el("dt", { text: key }), el("dd", { text: value })])));
  $("#context-info").replaceChildren(dl);
}

function legacyPresentation(task, result) {
  const fallback = Boolean(result.fallback_used); const mock = result.provider === "mock" || result.mock_used;
  return {
    title: `${taskLabels[task.intent] || "专业任务"} · ${courseLabels[task.course_id] || task.course_id}`,
    status_label: mock ? "开发演示" : fallback ? "降级完成" : "已完成",
    source_summary: `课程资料 ${(result.citations || []).length}`,
    provider_label: mock ? "开发态 Mock" : fallback ? "安全后备能力" : result.provider === "local_agent" ? "内部 Agent 协作" : "智能协作",
    fallback_message: fallback ? "主能力暂不可用，本次已切换到安全后备能力。" : "",
    evidence_message: "当前任务使用旧响应格式。",
    execution_steps: [],
  };
}

function renderResult(task) {
  const renderStarted = performance.now();
  const result = task.result_content || {}; const structured = result.structured_result || {};
  const presentation = presentationFor(task, result);
  const summary = structured.execution_summary || {};
  const evidence = structured.evidence_view || [];
  state.lastAnswer = displayAnswer(task, result);
  state.currentTask = task;
  $("#answer-panel").hidden = false;
  $("#answer-status").textContent = presentation.status_label || "已完成";
  $("#answer-title").textContent = presentation.title;
  $("#answer-source-chip").textContent = presentation.source_summary;
  $("#context-task-title").textContent = presentation.title;
  renderMarkdown($("#answer-text"), state.lastAnswer);
  renderBusinessView(structured.business_view || {});
  const notices = [];
  if (summary.mock || result.provider === "mock" || result.mock_used) notices.push({ status: "mock", text: "当前为开发态模拟结果，不代表正式智能能力输出。" });
  if (presentation.fallback_message) notices.push({ status: "warning", text: presentation.fallback_message });
  if (presentation.evidence_message) notices.push({ status: "", text: presentation.evidence_message });
  $("#answer-notices").replaceChildren(...notices.map((item) => el("div", { class: `notice ${item.status}`, text: item.text })));
  renderEvidence(evidence, presentation); renderProcess(presentation.execution_steps || []);
  const renderMs = performance.now() - renderStarted; localStorage.setItem("xinzhi_last_render_ms", renderMs.toFixed(1));
  renderInfo(task, result, summary, presentation, renderMs);
  $("#answer-panel").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadSessionHistory() {
  if (!state.sessionId) return;
  try {
    const tasks = await api(`/api/v1/sessions/${state.sessionId}/tasks?limit=50`);
    if (!tasks.length) return;
    $("#welcome").hidden = true;
    tasks.slice(0, -1).forEach((task) => {
      addMessage(taskQuestion(task), "user", task.id);
      archiveTaskAnswer(task);
    });
    const latest = tasks[tasks.length - 1];
    addMessage(taskQuestion(latest), "user", latest.id);
    state.lastQuestion = taskQuestion(latest);
    if (["created", "queued", "running"].includes(latest.status)) {
      state.taskId = latest.id;
      setBusy(true);
      try { renderResult(await waitForTask(latest.id)); }
      finally { state.taskId = ""; setBusy(false); }
    } else {
      renderResult(await api(`/api/v1/tasks/${latest.id}`));
    }
  } catch (error) {
    toast(`暂未恢复会话历史：${error.message}`);
  }
}

function renderBusinessView(view) {
  const root = $("#business-result"); root.replaceChildren();
  if (view.banner) root.append(el("div", { class: "notice warning", text: view.banner }));
  (view.sections || []).forEach((section) => {
    const card = el("section", { class: `business-section business-${section.key}` });
    card.append(el("h3", { text: section.label }));
    const content = typeof section.content === "string" ? section.content : JSON.stringify(section.content, null, 2);
    card.append(el("div", { class: "markdown-view" })); renderMarkdown(card.lastElementChild, content);
    root.append(card);
  });
}

async function uploadMaterial() {
  const file = $("#image-input").files[0]; if (!file) return null;
  const allowed = ["image/jpeg", "image/png", "image/webp", "text/plain", "text/markdown", "text/csv", "application/json", "application/pdf"];
  if (!allowed.includes(file.type) && !/\.(md|txt|csv|json|pdf)$/i.test(file.name)) throw new Error("暂不支持该材料类型");
  if (file.size > 20 * 1024 * 1024) throw new Error("材料不能超过 20MB");
  const form = new FormData(); form.append("upload", file); form.append("purpose", "unified_task_material");
  const uploaded = await api("/api/v1/files", { method: "POST", body: form });
  let extractedText = "";
  if ((file.type.startsWith("text/") || file.type === "application/json" || /\.(md|txt|csv|json)$/i.test(file.name)) && file.size <= 2 * 1024 * 1024) extractedText = await file.text();
  return { uploaded, extractedText, originalType: file.type };
}
function attachmentRef(file) { return { file_id: file.id, filename: file.filename, content_type: file.content_type, size_bytes: file.size_bytes, storage_key: file.storage_key, checksum_sha256: file.checksum_sha256 }; }

async function waitForTask(id) {
  return new Promise((resolve, reject) => {
    let settled = false; const events = new EventSource(`/api/v1/tasks/${id}/stream`);
    const finish = async () => { if (settled) return; try { const task = await api(`/api/v1/tasks/${id}`); if (["completed", "failed", "cancelled"].includes(task.status)) { settled = true; events.close(); resolve(task); } } catch (error) { settled = true; events.close(); reject(error); } };
    ["task.completed", "task.failed", "task.cancelled"].forEach((name) => events.addEventListener(name, finish));
    events.addEventListener("agent.started", () => addMessage("已完成能力编排，内部 Agent 正在协作处理…", "system"));
    events.addEventListener("knowledge.retrieved", () => { addMessage("已完成课程资料检索，正在整理本次证据…", "system"); selectContextTab("process"); });
    events.onerror = () => { events.close(); const timer = setInterval(async () => { try { const task = await api(`/api/v1/tasks/${id}`); if (["completed", "failed", "cancelled"].includes(task.status)) { clearInterval(timer); if (!settled) { settled = true; resolve(task); } } } catch (error) { clearInterval(timer); if (!settled) { settled = true; reject(error); } } }, 900); };
  });
}

function setBusy(busy) {
  $("#send-button").disabled = busy; $("#stop-button").disabled = !busy; $("#question-input").disabled = busy;
}

async function submit(event) {
  event.preventDefault(); if (state.taskId) return;
  $("#form-error").textContent = "";
  const question = $("#question-input").value.trim(); const course = selectedCourse();
  if (!question && !$("#image-input").files[0]) { $("#form-error").textContent = "请输入题目或上传图片"; return; }
  state.lastQuestion = question; setBusy(true); renderProcess([{ label: "正在理解你的需求", status: "running" }]);
  try {
    await ensureSession(); state.activeCourse = course; localStorage.setItem("xinzhi_student_course", course); archiveCurrentAnswer(); if (question) addMessage(question);
    const material = await uploadMaterial();
    const canonical = { text: question }; if (material?.extractedText) canonical.uploaded_text = material.extractedText;
    if (material?.originalType === "text/csv") canonical.data_description = material.extractedText;
    const payload = { session_id: state.sessionId, user_id: state.userId, user_role: "student", scene: "dispatch", course_id: course, intent: "unknown", canonical_input: canonical, attachments: material ? [attachmentRef(material.uploaded)] : [], context_refs: [], options: { request_id: `student_${crypto.randomUUID()}`, response_depth: $("#depth-select").value, prefer_internal_agents: true, use_local_rag: true, allow_cloud: false } };
    const task = await api("/api/v1/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    state.taskId = task.id; localStorage.setItem("xinzhi_last_task", task.id); addMessage(`已识别：${taskLabels[task.intent] || "待进一步判断"}${task.course_id ? ` · ${courseLabels[task.course_id] || task.course_id}` : ""}`, "system"); renderResult(await waitForTask(task.id));
    $("#question-input").value = ""; autoGrow(); clearImage();
  } catch (error) { $("#form-error").textContent = `${error.message}。请检查本地服务后重试。`; }
  finally { state.taskId = ""; setBusy(false); }
}

function clearImage() { $("#image-input").value = ""; $("#image-preview").hidden = true; $("#preview-image").removeAttribute("src"); $("#image-name").textContent = ""; }
function autoGrow() { const input = $("#question-input"); input.style.height = "auto"; input.style.height = `${Math.min(input.scrollHeight, 180)}px`; }
function applyParams() { if (params.get("course")) $("#course-select").value = params.get("course"); if (params.get("prompt")) $("#question-input").value = params.get("prompt"); }

async function loadCapabilities() {
  try {
    const payload = await api("/api/v1/capabilities");
    const features = new Map((payload.workspace_features || []).map((item) => [item.id, item]));
    all("[data-capability]").forEach((button) => {
      const feature = features.get(button.dataset.capability);
      if (!feature) return;
      button.classList.toggle("capability-unavailable", !feature.available);
      const stateLabel = button.querySelector(".capability-state");
      if (stateLabel) stateLabel.textContent = feature.available ? (feature.knowledge_enhanced ? "本地资料增强" : "内部 Agent 就绪") : "配置后可用";
    });
  } catch (error) {
    all("[data-capability] .capability-state").forEach((node) => { node.textContent = "状态待确认"; });
  }
}

window.addEventListener("DOMContentLoaded", () => {
  initShell({ page: "workspace", title: "智能任务工作台", description: "内部 Agent 与本地课程资料协同", context: "自动编排 · 本地知识增强", audience: "student" });
  applyParams(); updateShell(); autoGrow(); loadCapabilities(); loadSessionHistory();
  if (innerWidth <= 1180 && !document.body.classList.contains("presentation-mode")) setContextOpen(false);
  all("[data-prompt]").forEach((button) => button.addEventListener("click", () => { $("#question-input").value = button.dataset.prompt; $("#course-select").value = button.dataset.course || "AUTO"; updateShell(); autoGrow(); $("#question-input").focus(); }));
  all("[data-context-tab]").forEach((button) => button.addEventListener("click", () => selectContextTab(button.dataset.contextTab)));
  $("#student-form").addEventListener("submit", submit);
  $("#question-input").addEventListener("input", autoGrow);
  $("#question-input").addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("#student-form").requestSubmit(); } });
  $("#course-select").addEventListener("change", () => { if ($("#course-select").value !== "AUTO") state.activeCourse = $("#course-select").value; updateShell(); });
  $("#image-input").addEventListener("change", (event) => { const file = event.target.files[0]; if (!file) return clearImage(); $("#image-name").textContent = file.name; if (file.type.startsWith("image/")) { $("#preview-image").src = URL.createObjectURL(file); $("#preview-image").hidden = false; } else { $("#preview-image").hidden = true; } $("#image-preview").hidden = false; });
  $("#remove-image").addEventListener("click", clearImage);
  $("#stop-button").addEventListener("click", async () => { if (state.taskId) await api(`/api/v1/tasks/${state.taskId}/cancel`, { method: "POST" }); });
  $("#new-session").addEventListener("click", () => { state.sessionId = ""; state.currentTask = null; state.archivedTaskIds.clear(); localStorage.removeItem("xinzhi_student_session"); $("#messages").replaceChildren(); $("#answer-panel").hidden = true; $("#welcome").hidden = false; renderEvidence([], {}); renderProcess([]); $("#context-info").replaceChildren(); toast("已新建本地会话"); });
  $("#toggle-context").addEventListener("click", () => setContextOpen(document.body.classList.contains("context-closed")));
  $("#close-context").addEventListener("click", () => setContextOpen(false));
  $("#toggle-sources").addEventListener("click", () => selectContextTab("evidence"));
  $("#answer-source-chip").addEventListener("click", () => selectContextTab("evidence"));
  $("#answer-text").addEventListener("click", (event) => { const ref = event.target.closest("[data-evidence-ref]"); if (ref) focusEvidence(ref.dataset.evidenceRef); });
  $("#copy-answer").addEventListener("click", async () => { await navigator.clipboard.writeText(state.lastAnswer); toast("回答已复制"); });
  $("#follow-up").addEventListener("click", () => { $("#question-input").focus(); $("#question-input").placeholder = "继续追问这一回答…"; });
  $("#reask").addEventListener("click", () => { $("#question-input").value = state.lastQuestion; autoGrow(); $("#question-input").focus(); });
  $("#close-image-dialog").addEventListener("click", () => $("#image-dialog").close());
});
