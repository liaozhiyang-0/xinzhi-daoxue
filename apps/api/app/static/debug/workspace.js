const { $, all, api, el, initIdentityGate, initShell, renderMarkdown, toast } = XinzhiUI;
const params = new URLSearchParams(location.search);
const courseLabels = {
  CT: "电路理论",
  AE: "模拟电子技术",
  DE: "数字电子技术",
  SS: "信号与系统",
  DSP: "数字信号处理",
  COMM: "通信原理",
};
const taskLabels = { explain_concept: "知识问答", general_qa: "知识问答", solve_problem: "电路解题", lesson_prep: "教案设计", assignment_review: "作业批改", academic_writing: "学术写作", data_analysis: "数据分析" };
const intentLabels = { unknown: "自动识别", explain_concept: "概念解释", general_qa: "知识问答", solve_problem: "电路分析", lesson_prep: "教案设计", assignment_review: "作业初审", academic_writing: "学术写作", data_analysis: "数据分析" };
const ragLabels = { grounded_generation: "课程资料支撑", method_reference: "方法参考", reference_only: "资料参考", user_sources_only: "用户材料", data_context_only: "数据上下文", no_rag: "无需课程检索" };
const maxMultiImageFiles = 8;
const panelWidthStorage = {
  left: "xinzhi_workspace_left_width",
  right: "xinzhi_workspace_right_width",
};
let pendingMaterialFiles = [];
let materialPreviewUrls = [];
let conversationMaterialUrls = [];
let pendingLearningFollowUp = null;
const documentPageState = {
  item: null,
  previousOffset: null,
  nextOffset: null,
  requestSequence: 0,
  controller: null,
};
const state = {
  sessionId: localStorage.getItem("xinzhi_student_session") || "",
  userId: localStorage.getItem("xinzhi_student_user") || `student_${crypto.randomUUID()}`,
  taskId: "",
  activeCourse: params.get("course") || localStorage.getItem("xinzhi_student_course") || "AUTO",
  lastQuestion: "",
  lastAnswer: "",
  evidence: [],
  currentTask: null,
  activeMemoryIds: new Set(),
  archivedTaskIds: new Set(),
  showArchived: false,
};
localStorage.setItem("xinzhi_student_user", state.userId);

function selectedCourse() {
  return $("#course-select").value;
}

function updateTeachingMode() {
  const mode = $("#teaching-mode").value;
  const checking = mode === "check_my_work";
  $("#student-attempt-panel").hidden = !checking;
  const descriptions = {
    direct_answer: "直接给出完整思路与结论。",
    guided_learning: "先给一层提示和一个理解检查，不提前展示最终答案。",
    check_my_work: "核对明确数值、单位、符号和有限课程规则；复杂推导会标记人工复核。",
  };
  $("#teaching-mode-boundary").textContent = descriptions[mode] || descriptions.direct_answer;
}

function ownedTaskUrl(id) {
  return `/api/v1/tasks/${id}?user_id=${encodeURIComponent(state.userId)}`;
}

async function ensureSession(force = false) {
  if (state.sessionId && !force) return state.sessionId;
  const session = await api("/api/v1/sessions", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: state.userId, course_id: state.activeCourse === "AUTO" ? "CT" : state.activeCourse, title: "" }),
  });
  state.sessionId = session.id;
  localStorage.setItem("xinzhi_student_session", session.id);
  await loadSessionList();
  return session.id;
}

function resetConversation() {
  conversationMaterialUrls.forEach((url) => URL.revokeObjectURL(url));
  conversationMaterialUrls = [];
  state.currentTask = null; state.archivedTaskIds.clear();
  $("#messages").replaceChildren(); $("#answer-panel").hidden = true; $("#welcome").hidden = false;
  $("#teaching-loop-panel").hidden = true;
  $("#learning-progress-panel").hidden = true;
  state.activeMemoryIds.clear();
  renderEvidence([], {}); renderProcess([]);
  $("#context-usage").replaceChildren();
  $("#context-info").replaceChildren();
}

async function newSession() {
  state.sessionId = ""; localStorage.removeItem("xinzhi_student_session");
  resetConversation(); await ensureSession(true); toast("已新建会话");
}

function sessionItem(session) {
  const active = session.id === state.sessionId ? " active" : "";
  const button = el("article", { class: `session-item${active}`, tabindex: "0", "data-session-id": session.id }, [
    el("strong", { text: session.title || "新会话" }),
    el("button", { class: "session-archive", type: "button", title: session.archived_at ? "恢复" : "归档", text: session.archived_at ? "↩" : "×" }),
    el("small", { text: `${courseLabels[session.course_id] || session.course_id} · ${session.message_count || 0} 条消息` }),
  ]);
  button.addEventListener("click", async (event) => {
    if (event.target.closest(".session-archive")) {
      event.stopPropagation();
      const action = session.archived_at ? "restore" : "archive";
      await api(`/api/v1/sessions/${session.id}/${action}?user_id=${encodeURIComponent(state.userId)}`, { method: "POST" });
      if (!session.archived_at && state.sessionId === session.id) await newSession();
      await loadSessionList(); return;
    }
    state.sessionId = session.id; localStorage.setItem("xinzhi_student_session", session.id);
    resetConversation(); await loadSessionHistory(); await loadSessionList();
  });
  button.querySelector("strong").addEventListener("dblclick", async (event) => {
    event.stopPropagation();
    const title = window.prompt("修改会话标题", session.title || "")?.trim();
    if (!title || title === session.title) return;
    await api(`/api/v1/sessions/${session.id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: state.userId, title }),
    });
    await loadSessionList();
  });
  return button;
}

async function loadSessionList(query = "") {
  const endpoint = query
    ? `/api/v1/sessions/search?user_id=${encodeURIComponent(state.userId)}&q=${encodeURIComponent(query)}&include_archived=${state.showArchived}`
    : `/api/v1/sessions?user_id=${encodeURIComponent(state.userId)}&include_archived=${state.showArchived}`;
  try {
    const sessions = await api(endpoint);
    $("#session-list").replaceChildren(...sessions.map(sessionItem));
  } catch (error) { $("#session-list").replaceChildren(el("p", { class: "context-empty", text: "会话列表暂不可用" })); }
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

function addMessage(text, kind = "user", taskId = "", files = []) {
  $("#welcome").hidden = true;
  const attrs = { class: `conversation-message ${kind}` };
  if (taskId) attrs["data-task-id"] = taskId;
  const article = el("article", attrs, [
    el("span", { class: "message-role", text: kind === "user" ? "你" : "进度" }),
    el("p", { text }),
  ]);
  const imageFiles = files.filter((file) => file.type?.startsWith("image/"));
  if (imageFiles.length) {
    const gallery = el("div", { class: "message-image-gallery" });
    imageFiles.forEach((file, index) => {
      const url = URL.createObjectURL(file);
      conversationMaterialUrls.push(url);
      gallery.append(el("button", {
        type: "button",
        title: `查看 ${file.name}`,
        onclick: () => openImage(url, `${index + 1}. ${file.name}`),
      }, el("img", {
        src: url,
        alt: `${file.name} 原图`,
      })));
    });
    article.append(gallery);
  }
  $("#messages").append(article);
  scrollConversationToEnd();
  return article;
}

function appendStoredAttachmentImages(article, attachmentIds = []) {
  if (!article || !attachmentIds.length) return;
  const gallery = el("div", { class: "message-image-gallery" });
  attachmentIds.forEach((fileId, index) => {
    const src = `/api/v1/files/${encodeURIComponent(fileId)}/content?user_id=${encodeURIComponent(state.userId)}`;
    const image = el("img", {
      src,
      alt: `题目原图 ${index + 1}`,
      loading: "lazy",
      decoding: "async",
    });
    image.addEventListener("error", () => {
      image.closest("button")?.classList.add("image-load-failed");
    }, { once: true });
    gallery.append(el("button", {
      type: "button",
      title: `查看题目原图 ${index + 1}`,
      onclick: () => openImage(src, `题目原图 ${index + 1}`),
    }, image));
  });
  article.append(gallery);
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
    academic_generation_direct_model: "专业求解链路未形成完整回答，已由通用模型直接完成本次回答。",
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
  if (String(uri).startsWith("/api/v1/knowledge/images/")) return String(uri);
  if (!String(uri).startsWith("kb-image://")) return "";
  const rest = uri.slice(11); const slash = rest.indexOf("/");
  if (slash < 0) return "";
  return `/api/v1/knowledge/images/${encodeURIComponent(rest.slice(0, slash))}/${rest.slice(slash + 1).split("/").map(encodeURIComponent).join("/")}`;
}

function normalizeRelativeKnowledgePath(documentPath, resourcePath) {
  const clean = String(resourcePath || "").split(/[?#]/, 1)[0].replace(/\\/g, "/");
  if (!clean || clean.startsWith("/") || /^[a-z]+:/i.test(clean)) return "";
  const parts = [...String(documentPath || "").split("/").slice(0, -1), ...clean.split("/")];
  const normalized = [];
  parts.forEach((part) => {
    if (!part || part === ".") return;
    if (part === "..") normalized.pop();
    else normalized.push(part);
  });
  return normalized.join("/");
}

function rewriteKnowledgeDocumentImages(markdown, page) {
  return String(markdown || "").replace(
    /!\[([^\]]*)\]\((<[^>]+>|[^)\s]+)(\s+"[^"]*")?\)/g,
    (match, alt, rawTarget, title = "") => {
      const target = String(rawTarget).replace(/^<|>$/g, "");
      if (target.startsWith("kb-image://")) {
        const src = imageUrl(target);
        return src ? `![${alt}](${src}${title})` : match;
      }
      if (/^(?:https?:|data:image\/|\/api\/v1\/knowledge\/images\/)/i.test(target)) {
        return match;
      }
      const relative = normalizeRelativeKnowledgePath(page.relative_path, target);
      if (!relative) return match;
      const src = imageUrl(`kb-image://${page.course_id}/${relative}`);
      return src ? `![${alt}](${src}${title})` : match;
    },
  );
}

function knowledgeDocumentUrl(sourceRef) {
  const value = String(sourceRef || "");
  if (!value.startsWith("kb://")) return "";
  const [withoutFragment, fragment = ""] = value.slice(5).split("#", 2);
  const slash = withoutFragment.indexOf("/");
  if (slash < 1 || slash === withoutFragment.length - 1) return "";
  const course = withoutFragment.slice(0, slash);
  const path = withoutFragment.slice(slash + 1);
  const query = new URLSearchParams({ normalize_math: "true" });
  if (fragment) query.set("chunk", fragment);
  return `/api/v1/knowledge/documents/${encodeURIComponent(course)}/${path.split("/").map(encodeURIComponent).join("/")}?${query}`;
}

function knowledgeDocumentPageUrl(sourceRef, { offset = null, anchor = "" } = {}) {
  const value = String(sourceRef || "");
  if (!value.startsWith("kb://")) return "";
  const [withoutFragment, fragment = ""] = value.slice(5).split("#", 2);
  const slash = withoutFragment.indexOf("/");
  if (slash < 1 || slash === withoutFragment.length - 1) return "";
  const course = withoutFragment.slice(0, slash);
  const path = withoutFragment.slice(slash + 1);
  const query = new URLSearchParams({ normalize_math: "true" });
  if (fragment) query.set("chunk", fragment);
  if (offset != null) query.set("offset", String(offset));
  else if (anchor) query.set("anchor", anchor.slice(0, 1200));
  return `/api/v1/knowledge/document-pages/${encodeURIComponent(course)}/${path.split("/").map(encodeURIComponent).join("/")}?${query}`;
}

function documentPageStatus(page) {
  const format = new Intl.NumberFormat("zh-CN");
  const start = page.total_chars ? page.start_offset + 1 : 0;
  return `完整原文 ${format.format(start)}–${format.format(page.end_offset)} / ${format.format(page.total_chars)} 字符`;
}

async function loadEvidenceDocumentPage(item, offset = null) {
  const anchor = offset == null ? String(item.summary || "").trim() : "";
  const url = knowledgeDocumentPageUrl(item.source_ref, { offset, anchor });
  if (!url) {
    toast("这条资料没有可打开的本地文档", "degraded");
    return;
  }
  documentPageState.controller?.abort();
  const controller = new AbortController();
  const requestSequence = documentPageState.requestSequence + 1;
  documentPageState.requestSequence = requestSequence;
  documentPageState.controller = controller;
  documentPageState.item = item;
  const content = $("#document-dialog-content");
  const note = $("#document-dialog-note");
  const previous = $("#document-page-previous");
  const next = $("#document-page-next");
  content.classList.add("loading");
  content.textContent = "正在读取并排版课程资料…";
  note.hidden = true;
  previous.disabled = true;
  next.disabled = true;
  $("#document-page-status").textContent = offset == null ? "正在定位资料原文…" : "正在加载资料原文…";
  try {
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `资料读取失败（${response.status}）`);
    }
    const page = await response.json();
    if (requestSequence !== documentPageState.requestSequence) return;
    documentPageState.previousOffset = page.previous_offset;
    documentPageState.nextOffset = page.next_offset;
    renderMarkdown(
      content,
      rewriteKnowledgeDocumentImages(
        page.content || "这部分原文没有可显示的文本。",
        page,
      ),
    );
    all("img.markdown-image", content).forEach((image) => {
      image.addEventListener("click", () => openImage(
        image.currentSrc || image.src,
        image.alt || item.title || "课程资料图片",
      ));
      image.addEventListener("error", () => {
        image.classList.add("image-load-failed");
        image.alt = `${image.alt || "课程资料图片"}（加载失败）`;
      }, { once: true });
    });
    content.classList.remove("loading");
    previous.disabled = page.previous_offset == null;
    next.disabled = page.next_offset == null;
    $("#document-page-status").textContent = documentPageStatus(page);
    $("#document-dialog-meta").textContent = [
      courseLabels[page.course_id] || item.course_name,
      item.chapter,
      item.section,
      page.relative_path,
    ].filter(Boolean).join(" · ");
    if (page.anchor_status === "not_found") {
      note.textContent = "当前索引片段与本地原文版本不完全一致；上方仍保留本次回答实际使用的片段，下面从原文开头开始显示。";
      note.hidden = false;
    }
    $("#document-dialog-body").scrollTop = 0;
  } catch (error) {
    if (error.name === "AbortError" || requestSequence !== documentPageState.requestSequence) return;
    content.classList.remove("loading");
    content.replaceChildren(el("div", { class: "context-empty" }, [
      el("strong", { text: "暂时无法打开这份资料" }),
      el("p", { text: error.message }),
    ]));
    $("#document-page-status").textContent = "资料原文读取失败";
  }
}

async function openEvidenceDocument(item) {
  if (!knowledgeDocumentPageUrl(item.source_ref)) {
    toast("这条资料没有可打开的本地文档", "degraded");
    return;
  }
  const dialog = $("#document-dialog");
  $("#document-dialog-title").textContent = item.title || item.chapter || "课程资料";
  $("#document-dialog-meta").textContent = [courseLabels[item.course_id] || item.course_name, item.chapter, item.section].filter(Boolean).join(" · ");
  const match = $("#document-dialog-match");
  const summary = String(item.summary || "").trim();
  match.hidden = !summary;
  if (summary) {
    renderMarkdown($("#document-dialog-match-content"), summary);
  }
  if (!dialog.open) dialog.showModal();
  await loadEvidenceDocumentPage(item);
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
  const card = el("article", { class: "evidence-card", "data-evidence-id": item.evidence_id, role: "button", tabindex: "0", "aria-label": `打开资料：${item.title || item.chapter || "课程资料"}` });
  const summary = el("div", { class: "evidence-summary" });
  renderMarkdown(summary, item.summary || "本条资料没有可展示摘要。");
  const actions = el("div", { class: "evidence-card-actions" }, [
    el("small", { text: item.source_ref ? "本地只读资料" : "来源路径不可用" }),
    el("button", { type: "button", class: "evidence-open", text: "打开资料" }),
  ]);
  card.append(
    el("div", { class: "evidence-card-header" }, [el("span", { class: "evidence-id", text: item.evidence_id }), el("span", { class: "evidence-role", text: role })]),
    el("h3", { text: item.title || item.chapter || "课程资料" }),
    el("small", { text: [courseLabels[item.course_id] || item.course_name, item.chapter, item.content_type].filter(Boolean).join(" · ") }),
    summary,
  );
  const images = (item.related_images || []).map((image) => ({ image, src: imageUrl(image.resource_uri) })).filter((entry) => entry.src);
  if (images.length) {
    const row = el("div", { class: "evidence-images" });
    images.forEach(({ image, src }) => row.append(el("button", { type: "button", onclick: (event) => { event.stopPropagation(); openImage(src, image.caption || item.title); } }, el("img", { src, loading: "lazy", alt: image.caption || item.title }))));
    card.append(row);
  }
  card.append(actions);
  const open = () => { focusEvidence(item.evidence_id); void openEvidenceDocument(item); };
  actions.lastElementChild.addEventListener("click", (event) => { event.stopPropagation(); open(); });
  card.addEventListener("click", (event) => { if (!event.target.closest(".evidence-images")) open(); });
  card.addEventListener("keydown", (event) => {
    if (event.target !== card) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      open();
    }
  });
  return card;
}

function focusEvidence(id) {
  selectContextTab("evidence");
  all("[data-evidence-id]").forEach((card) => card.classList.toggle("active", card.dataset.evidenceId === id));
  const active = $(`[data-evidence-id="${CSS.escape(id)}"]`);
  active?.scrollIntoView({ behavior: "smooth", block: "center" });
}

function relatedImageCard(images) {
  const unique = [...new Map(
    images
      .filter((item) => imageUrl(item.resource_uri))
      .map((item) => [item.resource_uri, item]),
  ).values()];
  if (!unique.length) return null;
  const gallery = el("div", { class: "related-image-gallery" });
  unique.forEach((item) => {
    const src = imageUrl(item.resource_uri);
    const image = el("img", {
      src,
      alt: item.caption || "检索到的教材图片",
      loading: "lazy",
      decoding: "async",
    });
    image.addEventListener("error", () => {
      image.closest("button")?.classList.add("image-load-failed");
    }, { once: true });
    gallery.append(el("button", {
      type: "button",
      title: "打开教材图片",
      onclick: () => openImage(src, item.caption || item.resource_uri),
    }, image));
  });
  return el("article", { class: "evidence-card related-image-card" }, [
    el("div", { class: "evidence-card-header" }, [
      el("span", { class: "evidence-id", text: "图片资料" }),
      el("span", { class: "evidence-role", text: `${unique.length} 张` }),
    ]),
    el("h3", { text: "检索到的教材原图" }),
    el("small", { text: "点击缩略图查看完整图片" }),
    gallery,
  ]);
}

function renderEvidence(items, presentation, relatedImages = []) {
  state.evidence = items || [];
  const cards = state.evidence.map(evidenceCard);
  const imageCard = relatedImageCard(relatedImages);
  if (imageCard) cards.push(imageCard);
  $("#context-evidence").replaceChildren(...(cards.length ? cards : [el("div", { class: "context-empty" }, [el("strong", { text: "本次没有可展示的课程依据" }), el("p", { text: presentation?.evidence_message || "系统不会把未使用的候选资料显示为回答依据。" })]) ]));
}

function renderProcess(steps = []) {
  const list = el("div", { class: "process-list" });
  (steps.length ? steps : [{ label: "等待任务执行", status: "skipped" }]).forEach((step) => list.append(el("div", { class: `process-step ${step.status || "completed"}` }, [el("span", { class: "process-dot" }), el("div", {}, [el("strong", { text: step.label }), el("span", { text: ({ completed: "已完成", passed: "验证通过", failed: "需要检查", fallback: "已降级", skipped: "本次未执行" })[step.status] || step.status })])])));
  $("#context-process").replaceChildren(list);
}

function renderContextUsage(result = {}) {
  const metrics = result.metrics || {};
  const usage = result.context_usage || {
    memory_enabled: metrics.memory_enabled,
    active_memory_count: metrics.memory_retrieval_count,
    memory_write_count: metrics.memory_write_count,
    recent_message_count: metrics.recent_message_count,
    older_message_count: metrics.older_message_count,
    summary_used: metrics.session_summary_used,
    summary_version: metrics.summary_version,
    estimated_tokens: metrics.context_estimated_tokens,
    budget_tokens: metrics.context_budget_tokens,
    budget_ratio: metrics.context_budget_ratio,
    trimmed: metrics.context_trimmed,
    compaction_count: metrics.compaction_count,
    cache_status: metrics.context_cache_hit ? "hit" : "miss",
    build_latency_ms: metrics.context_build_latency_ms,
    active_memory_ids: [],
  };
  state.activeMemoryIds = new Set(usage.active_memory_ids || []);
  if (usage.estimated_tokens == null && usage.active_memory_count == null) {
    $("#context-usage").replaceChildren(el("div", { class: "context-empty" }, [
      el("strong", { text: "当前响应没有上下文统计" }),
      el("p", { text: "旧任务仍可正常查看答案，但不会补造上下文使用记录。" }),
    ]));
    return;
  }
  const ratio = Math.max(0, Math.min(1, Number(usage.budget_ratio || 0)));
  const memoryStatus = usage.memory_enabled
    ? `已使用 ${usage.active_memory_count || 0} 条`
    : "长期记忆未启用";
  const summaryStatus = usage.summary_used
    ? `摘要 v${usage.summary_version || 1}`
    : "未使用摘要";
  const cards = el("div", { class: "context-stat-grid" }, [
    el("article", { class: "context-stat" }, [el("span", { text: "会话消息" }), el("strong", { text: `${usage.recent_message_count || 0} 条近期 · ${usage.older_message_count || 0} 条相关历史` })]),
    el("article", { class: "context-stat" }, [el("span", { text: "长期记忆" }), el("strong", { text: memoryStatus })]),
    el("article", { class: "context-stat" }, [el("span", { text: "历史压缩" }), el("strong", { text: summaryStatus })]),
    el("article", { class: "context-stat" }, [el("span", { text: "构建状态" }), el("strong", { text: `${usage.cache_status === "hit" ? "缓存命中" : "实时构建"} · ${Number(usage.build_latency_ms || 0).toFixed(1)} ms` })]),
  ]);
  const budget = el("section", { class: "context-budget-card" }, [
    el("div", { class: "context-budget-heading" }, [
      el("strong", { text: "上下文预算" }),
      el("span", { text: `${usage.estimated_tokens || 0} / ${usage.budget_tokens || 0} tokens` }),
    ]),
    el("div", { class: "context-meter", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(Math.round(ratio * 100)) }, [
      el("span", { style: `width:${Math.round(ratio * 100)}%` }),
    ]),
    el("p", { text: usage.trimmed ? "已按预算裁剪较早内容，当前问题和稳定偏好仍被保留。" : "上下文处于预算内，没有触发裁剪。" }),
  ]);
  const actions = el("div", { class: "context-usage-actions" });
  actions.append(el("button", { class: "text-button", type: "button", text: "查看记忆设置", onclick: async () => { await loadMemories(); $("#memory-dialog").showModal(); } }));
  const notices = [];
  if ((usage.memory_write_count || 0) > 0) notices.push(el("p", { class: "context-usage-note", text: usage.memory_action === "auto_remembered" ? "本轮按你的自动记忆设置保存了稳定偏好。" : "本轮已按明确指令更新长期记忆。" }));
  if ((usage.compaction_count || 0) > 0) notices.push(el("p", { class: "context-usage-note", text: "本轮已生成新的会话摘要，后续对话会优先使用压缩后的历史。" }));
  if (usage.summary_refresh_status === "queued") notices.push(el("p", { class: "context-usage-note", text: "回答已完成；后台正在提炼本轮关键信息，不会阻塞你继续提问。" }));
  if (usage.summary_refresh_status === "failed") notices.push(el("p", { class: "context-usage-note", text: "本轮后台总结未完成；近期对话仍会原样进入后续上下文。" }));
  $("#context-usage").replaceChildren(cards, budget, ...notices, actions);
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
    ["答案质量", presentation.answer_quality_status === "checked" ? "已检查" : presentation.requires_review ? "需要复核" : "未检查"],
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
  renderTeachingLoop(structured);
  void loadLearningProgress(task);
  renderBusinessView(structured.business_view || {});
  const notices = [];
  if (summary.mock || result.provider === "mock" || result.mock_used) notices.push({ status: "mock", text: "当前为开发态模拟结果，不代表正式智能能力输出。" });
  if (presentation.answer_quality_message) notices.push({
    status: presentation.requires_review ? "warning" : "",
    text: presentation.answer_quality_message,
  });
  if (presentation.fallback_message) notices.push({ status: "warning", text: presentation.fallback_message });
  if (presentation.evidence_message) notices.push({ status: "", text: presentation.evidence_message });
  if (structured.teaching?.warning) notices.push({ status: "warning", text: structured.teaching.warning });
  if (structured.teaching?.teaching_mode === "check_my_work") notices.push({ status: "warning", text: structured.teaching.diagnostic_scope });
  if (structured.student_attempt_review?.feedback?.length) notices.push({ status: "", text: structured.student_attempt_review.feedback.join("；") });
  $("#answer-notices").replaceChildren(...notices.map((item) => el("div", { class: `notice ${item.status}`, text: item.text })));
  const relatedImages = [
    ...(structured.related_images || []),
    ...(result.related_images || []),
    ...(structured.knowledge?.images || []),
  ];
  renderEvidence(evidence, presentation, relatedImages); renderProcess(presentation.execution_steps || []);
  renderContextUsage(result);
  const renderMs = performance.now() - renderStarted; localStorage.setItem("xinzhi_last_render_ms", renderMs.toFixed(1));
  renderInfo(task, result, summary, presentation, renderMs);
  $("#answer-panel").scrollIntoView({ behavior: "smooth", block: "start" });
}

function verificationPresentation(report) {
  if (!report) return null;
  const firstError = (report.step_results || []).find((item) => item.status === "verified_incorrect");
  if (firstError) {
    return {
      kind: "is-error",
      title: "已确认有限范围错误",
      text: firstError.message || "检测到一项可由规则明确确认的错误。",
    };
  }
  if (report.overall_status === "verified_correct") {
    return {
      kind: "is-correct",
      title: "有限核对通过",
      text: "在当前支持的规则范围内未发现错误；这不等同于对全部复杂推导的证明。",
    };
  }
  if (report.manual_review_required || report.overall_status === "manual_review") {
    return {
      kind: "is-review",
      title: "需要人工复核",
      text: (report.warnings || [])[0] || "当前推导超出有限核对范围，系统不会把不确定判断表述成已确认错误。",
    };
  }
  return {
    kind: "is-review",
    title: "本轮仅作启发式检查",
    text: (report.warnings || [])[0] || "尚无足够规则证据确认正误。",
  };
}

function usesInteractiveTeaching(structured = {}) {
  const mode = structured.teaching?.teaching_mode;
  if (mode) return ["guided_learning", "check_my_work"].includes(mode);
  const path = structured.teaching_loop?.execution_plan?.path;
  return ["guided", "check"].includes(path);
}

function renderTeachingLoop(structured) {
  const loop = structured.teaching_loop;
  const panel = $("#teaching-loop-panel");
  if (!loop || !usesInteractiveTeaching(structured)) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const plan = loop.execution_plan || {};
  const full = loop.disclosure_policy?.reveal_final_answer || loop.full_solution_disclosed;
  const pathLabels = { direct: "直接解答", guided: "分步辅导", check: "检查步骤" };
  $("#teaching-path-badge").textContent = full
    ? "完整解答已开启"
    : pathLabels[plan.path] || "学习闭环";

  const hint = loop.hint;
  $("#teaching-hint-badge").hidden = !hint || full;
  if (hint) $("#teaching-hint-badge").textContent = hint.hint_level;
  $("#teaching-hint-card").hidden = !hint || full;
  if (hint) $("#teaching-hint-text").textContent = hint.hint_text;

  const verification = verificationPresentation(loop.verification || structured.verification_report_v1);
  const verificationCard = $("#teaching-verification-card");
  verificationCard.hidden = !verification;
  verificationCard.className = `teaching-status-card${verification ? ` ${verification.kind}` : ""}`;
  if (verification) {
    $("#teaching-verification-title").textContent = verification.title;
    $("#teaching-verification-text").textContent = verification.text;
  }

  const nextCheck = loop.next_check;
  $("#teaching-next-card").hidden = !nextCheck || full;
  if (nextCheck) $("#teaching-next-question").textContent = nextCheck.question_text;
  $("#submit-teaching-response").hidden = !nextCheck || full;
  $("#request-more-hint").hidden = !hint || full;
  $("#switch-direct-answer").hidden = full;
  $("#teaching-scope-note").hidden = !loop.verification && plan.path !== "check";
}

function formatLearningTime(value) {
  if (!value) return "时间未记录";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "时间未记录" : date.toLocaleString("zh-CN", { hour12: false });
}

function renderAttemptHistory(attempts) {
  const container = $("#attempt-history");
  if (!attempts.length) {
    container.replaceChildren(el("p", { class: "learning-empty", text: "本题还没有正式提交的尝试。" }));
    return;
  }
  const verificationLabels = {
    verified_correct: "有限核对通过",
    verified_incorrect: "发现可确认差异",
    manual_review: "需要人工复核",
    not_checked: "未自动核对",
  };
  container.replaceChildren(...attempts
    .slice()
    .sort((a, b) => a.attempt_sequence - b.attempt_sequence)
    .map((attempt) => el("article", { class: "attempt-item" }, [
      el("strong", { text: `第${attempt.attempt_sequence}次尝试` }),
      el("span", { text: `${verificationLabels[attempt.verification_status] || "已提交"} · 提示 ${attempt.hint_level_used || "未使用"}` }),
      el("small", { text: `${formatLearningTime(attempt.submitted_at)} · ${attempt.full_solution_seen ? "已查看完整答案" : "未查看完整答案"}${attempt.status === "superseded" ? " · 已由新版本替代" : ""}` }),
    ])));
}

function renderMasteryProgress(states, attempts) {
  const container = $("#mastery-progress-list");
  if (!states.length) {
    container.replaceChildren(el("p", { class: "learning-empty", text: "完成可验证练习后，这里会显示辅助估计。" }));
    return;
  }
  const latest = attempts.slice().sort((a, b) => b.attempt_sequence - a.attempt_sequence)[0];
  container.replaceChildren(...states.map((item) => {
    const estimate = Math.round(Number(item.mastery_score || 0) * 100);
    return el("article", { class: "mastery-item" }, [
      el("strong", { text: item.knowledge_point }),
      el("span", { text: `学习进度估计 ${estimate}/100` }),
      el("small", { text: `最近练习 ${latest ? formatLearningTime(latest.submitted_at) : "暂无"} · 提示使用 ${item.hint_count || 0} 次` }),
    ]);
  }));
}

function renderRetestPlans(plans) {
  const container = $("#retest-plan-list");
  const active = plans.filter((item) => ["scheduled", "due"].includes(item.status));
  if (!active.length) {
    container.replaceChildren(el("p", { class: "learning-empty", text: "当前没有待处理的复习项。" }));
    return;
  }
  container.replaceChildren(...active.map((plan) => {
    const actions = el("div", { class: "retest-item-actions" }, [
      el("button", { class: "button", type: "button", text: "开始复习", "data-start-retest": plan.retest_plan_id }),
      el("button", { class: "text-button", type: "button", text: "稍后处理", "data-dismiss-retest": plan.retest_plan_id }),
    ]);
    actions.querySelector("[data-start-retest]").addEventListener("click", () => learningAction("start_retest", { retest_plan_id: plan.retest_plan_id }));
    actions.querySelector("[data-dismiss-retest]").addEventListener("click", () => learningAction("dismiss_retest", { retest_plan_id: plan.retest_plan_id }));
    return el("article", { class: "retest-item" }, [
      el("strong", { text: plan.skill_id }),
      el("span", { text: `${plan.status === "due" ? "已到期" : "计划复习"} · ${formatLearningTime(plan.due_at)}` }),
      el("small", { text: `来源题目 ${plan.source_task_id.slice(0, 12)}` }),
      actions,
    ]);
  }));
}

async function loadLearningProgress(task = state.currentTask) {
  if (!task?.id) return;
  const structured = task.result_content?.structured_result || {};
  if (!usesInteractiveTeaching(structured)) {
    $("#learning-progress-panel").hidden = true;
    return;
  }
  try {
    const query = `user_id=${encodeURIComponent(state.userId)}`;
    const [attempts, mastery, retests] = await Promise.all([
      api(`/api/v1/learning/attempts?${query}&source_task_id=${encodeURIComponent(task.id)}&limit=50`),
      api(`/api/v1/learning/states?${query}&course_id=${encodeURIComponent(task.course_id || "")}`),
      api(`/api/v1/learning/retests?${query}&limit=50`),
    ]);
    if (state.currentTask?.id !== task.id) return;
    $("#learning-progress-panel").hidden = false;
    renderAttemptHistory(attempts);
    renderMasteryProgress(mastery, attempts);
    renderRetestPlans(retests.filter((item) => item.source_task_id === task.id));
  } catch (error) {
    console.warn("learning progress unavailable", error);
  }
}

async function loadSessionHistory() {
  if (!state.sessionId) return;
  try {
    const messages = await api(`/api/v1/sessions/${state.sessionId}/messages?user_id=${encodeURIComponent(state.userId)}&limit=100`);
    if (!messages.length) return;
    $("#welcome").hidden = true;
    messages.forEach((message) => {
      if (message.role === "user") {
        const article = addMessage(message.content_text, "user", message.source_task_id || "");
        appendStoredAttachmentImages(article, message.attachment_ids || []);
      } else if (message.role === "assistant") {
        const body = el("div", { class: "message-body" }, [
          el("span", { class: "message-meta", text: message.status === "completed" ? "已完成" : message.status }),
          el("div", { class: "markdown-view" }),
        ]);
        renderMarkdown(body.lastElementChild, message.content_text);
        $("#messages").append(el("article", { class: "conversation-message assistant", "data-task-id": message.source_task_id || "" }, [
          el("span", { class: "message-role", text: "芯智导学" }), body,
        ]));
        if (message.source_task_id) state.archivedTaskIds.add(message.source_task_id);
      } else if (message.role === "system_event") {
        addMessage(message.content_text, "system", message.source_task_id || "");
      }
    });
    const latest = messages[messages.length - 1];
    state.lastQuestion = [...messages].reverse().find((item) => item.role === "user")?.content_text || "";
    if (latest.role === "user" && latest.source_task_id) {
      const latestTask = await api(ownedTaskUrl(latest.source_task_id));
      if (["created", "queued", "running"].includes(latestTask.status)) {
        state.taskId = latestTask.id;
        setBusy(true);
        try { renderResult(await waitForTask(latestTask.id)); }
        finally { state.taskId = ""; setBusy(false); }
      }
    }
    const latestAssistantTask = [...messages].reverse().find((item) => item.role === "assistant" && item.source_task_id);
    if (latestAssistantTask && latestAssistantTask.source_task_id !== state.taskId) {
      const restoredTask = await api(ownedTaskUrl(latestAssistantTask.source_task_id));
      if (restoredTask.status === "completed") renderResult(restoredTask);
    }
  } catch (error) {
    try {
      const tasks = await api(`/api/v1/sessions/${state.sessionId}/tasks?limit=50`);
      tasks.forEach((task) => {
        const article = addMessage(taskQuestion(task), "user", task.id);
        appendStoredAttachmentImages(
          article,
          (task.input_content?.attachments || []).map((item) => item.file_id),
        );
        archiveTaskAnswer(task);
      });
    } catch (_fallbackError) {
      toast(`暂未恢复会话历史：${error.message}`);
    }
  }
}

async function loadMemories() {
  const [session, memories, summary] = await Promise.all([
    api(`/api/v1/sessions/${state.sessionId}?user_id=${encodeURIComponent(state.userId)}`),
    api(`/api/v1/memories?user_id=${encodeURIComponent(state.userId)}`),
    api(`/api/v1/sessions/${state.sessionId}/summary?user_id=${encodeURIComponent(state.userId)}`),
  ]);
  $("#memory-enabled").checked = session.memory_enabled;
  $("#auto-memory-enabled").checked = session.auto_memory_enabled;
  $("#session-summary-preview").replaceChildren(
    el("strong", { text: summary ? "最近自动会话摘要" : "自动会话摘要" }),
    el("p", { text: summary?.summary_text || (session.memory_enabled ? "回答完成后会在后台提炼关键目标、事实和待继续事项。" : "当前已关闭，不会调用模型生成会话摘要。") }),
    el("small", { text: summary ? `v${summary.version} · ${summary.generation_method === "model" ? "模型总结" : "确定性降级摘要"} · 覆盖 ${summary.covers_through_sequence} 条消息` : "尚无摘要" }),
  );
  $("#memory-list").replaceChildren(...memories.map((memory) => {
    const actions = el("div", {}, [
      el("button", { type: "button", text: "编辑", "aria-label": "编辑记忆" }),
      el("button", { type: "button", text: "删除", "aria-label": "删除记忆" }),
    ]);
    const usedNow = state.activeMemoryIds.has(memory.memory_id);
    const source = ["automatic_opt_in", "model_summary_explicit_preference"].includes(memory.content_data?.capture_mode)
      ? "自动保存"
      : memory.source_session_id ? "来自会话" : "手动添加";
    const scope = memory.scope === "course" && memory.course_id
      ? courseLabels[memory.course_id] || memory.course_id
      : "全部课程";
    const row = el("article", { class: `memory-item${usedNow ? " active" : ""}` }, [
      el("div", {}, [el("p", { text: memory.content }), el("small", { text: `${source} · ${scope}${usedNow ? " · 本次已使用" : ""}` })]),
      actions,
    ]);
    actions.firstElementChild.addEventListener("click", async () => {
      const content = window.prompt("编辑记忆", memory.content)?.trim();
      if (!content || content === memory.content) return;
      await api(`/api/v1/memories/${memory.memory_id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: state.userId, content }) });
      await loadMemories();
    });
    actions.lastElementChild.addEventListener("click", async () => {
      await api(`/api/v1/memories/${memory.memory_id}?user_id=${encodeURIComponent(state.userId)}`, { method: "DELETE" });
      await loadMemories();
    });
    return row;
  }));
}

async function updateMemorySettings() {
  const session = await api(`/api/v1/sessions/${state.sessionId}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: state.userId, memory_enabled: $("#memory-enabled").checked, auto_memory_enabled: $("#auto-memory-enabled").checked }),
  });
  $("#memory-enabled").checked = session.memory_enabled;
  $("#auto-memory-enabled").checked = session.auto_memory_enabled;
  toast(session.memory_enabled ? "记忆设置已更新" : "长期记忆已关闭");
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

function selectedMaterialFiles() {
  return [...pendingMaterialFiles];
}

function validateMaterialFiles(files) {
  const allowed = ["image/jpeg", "image/png", "image/webp", "text/plain", "text/markdown", "text/csv", "application/json", "application/pdf"];
  if (files.length > maxMultiImageFiles) throw new Error(`一次最多上传 ${maxMultiImageFiles} 张图片`);
  if (files.length > 1 && files.some((file) => !file.type.startsWith("image/"))) throw new Error("多文件输入目前仅支持图片；文档材料请单独上传");
  files.forEach((file) => {
    if (!allowed.includes(file.type) && !/\.(md|txt|csv|json|pdf)$/i.test(file.name)) throw new Error(`暂不支持材料类型：${file.name}`);
    if (file.size > 20 * 1024 * 1024) throw new Error(`材料不能超过 20MB：${file.name}`);
  });
}

function materialFileKey(file) {
  return [file.name, file.size, file.type, file.lastModified].join(":");
}

function appendMaterialFiles(files) {
  const known = new Set(pendingMaterialFiles.map(materialFileKey));
  const additions = files.filter((file) => !known.has(materialFileKey(file)));
  const combined = [...pendingMaterialFiles, ...additions];
  validateMaterialFiles(combined);
  pendingMaterialFiles = combined;
}

async function uploadMaterials() {
  const files = selectedMaterialFiles(); if (!files.length) return [];
  validateMaterialFiles(files);
  const materials = [];
  for (const file of files) {
    const form = new FormData(); form.append("upload", file); form.append("purpose", "unified_task_material");
    const uploaded = await api("/api/v1/files", { method: "POST", body: form });
    let extractedText = "";
    if ((file.type.startsWith("text/") || file.type === "application/json" || /\.(md|txt|csv|json)$/i.test(file.name)) && file.size <= 2 * 1024 * 1024) extractedText = await file.text();
    materials.push({ uploaded, extractedText, originalType: file.type });
  }
  return materials;
}
function attachmentRef(file) { return { file_id: file.id, filename: file.filename, content_type: file.content_type, size_bytes: file.size_bytes, storage_key: file.storage_key, checksum_sha256: file.checksum_sha256 }; }

async function waitForTask(id) {
  return new Promise((resolve, reject) => {
    let settled = false; const events = new EventSource(`/api/v1/tasks/${id}/stream`);
    const finish = async () => { if (settled) return; try { const task = await api(ownedTaskUrl(id)); if (["completed", "failed", "cancelled"].includes(task.status)) { settled = true; events.close(); resolve(task); } } catch (error) { settled = true; events.close(); reject(error); } };
    ["task.completed", "task.failed", "task.cancelled"].forEach((name) => events.addEventListener(name, finish));
    events.addEventListener("agent.started", () => addMessage("已完成能力编排，内部 Agent 正在协作处理…", "system"));
    events.addEventListener("knowledge.retrieved", () => { addMessage("已完成课程资料检索，正在整理本次证据…", "system"); selectContextTab("process"); });
    events.onerror = () => { events.close(); const timer = setInterval(async () => { try { const task = await api(ownedTaskUrl(id)); if (["completed", "failed", "cancelled"].includes(task.status)) { clearInterval(timer); if (!settled) { settled = true; resolve(task); } } } catch (error) { clearInterval(timer); if (!settled) { settled = true; reject(error); } } }, 900); };
  });
}

function setBusy(busy) {
  $("#send-button").disabled = busy; $("#stop-button").disabled = !busy; $("#question-input").disabled = busy; $("#student-attempt-input").disabled = busy; $("#teaching-mode").disabled = busy; $("#image-input").disabled = busy; $("#remove-image").disabled = busy;
  $("#teaching-response-input").disabled = busy;
  $("#submit-teaching-response").disabled = busy;
  $("#request-more-hint").disabled = busy;
  $("#switch-direct-answer").disabled = busy;
}

async function submit(event) {
  event.preventDefault(); if (state.taskId) return;
  $("#form-error").textContent = "";
  const question = $("#question-input").value.trim(); const course = selectedCourse();
  const teachingMode = $("#teaching-mode").value;
  const studentAttempt = $("#student-attempt-input").value.trim();
  const learningFollowUp = pendingLearningFollowUp;
  const requestedCourse = learningFollowUp?.course_id || course;
  const requestedIntent = learningFollowUp?.intent || "unknown";
  const selectedFiles = selectedMaterialFiles();
  if (!question && !selectedFiles.length) { $("#form-error").textContent = "请输入题目或上传图片"; return; }
  if (teachingMode === "check_my_work" && !studentAttempt) { $("#form-error").textContent = "请填写你的解题过程或答案"; return; }
  state.lastQuestion = question; state.activeMemoryIds.clear(); setBusy(true);
  renderProcess([{ label: "正在理解你的需求", status: "running" }]);
  $("#context-usage").replaceChildren(el("div", { class: "context-empty" }, [
    el("strong", { text: "正在组装本次上下文" }),
    el("p", { text: "任务完成后会展示实际使用的消息、记忆和预算。" }),
  ]));
  try {
    await ensureSession(); state.activeCourse = requestedCourse; localStorage.setItem("xinzhi_student_course", requestedCourse); archiveCurrentAnswer(); if (question) addMessage(question, "user", "", selectedFiles); else addMessage(`已上传 ${selectedFiles.length} 张题目图片`, "user", "", selectedFiles);
    const materials = await uploadMaterials();
    const canonical = { text: question };
    const uploadedText = materials.map((item) => item.extractedText).filter(Boolean).join("\n\n");
    if (uploadedText) canonical.uploaded_text = uploadedText;
    if (materials.length === 1 && materials[0].originalType === "text/csv") canonical.data_description = uploadedText;
    const payload = { session_id: state.sessionId, user_id: state.userId, user_role: "student", scene: "dispatch", course_id: requestedCourse, intent: requestedIntent, canonical_input: canonical, attachments: materials.map((item) => attachmentRef(item.uploaded)), context_refs: [], options: { request_id: `student_${crypto.randomUUID()}`, response_depth: $("#depth-select").value, teaching_mode: teachingMode, student_attempt: teachingMode === "check_my_work" ? { raw_text: studentAttempt } : undefined, prefer_internal_agents: true, use_local_rag: true, allow_cloud: false, source_task_id: learningFollowUp?.source_task_id || "", learning_action: learningFollowUp?.action || "" } };
    const task = await api("/api/v1/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    pendingLearningFollowUp = null;
    state.taskId = task.id; localStorage.setItem("xinzhi_last_task", task.id); addMessage(`已识别：${taskLabels[task.intent] || "待进一步判断"}${task.course_id ? ` · ${courseLabels[task.course_id] || task.course_id}` : ""}`, "system"); renderResult(await waitForTask(task.id)); await loadSessionList();
    $("#question-input").value = ""; $("#student-attempt-input").value = ""; autoGrow(); clearImage();
  } catch (error) { $("#form-error").textContent = `${error.message}。请检查本地服务后重试。`; }
  finally { state.taskId = ""; setBusy(false); }
}

function revokeMaterialPreviews() {
  materialPreviewUrls.forEach((url) => URL.revokeObjectURL(url));
  materialPreviewUrls = [];
}
function showMaterialPreview(files) {
  revokeMaterialPreviews();
  const previewList = $("#preview-images");
  previewList.replaceChildren();
  if (!files.length) {
    $("#image-preview").hidden = true;
    $("#image-name").textContent = "已选择 0 个材料";
    return;
  }
  const imageCount = files.filter((file) => file.type.startsWith("image/")).length;
  $("#image-name").textContent = imageCount === files.length
    ? `已选择 ${imageCount} 张图片，可继续点击“添加材料”追加`
    : `已选择 ${files.length} 个材料`;
  files.forEach((file, index) => {
    const item = document.createElement("div");
    item.className = "upload-preview-item";
    if (file.type.startsWith("image/")) {
      const image = document.createElement("img");
      const url = URL.createObjectURL(file);
      materialPreviewUrls.push(url);
      image.className = "upload-preview-thumb";
      image.src = url;
      image.alt = `${file.name} 预览`;
      item.append(image);
    } else {
      const icon = document.createElement("span");
      icon.className = "upload-preview-file-icon";
      icon.textContent = "文件";
      item.append(icon);
    }
    const meta = document.createElement("span");
    meta.className = "upload-preview-meta";
    const name = document.createElement("strong");
    name.textContent = `${index + 1}. ${file.name}`;
    const size = document.createElement("small");
    size.textContent = `${Math.max(1, Math.round(file.size / 1024))} KB`;
    meta.append(name, size);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-preview-item";
    remove.setAttribute("aria-label", `移除 ${file.name}`);
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      pendingMaterialFiles.splice(index, 1);
      showMaterialPreview(selectedMaterialFiles());
    });
    item.append(meta, remove);
    previewList.append(item);
  });
  $("#image-preview").hidden = false;
}
function clearImage() {
  pendingMaterialFiles = [];
  revokeMaterialPreviews();
  $("#image-input").value = "";
  $("#preview-images").replaceChildren();
  $("#image-preview").hidden = true;
  $("#image-name").textContent = "已选择 0 个材料";
}
function autoGrow() {
  const input = $("#question-input");
  if (input.style.height && input.dataset.autoHeight && input.style.height !== input.dataset.autoHeight) return;
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
  input.dataset.autoHeight = input.style.height;
}

function clampPanelWidth(side, requested) {
  const minimum = side === "left" ? 180 : 280;
  const hardMaximum = side === "left" ? 360 : 620;
  const opposite = Number(localStorage.getItem(panelWidthStorage[side === "left" ? "right" : "left"])) || (side === "left" ? 360 : 238);
  const available = Math.max(minimum, innerWidth - opposite - 520);
  return Math.round(Math.max(minimum, Math.min(requested, hardMaximum, available)));
}

function applyPanelWidth(side, requested, persist = false) {
  const width = clampPanelWidth(side, requested);
  $(".workspace-shell").style.setProperty(`--${side}-panel-width`, `${width}px`);
  const resizer = $(`#${side}-resizer`);
  resizer.setAttribute("aria-valuenow", String(width));
  if (persist) localStorage.setItem(panelWidthStorage[side], String(width));
  return width;
}

function initializeResizablePanels() {
  ["left", "right"].forEach((side) => {
    const fallback = side === "left" ? 238 : 360;
    applyPanelWidth(side, Number(localStorage.getItem(panelWidthStorage[side])) || fallback);
    const handle = $(`#${side}-resizer`);
    handle.addEventListener("pointerdown", (event) => {
      if (innerWidth <= 1180) return;
      const startX = event.clientX;
      const current = Number(handle.getAttribute("aria-valuenow")) || fallback;
      handle.setPointerCapture(event.pointerId);
      document.body.classList.add("is-resizing");
      const move = (moveEvent) => {
        const delta = side === "left" ? moveEvent.clientX - startX : startX - moveEvent.clientX;
        applyPanelWidth(side, current + delta);
      };
      const finish = () => {
        handle.removeEventListener("pointermove", move);
        document.body.classList.remove("is-resizing");
        const value = parseInt(getComputedStyle($(".workspace-shell")).getPropertyValue(`--${side}-panel-width`), 10);
        applyPanelWidth(side, value, true);
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", finish, { once: true });
      handle.addEventListener("pointercancel", finish, { once: true });
    });
    handle.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const current = Number(handle.getAttribute("aria-valuenow")) || fallback;
      if (event.key === "Home") applyPanelWidth(side, Number(handle.getAttribute("aria-valuemin")), true);
      else if (event.key === "End") applyPanelWidth(side, Number(handle.getAttribute("aria-valuemax")), true);
      else {
        const direction = event.key === "ArrowRight" ? 1 : -1;
        applyPanelWidth(side, current + direction * (side === "left" ? 12 : -12), true);
      }
    });
    handle.addEventListener("dblclick", () => applyPanelWidth(side, fallback, true));
  });
  window.addEventListener("resize", () => {
    ["left", "right"].forEach((side) => {
      const fallback = side === "left" ? 238 : 360;
      applyPanelWidth(side, Number(localStorage.getItem(panelWidthStorage[side])) || fallback);
    });
  });
}
function applyParams() { if (params.get("course")) $("#course-select").value = params.get("course"); if (params.get("prompt")) $("#question-input").value = params.get("prompt"); }

async function learningAction(action, payload = {}) {
  if (!state.currentTask?.id) { toast("请先完成一道题或一次知识问答"); return; }
  const phase2Action = ["request_more_hint", "submit_check_response", "switch_to_direct_answer"].includes(action);
  const revisionAction = action === "submit_attempt_revision";
  const studentAnswer = revisionAction
    ? $("#attempt-revision-input").value.trim()
    : phase2Action ? $("#teaching-response-input").value.trim() : $("#question-input").value.trim();
  if (action === "submit_check_response" && !studentAnswer) {
    $("#teaching-response-input").focus(); toast("请先回答当前这一步理解检查"); return;
  }
  if (action === "check_answer" && !studentAnswer) {
    $("#question-input").placeholder = "在这里写下你的答案，再点击“检查我的答案”";
    $("#question-input").focus(); toast("请先输入你的答案"); return;
  }
  if (revisionAction && !studentAnswer) {
    $("#attempt-revision-input").focus(); toast("请先写下修改后的步骤或答案"); return;
  }
  try {
    const result = await api("/api/v1/learning/actions", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_task_id: state.currentTask.id,
        user_id: state.userId,
        action,
        idempotency_key: `learn_${crypto.randomUUID()}`,
        student_answer: studentAnswer,
        payload,
      }),
    });
    toast(result.message);
    if (result.feedback_uptake || revisionAction) {
      $("#feedback-uptake-message").hidden = false;
      $("#feedback-uptake-message").textContent = result.message;
    }
    if (phase2Action) {
      const task = await api(ownedTaskUrl(state.currentTask.id));
      renderResult(task);
      if (action === "submit_check_response") $("#teaching-response-input").value = "";
      return;
    }
    if (["submit_attempt_revision", "dismiss_retest", "complete_retest"].includes(action)) {
      if (revisionAction) $("#attempt-revision-input").value = "";
      await loadLearningProgress();
    }
    if (result.review) {
      const feedback = (result.review.feedback || []).join("；") || result.review.status;
      addMessage(`答案检查：${feedback}`, "system");
      return;
    }
    const nextPrompt = result.practice?.status === "ready"
      ? result.practice.problem_text
      : result.follow_up_prompt;
    if (nextPrompt) {
      pendingLearningFollowUp = result.follow_up_context || null;
      if (pendingLearningFollowUp?.course_id && $(`#course-select option[value="${pendingLearningFollowUp.course_id}"]`)) {
        $("#course-select").value = pendingLearningFollowUp.course_id;
      }
      $("#question-input").value = nextPrompt; autoGrow();
      $("#student-form").requestSubmit();
    }
  } catch (error) { toast(`学习动作未完成：${error.message}`); }
}

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

window.addEventListener("DOMContentLoaded", async () => {
  const identity = await initIdentityGate({ next: `${location.pathname}${location.search}` });
  if (identity?.user_id || identity?.id) {
    const identityId = identity.user_id || identity.id;
    if (state.userId !== identityId) {
      state.sessionId = "";
      localStorage.removeItem("xinzhi_student_session");
    }
    state.userId = identityId;
    localStorage.setItem("xinzhi_student_user", state.userId);
  }
  initShell({ page: "workspace", title: "智能任务工作台", description: "内部 Agent 与本地课程资料协同", context: "自动编排 · 本地知识增强", audience: "student" });
  applyParams(); updateShell(); updateTeachingMode(); autoGrow(); initializeResizablePanels(); loadCapabilities(); loadSessionHistory(); loadSessionList();
  if (innerWidth <= 1180 && !document.body.classList.contains("presentation-mode")) setContextOpen(false);
  all("[data-prompt]").forEach((button) => button.addEventListener("click", () => { $("#question-input").value = button.dataset.prompt; $("#course-select").value = button.dataset.course || "AUTO"; updateShell(); autoGrow(); $("#question-input").focus(); }));
  all("[data-context-tab]").forEach((button) => button.addEventListener("click", () => selectContextTab(button.dataset.contextTab)));
  $("#student-form").addEventListener("submit", submit);
  $("#question-input").addEventListener("input", autoGrow);
  $("#teaching-mode").addEventListener("change", updateTeachingMode);
  $("#question-input").addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("#student-form").requestSubmit(); } });
  $("#course-select").addEventListener("change", () => { if ($("#course-select").value !== "AUTO") state.activeCourse = $("#course-select").value; updateShell(); });
  $("#image-input").addEventListener("change", (event) => {
    const files = Array.from(event.target.files || []);
    $("#form-error").textContent = "";
    try { appendMaterialFiles(files); showMaterialPreview(selectedMaterialFiles()); }
    catch (error) { $("#form-error").textContent = error.message; showMaterialPreview(selectedMaterialFiles()); }
    event.target.value = "";
  });
  $("#remove-image").addEventListener("click", clearImage);
  $("#stop-button").addEventListener("click", async () => { if (state.taskId) await api(`/api/v1/tasks/${state.taskId}/cancel`, { method: "POST" }); });
  $("#new-session").addEventListener("click", newSession);
  $("#sidebar-new-session").addEventListener("click", newSession);
  $("#session-search").addEventListener("input", (event) => loadSessionList(event.target.value.trim()));
  $("#show-archived").addEventListener("click", async () => { state.showArchived = !state.showArchived; $("#show-archived").textContent = state.showArchived ? "最近会话" : "归档会话"; await loadSessionList($("#session-search").value.trim()); });
  $("#open-memory").addEventListener("click", async () => { await ensureSession(); await loadMemories(); $("#memory-dialog").showModal(); });
  $("#close-memory").addEventListener("click", () => $("#memory-dialog").close());
  $("#memory-enabled").addEventListener("change", updateMemorySettings);
  $("#auto-memory-enabled").addEventListener("change", updateMemorySettings);
  $("#memory-form").addEventListener("submit", async (event) => {
    event.preventDefault(); const content = $("#memory-input").value.trim(); if (!content) return;
    await api("/api/v1/memories", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: state.userId, memory_type: "preference", scope: "global", content }) });
    $("#memory-input").value = ""; await loadMemories();
  });
  $("#forget-all").addEventListener("click", async () => {
    await api("/api/v1/memories/forget", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: state.userId, all_memories: true }) });
    await loadMemories();
  });
  $("#toggle-context").addEventListener("click", () => setContextOpen(document.body.classList.contains("context-closed")));
  $("#close-context").addEventListener("click", () => setContextOpen(false));
  $("#toggle-sources").addEventListener("click", () => selectContextTab("evidence"));
  $("#answer-source-chip").addEventListener("click", () => selectContextTab("evidence"));
  $("#answer-text").addEventListener("click", (event) => { const ref = event.target.closest("[data-evidence-ref]"); if (ref) focusEvidence(ref.dataset.evidenceRef); });
  $("#copy-answer").addEventListener("click", async () => { await navigator.clipboard.writeText(state.lastAnswer); toast("回答已复制"); });
  $("#follow-up").addEventListener("click", () => { $("#question-input").focus(); $("#question-input").placeholder = "继续追问这一回答…"; });
  $("#reask").addEventListener("click", () => { $("#question-input").value = state.lastQuestion; autoGrow(); $("#question-input").focus(); });
  all("[data-learning-action]").forEach((button) => button.addEventListener("click", () => learningAction(button.dataset.learningAction)));
  $("#submit-teaching-response").addEventListener("click", () => learningAction("submit_check_response"));
  $("#request-more-hint").addEventListener("click", () => learningAction("request_more_hint"));
  $("#switch-direct-answer").addEventListener("click", () => learningAction("switch_to_direct_answer"));
  $("#submit-attempt-revision").addEventListener("click", () => learningAction("submit_attempt_revision"));
  $("#close-image-dialog").addEventListener("click", () => $("#image-dialog").close());
  $("#document-page-previous").addEventListener("click", () => {
    if (documentPageState.item && documentPageState.previousOffset != null) {
      void loadEvidenceDocumentPage(documentPageState.item, documentPageState.previousOffset);
    }
  });
  $("#document-page-next").addEventListener("click", () => {
    if (documentPageState.item && documentPageState.nextOffset != null) {
      void loadEvidenceDocumentPage(documentPageState.item, documentPageState.nextOffset);
    }
  });
  $("#close-document-dialog").addEventListener("click", () => {
    documentPageState.controller?.abort();
    documentPageState.requestSequence += 1;
    $("#document-dialog").close();
  });
});
