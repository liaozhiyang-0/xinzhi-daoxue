const { $, all, api, el, initIdentityGate, initShell, renderMarkdown, toast } = XinzhiUI;
const params = new URLSearchParams(location.search);
const scenarioId = params.get("scenario_id") || "";
const requestedWorkspaceRole = ["student", "teacher", "researcher"].includes(params.get("role"))
  ? params.get("role")
  : "student";
const courseLabels = {
  CT: "电路理论",
  AE: "模拟电子技术",
  DE: "数字电子技术",
  SS: "信号与系统",
  DSP: "数字信号处理",
  COMM: "通信原理",
};
const externalProviderLabels = {
  arxiv: "arXiv",
  crossref: "Crossref",
  openalex: "OpenAlex",
  semantic_scholar: "Semantic Scholar",
  cnki: "中国知网",
  web_json: "网页检索",
};
const taskLabels = { explain_concept: "知识问答", general_qa: "知识问答", solve_problem: "电路解题", lesson_prep: "教案设计", assignment_review: "作业批改", academic_writing: "学术写作", data_analysis: "数据分析" };
const intentLabels = { unknown: "自动识别", explain_concept: "概念解释", general_qa: "知识问答", solve_problem: "电路分析", lesson_prep: "教案设计", assignment_review: "作业初审", academic_writing: "学术写作", data_analysis: "数据分析" };
const ragLabels = { grounded_generation: "课程资料支撑", method_reference: "方法参考", reference_only: "资料参考", user_sources_only: "用户材料", data_context_only: "数据上下文", no_rag: "无需课程检索" };
const maxMultiImageFiles = 8;
const researchTabularExtensions = new Set(["csv", "tsv", "json", "xlsx", "parquet"]);
const panelWidthStorage = {
  left: "xinzhi_workspace_left_width",
  right: "xinzhi_workspace_right_width",
};
let pendingMaterialFiles = [];
let materialPreviewUrls = [];
let conversationMaterialUrls = [];
let pendingLearningFollowUp = null;
let runtimeTaskControls = null;
let runtimeTaskControlsRequest = 0;
let runtimeTaskControlsBusy = false;
let runtimeLearningRunId = "";
let runtimeLearningTaskId = "";
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
  historyRequestSequence: 0,
  runSequence: 0,
  activeTaskWait: null,
  cancelRequested: false,
  feedbackEnabled: null,
  activeMemoryIds: new Set(),
  archivedTaskIds: new Set(),
  showArchived: false,
  liveProcessSteps: new Map(),
  intentOverride: params.get("intent") || "",
  userRole: "student",
};
let identityReady = Promise.resolve();
let scenarioRoles = null;
let scenarioRoleRequest = Promise.resolve();
localStorage.setItem("xinzhi_student_user", state.userId);

function effectiveWorkspaceRole(identity) {
  const role = String(identity?.role || "").trim().toLowerCase();
  return ["student", "teacher", "researcher", "admin"].includes(role)
    ? role
    : "student";
}

async function loadScenarioRolePolicy() {
  if (!scenarioId) return null;
  try {
    const scenario = await api(`/api/v1/scenarios/${encodeURIComponent(scenarioId)}`);
    scenarioRoles = Array.isArray(scenario.roles) ? scenario.roles : [];
  } catch (_error) {
    scenarioRoles = [];
  }
  return scenarioRoles;
}

function scenarioRoleAllowed() {
  return !scenarioId || scenarioRoles === null || scenarioRoles.includes(state.userRole);
}

function scenarioRoleMessage() {
  if (scenarioRoleAllowed()) return "";
  const roles = scenarioRoles.join("、") || requestedWorkspaceRole;
  return `当前场景仅允许 ${roles} 角色。请使用已获授权的账号登录后继续。`;
}

function selectedCourse() {
  return $("#course-select").value;
}

function researchAnalysisQuestionDetected(text = "") {
  const normalized = String(text || "").toLowerCase();
  return /数据分析|研究设计|数据质量|效应量|置信区间|不确定性|诊断结果|结论边界|双臂实验|处理组|对照组|treatment|control|effect size|confidence interval/.test(normalized);
}

function researchAnalysisV2Enabled(text = "") {
  const question = text || $("#question-input")?.value || "";
  return params.get("analysis_v2") === "1"
    || scenarioId === "research_data_workbench_v1"
    || state.intentOverride === "data_analysis"
    || researchAnalysisQuestionDetected(question);
}

function updateResearchAnalysisPanel() {
  const panel = $("#research-analysis-v2-panel");
  if (!panel) return;
  panel.hidden = !researchAnalysisV2Enabled();
}

function parseResearchAnalysisVariables(raw) {
  return raw.split("\n").map((line) => line.trim()).filter(Boolean).map((line) => {
    const [name, role = "unknown", unit = "", description = ""] = line.split("|").map((item) => item.trim());
    if (!name) throw new Error("科研分析变量行缺少变量名");
    return { name, role, unit, description, dtype: "unknown" };
  });
}

function parseResearchAnalysisJson(raw, label) {
  if (!raw) return undefined;
  try {
    return JSON.parse(raw);
  } catch (_error) {
    throw new Error(`${label} JSON 无法解析`);
  }
}

function researchTabularFormat(material) {
  const filename = String(material?.uploaded?.filename || "");
  const extension = filename.includes(".") ? filename.split(".").pop().toLowerCase() : "";
  return researchTabularExtensions.has(extension) ? extension : "";
}

function splitResearchCsvHeader(line, delimiter = ",") {
  const cells = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    if (character === '"' && line[index + 1] === '"' && quoted) {
      current += '"'; index += 1; continue;
    }
    if (character === '"') { quoted = !quoted; continue; }
    if (character === delimiter && !quoted) {
      cells.push(current.trim()); current = ""; continue;
    }
    current += character;
  }
  cells.push(current.trim());
  return cells.map((item) => item.replace(/^\uFEFF/, "").trim()).filter(Boolean);
}

function researchTabularColumns(material) {
  const format = researchTabularFormat(material);
  const extracted = String(material?.uploaded?.extracted_text || "").trim();
  if (!extracted) return [];
  if (format === "json") {
    try {
      const parsed = JSON.parse(extracted);
      const rows = Array.isArray(parsed) ? parsed : [parsed];
      return rows.length && rows[0] && typeof rows[0] === "object"
        ? Object.keys(rows[0])
        : [];
    } catch (_error) { return []; }
  }
  const firstLine = extracted.split(/\r?\n/).find((line) => line.trim());
  return firstLine ? splitResearchCsvHeader(firstLine, format === "tsv" ? "\t" : ",") : [];
}

function inferResearchAnalysisInputs(question, materials) {
  const normalizedQuestion = String(question || "").toLowerCase();
  const tabular = materials.find((item) => researchTabularFormat(item));
  const columns = researchTabularColumns(tabular);
  const findColumn = (patterns) => columns.find((column) => {
    const normalized = column.toLowerCase();
    return patterns.some((pattern) => normalized.includes(pattern));
  });
  const outcome = findColumn(["score", "outcome", "result", "endpoint", "结局", "指标", "分数"]);
  const treatment = findColumn(["treatment", "group", "arm", "condition", "intervention", "处理", "分组", "组别"]);
  const identifier = findColumn(["id", "subject", "participant", "受试者", "样本"]);
  const comparisonRequested = /比较|差异|效应量|置信区间|不确定性|compare|difference|effect|uncertainty|interval/.test(normalizedQuestion);
  const randomized = /随机|双臂|对照|处理组|treatment|control|random|controlled|trial/.test(normalizedQuestion);
  const variables = [
    identifier ? { name: identifier, role: "identifier", unit: "", description: "受试者标识" } : null,
    outcome ? { name: outcome, role: "outcome", unit: outcome.toLowerCase().includes("score") ? "score" : "", description: "主要结局" } : null,
    treatment ? { name: treatment, role: "treatment", unit: "label", description: "随机分配的处理/对照组" } : null,
  ].filter(Boolean);
  return {
    design: randomized ? "experimental_comparison" : "",
    analysisGoal: comparisonRequested ? "estimate_effect" : "describe",
    estimand: outcome ? `treatment 与 control 的 ${outcome} 平均差异` : "处理组与对照组结果指标的平均差异",
    unit: /每行|每名受试者|受试者一行|participant|subject/.test(normalizedQuestion)
      ? "每位受试者一行" : "每行代表一个分析单位",
    variables,
    dataDictionary: columns.map((column) => `${column}: ${column === outcome ? "主要结局" : column === treatment ? "处理/对照分组" : column === identifier ? "受试者标识" : "待补证据"}`).join("\n"),
    studyDesign: randomized ? question : "",
  };
}

function buildResearchAnalysisV2(question, materials = []) {
  if (!researchAnalysisV2Enabled(question)) return null;
  const rawManifest = $("#research-analysis-manifest").value.trim();
  const dataManifest = parseResearchAnalysisJson(rawManifest, "数据清单");
  const rawEvidence = $("#research-analysis-evidence").value.trim();
  const evidence = parseResearchAnalysisJson(rawEvidence, "方法证据");
  if (evidence !== undefined && !Array.isArray(evidence)) {
    throw new Error("方法证据必须是 JSON 数组");
  }
  const resamplingMethod = $("#research-analysis-resampling").value;
  const requestedReplicates = Number(
    $("#research-analysis-bootstrap-replicates").value || 0
  );
  const request = {
    research_question: question || "请先补充研究问题",
    hypothesis: $("#research-analysis-hypothesis").value.trim(),
    analysis_goal: $("#research-analysis-goal").value,
    design: $("#research-analysis-design").value,
    estimand: $("#research-analysis-estimand").value.trim(),
    unit_of_analysis: $("#research-analysis-unit").value.trim(),
    study_design: $("#research-analysis-study-design").value.trim(),
    resampling_method: resamplingMethod,
    bootstrap_replicates: resamplingMethod === "bootstrap"
      ? Math.max(100, Math.min(10000, requestedReplicates))
      : 0,
    random_seed: 0,
    multiple_comparison_method: $("#research-analysis-multiple-comparison").value,
    variables: parseResearchAnalysisVariables($("#research-analysis-variables").value),
    data_dictionary: $("#research-analysis-dictionary").value.trim(),
    exploratory: $("#research-analysis-exploratory").value === "true",
  };
  if (dataManifest) request.data_manifest = dataManifest;
  const tabularMaterials = materials.filter((item) => researchTabularFormat(item));
  if (tabularMaterials.length > 1) {
    throw new Error("科研分析当前只允许一个主数据文件；其他文件可作为辅助材料");
  }
  const inferred = inferResearchAnalysisInputs(question, materials);
  if (request.design === "experimental_comparison" && inferred.design) request.design = inferred.design;
  if (request.analysis_goal === "describe" && inferred.analysisGoal !== "describe") {
    request.analysis_goal = inferred.analysisGoal;
  }
  if (!request.estimand && request.analysis_goal === "estimate_effect") request.estimand = inferred.estimand;
  if (!request.unit_of_analysis) request.unit_of_analysis = inferred.unit;
  if (!request.variables.length) request.variables = inferred.variables;
  if (!request.study_design) request.study_design = inferred.studyDesign;
  if (!request.data_dictionary) request.data_dictionary = inferred.dataDictionary;
  if (tabularMaterials.length === 1) {
    const uploaded = tabularMaterials[0].uploaded;
    const format = researchTabularFormat(tabularMaterials[0]);
    request.data_manifest = {
      ...(dataManifest || {}),
      dataset_id: dataManifest?.dataset_id || uploaded.id,
      version: dataManifest?.version || "upload",
      format: dataManifest?.format && dataManifest.format !== "unknown"
        ? dataManifest.format
        : format,
      checksum_sha256: dataManifest?.checksum_sha256 || uploaded.checksum_sha256,
      authorized: dataManifest?.authorized ?? true,
      contains_sensitive_data: dataManifest?.contains_sensitive_data ?? false,
      source_ref: dataManifest?.source_ref || `attachment:${uploaded.id}`,
    };
  }
  if (evidence) request.evidence = evidence;
  return { request, execute: tabularMaterials.length === 1 };
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
  if (state.sessionId && !force) {
    try {
      await api(`/api/v1/sessions/${state.sessionId}?user_id=${encodeURIComponent(state.userId)}`);
      return state.sessionId;
    } catch (_error) {
      state.sessionId = "";
      localStorage.removeItem("xinzhi_student_session");
    }
  }
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
  state.historyRequestSequence += 1;
  state.runSequence += 1;
  state.activeTaskWait?.cancel();
  state.activeTaskWait = null;
  state.taskId = "";
  state.cancelRequested = false;
  conversationMaterialUrls.forEach((url) => URL.revokeObjectURL(url));
  conversationMaterialUrls = [];
  state.currentTask = null; state.archivedTaskIds.clear(); state.liveProcessSteps.clear();
  runtimeLearningRunId = "";
  runtimeLearningTaskId = "";
  runtimeTaskControls = null;
  state.lastQuestion = ""; state.lastAnswer = "";
  $("#messages").replaceChildren(); $("#answer-panel").hidden = true; $("#welcome").hidden = false;
  $("#context-task-title").textContent = "等待提问";
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

function externalPaperCard(item) {
  const rawUrl = String(item.url || "").trim();
  const category = item.metadata?.category === "conference"
    ? "相关会议"
    : item.source_type === "academic_paper"
      ? "学术论文"
      : "报道/网页";
  let safeUrl = "";
  try {
    const url = new URL(rawUrl, location.origin);
    if (["http:", "https:"].includes(url.protocol)) safeUrl = url.href;
  } catch (_) {
    safeUrl = "";
  }
  const metadata = [
    item.date_label ? `发表/更新 ${item.date_label}` : "时间未知",
    externalProviderLabels[item.provider] || item.provider || "学术来源",
    item.venue,
    item.citation_count != null ? `被引 ${item.citation_count} 次` : "引用数据未提供",
  ].filter(Boolean).join(" · ");
  const authors = Array.isArray(item.authors) ? item.authors.filter(Boolean).join(", ") : "";
  const abstract = item.abstract || "暂无摘要，建议打开原文查看。";
  const title = safeUrl
    ? el("a", { href: safeUrl, target: "_blank", rel: "noopener noreferrer", text: item.title || "未命名论文" })
    : el("span", { text: item.title || "未命名论文" });
  const actions = safeUrl
    ? el("a", { class: "external-paper-open", href: safeUrl, target: "_blank", rel: "noopener noreferrer", text: "打开论文" })
    : el("small", { text: "链接不可用" });
  return el("article", { class: "external-paper-card" }, [
    el("div", { class: "external-paper-header" }, [
      el("span", { class: "evidence-id", text: item.evidence_id || "paper" }),
      el("span", { class: "external-paper-date", text: category }),
    ]),
    el("h3", {}, title),
    el("small", { class: "external-paper-meta", text: metadata }),
    authors ? el("p", { class: "external-paper-authors", text: authors }) : null,
    el("p", { class: "external-paper-abstract", text: abstract }),
    el("div", { class: "external-paper-footer" }, [
      el("span", { text: item.doi ? `DOI: ${item.doi}` : item.arxiv_id ? `arXiv: ${item.arxiv_id}` : "" }),
      actions,
    ]),
  ].filter(Boolean));
}

function renderExternalPapers(items) {
  if (!items?.length) return null;
  return el("section", { class: "external-results" }, [
    el("div", { class: "external-results-heading" }, [
      el("strong", { text: `外部科研证据 ${items.length} 条 · 已通过相关性审核` }),
      el("span", { text: "论文、报道和会议线索均需打开原文核验" }),
    ]),
    ...items.map(externalPaperCard),
  ]);
}

function renderEvidence(items, presentation, relatedImages = [], externalItems = []) {
  state.evidence = items || [];
  const cards = state.evidence.map(evidenceCard);
  const imageCard = relatedImageCard(relatedImages);
  if (imageCard) cards.push(imageCard);
  const external = renderExternalPapers(externalItems);
  $("#context-evidence").replaceChildren(...(cards.length || external ? [...(external ? [external] : []), ...cards] : [el("div", { class: "context-empty" }, [el("strong", { text: "本次没有可展示的资料依据" }), el("p", { text: presentation?.evidence_message || "系统不会把未使用的候选资料显示为回答依据。" })]) ]));
}

function renderProcess(steps = []) {
  const list = el("div", { class: "process-list" });
  const statusLabels = {
    started: "进行中",
    running: "进行中",
    planned: "待执行",
    completed: "已完成",
    passed: "验证通过",
    failed: "需要检查",
    fallback: "已降级",
    skipped: "本次未执行",
  };
  (steps.length ? steps : [{ label: "等待任务执行", status: "skipped" }]).forEach((step) => {
    const status = String(step.status || "completed");
    const detail = String(step.detail || "").trim();
    const detailDisplay = ({ accepted: "已通过", fallback: "使用后备路径", partial: "部分完成" })[detail] || detail;
    const detailSuffix = detailDisplay && detailDisplay !== status ? ` · ${detailDisplay}` : "";
    list.append(el("div", { class: `process-step ${status === "started" ? "running" : status}` }, [
      el("span", { class: "process-dot" }),
      el("div", {}, [
        el("strong", { text: step.label }),
        el("span", { text: `${statusLabels[status] || status}${detailSuffix}` }),
      ]),
    ]));
  });
  $("#context-process").replaceChildren(list);
}

function liveProgressData(event) {
  try {
    const payload = JSON.parse(event.data || "{}");
    return payload.data && typeof payload.data === "object" ? payload.data : payload;
  } catch (_error) {
    return {};
  }
}

function updateLiveProgress(data = {}, fallback = {}) {
  const stageId = String(data.stage_id || fallback.stage_id || "").trim();
  if (!stageId) return;
  state.liveProcessSteps.set(stageId, {
    label: String(data.label || fallback.label || stageId),
    status: String(data.status || fallback.status || "running"),
    detail: String(data.detail || fallback.detail || ""),
  });
  renderProcess([...state.liveProcessSteps.values()]);
  selectContextTab("process");
}

function intentPlanSteps(plan = {}) {
  const labels = { retrieval: "检索证据", agent: "调用本地 Agent", tool: "调用工具", skill: "加载 Skill", verifier: "结果核验", compose: "组织回答" };
  return (plan.nodes || []).map((node) => ({
    label: `${labels[node.node_type] || "执行节点"} · ${node.target_id}`,
    status: "planned",
  }));
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
  const scenarioReview = result.structured_result?.scenario_evidence_review || {};
  const scenarioReviewStatus = scenarioReview.status === "approved"
    ? "证据审查通过"
    : scenarioReview.status === "rejected"
      ? "证据审查拒绝"
      : scenarioReview.status === "needs_manual_review"
        ? "需要人工复核"
        : scenarioReview.status === "pending_manual_review"
          ? "等待人工复核"
          : "未执行场景审查";
  const collaboration = result.provider === "local_agent" ? "内部 Agent 协作" : result.provider === "local" ? "本地知识增强" : result.provider === "mock" ? "开发演示" : "智能协作";
  const rows = [
    ["完成能力", presentation.title || summary.agent_label || "智能任务"],
    ["协作方式", collaboration],
    ["课程", courseLabels[task.course_id] || task.course_id],
    ["任务类型", intentLabels[task.intent] || "自动识别"],
    ["知识增强", ragLabels[summary.rag_mode] || "按需启用"],
    ["资料使用", `${summary.used_evidence_count || 0} / ${summary.evidence_count || 0} 条`],
    ["结果检查", summary.citation_status === "passed" ? "通过" : summary.citation_status === "failed" ? "需要复核" : "已完成结构检查"],
    ["场景证据审查", scenarioReviewStatus],
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

function runtimeTaskControlEntry(action) {
  const controls = Array.isArray(runtimeTaskControls?.controls)
    ? runtimeTaskControls.controls
    : [];
  return controls.find((item) => item?.action === action) || null;
}

function runtimeTaskControlAvailable(action) {
  if (action === "approve" || action === "reject") {
    return Boolean(
      runtimeTaskControls?.control_scope === "runtime_plan_proposal"
      && runtimeTaskControls?.plan_proposal?.proposal_id,
    ) || runtimeTaskControlEntry(action)?.available === true;
  }
  return runtimeTaskControlEntry(action)?.available === true;
}

function runtimeTaskControlMessage(projection) {
  if (!projection?.runtime_run_id) {
    return "当前任务尚未进入可控制的 Runtime；旧任务与未启动任务不会显示控制操作。";
  }
  if (
    projection.control_scope === "runtime_plan_proposal"
    && projection.plan_proposal?.proposal_id
  ) {
    return `Runtime proposal ${projection.plan_proposal.proposal_id} requires an explicit apply or reject decision.`;
  }
  const available = ["pause", "resume", "approve", "input"]
    .filter(runtimeTaskControlAvailable);
  if (available.length) {
    return "可用操作由服务端 checkpoint 和任务状态决定；提交后会从同一运行断点继续。";
  }
  const blocked = ["pause", "resume", "approve", "input"]
    .map(runtimeTaskControlEntry)
    .find((item) => item?.reason);
  return blocked?.reason || "当前 Runtime 状态没有可执行的人工控制操作。";
}

function renderRuntimeTaskControls() {
  const panel = $("#runtime-task-controls");
  if (!panel) return;
  const projection = runtimeTaskControls;
  const hasRuntime = Boolean(projection?.runtime_run_id);
  panel.hidden = !hasRuntime;
  if (!hasRuntime) return;

  const status = String(projection.status || "").toLowerCase();
  const proposalPending = Boolean(
    projection.control_scope === "runtime_plan_proposal"
    && projection.plan_proposal?.proposal_id,
  );
  $("#runtime-task-status").textContent = runtimeTaskStatusLabels[status]
    || "状态待确认";
  $("#runtime-task-controls-message").textContent = runtimeTaskControlMessage(projection);
  ["pause", "resume", "approve"].forEach((action) => {
    const button = $(`#runtime-task-${action}`);
    if (!button) return;
    const entry = runtimeTaskControlEntry(action);
    const available = proposalPending && action === "approve"
      ? true
      : entry?.available === true;
    button.hidden = !available;
    button.disabled = runtimeTaskControlsBusy || !available;
    if (proposalPending && action === "approve") button.textContent = "应用恢复计划";
    button.title = available ? "" : `${entry?.reason_code || "runtime_control_unavailable"}: ${entry?.reason || "当前状态不可用"}`;
  });
  const reject = $("#runtime-task-reject-proposal");
  if (reject) {
    reject.hidden = !proposalPending;
    reject.disabled = runtimeTaskControlsBusy || !proposalPending;
  }
  const inputAvailable = runtimeTaskControlAvailable("input");
  $("#runtime-task-input-form").hidden = !inputAvailable;
  $("#runtime-task-submit-input").disabled = runtimeTaskControlsBusy || !inputAvailable;
}

async function refreshRuntimeTaskControls(
  taskId = state.currentTask?.id || state.taskId,
  learningRunId = runtimeLearningTaskId === taskId ? runtimeLearningRunId : "",
) {
  if (!taskId) {
    runtimeTaskControls = null;
    renderRuntimeTaskControls();
    return null;
  }
  if (learningRunId) {
    runtimeLearningRunId = learningRunId;
    runtimeLearningTaskId = taskId;
  } else if (runtimeLearningTaskId !== taskId) {
    runtimeLearningRunId = "";
    runtimeLearningTaskId = "";
  }
  const requestSequence = runtimeTaskControlsRequest + 1;
  runtimeTaskControlsRequest = requestSequence;
  try {
    const projection = runtimeLearningRunId
      ? {
          ...(await api(
            `/api/v1/learning/runtime/${encodeURIComponent(runtimeLearningRunId)}/controls`,
          )),
          task_id: taskId,
          runtime_run_id: runtimeLearningRunId,
          control_scope: "learning_loop",
          control_request: "",
        }
      : await api(`/api/v1/tasks/${encodeURIComponent(taskId)}/runtime-controls`);
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
  const runId = String(runtimeTaskControls?.runtime_run_id || "").trim();
  if (
    runtimeTaskControls?.control_scope === "runtime_plan_proposal"
    && runtimeTaskControls?.plan_proposal?.proposal_id
  ) {
    return `/api/v1/tasks/${encodeURIComponent(state.currentTask?.id || state.taskId || "")}/runtime-plan-proposals/${encodeURIComponent(runtimeTaskControls.plan_proposal.proposal_id)}/decision`;
  }
  if (runtimeTaskControls?.control_scope === "learning_loop" && runId) {
    return `/api/v1/learning/runtime/${encodeURIComponent(runId)}/control`;
  }
  const query = runId ? `?runtime_run_id=${encodeURIComponent(runId)}` : "";
  return `/api/v1/tasks/${encodeURIComponent(state.currentTask?.id || state.taskId || "")}/${action}${query}`;
}

async function submitRuntimeTaskControl(action, payload = null) {
  const taskId = state.currentTask?.id || state.taskId;
  if (!taskId || !runtimeTaskControlAvailable(action)) return;
  runtimeTaskControlsBusy = true;
  renderRuntimeTaskControls();
  try {
    const learningControl = runtimeTaskControls?.control_scope === "learning_loop";
    const planProposalControl = runtimeTaskControls?.control_scope === "runtime_plan_proposal";
    const options = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      ...(planProposalControl
        ? {
            body: JSON.stringify({
              decision: action === "approve" ? "approved" : "rejected",
              reason: payload?.reason || "",
              expected_state_version: runtimeTaskControls?.plan_proposal?.state_version,
            }),
          }
        : learningControl
        ? {
            body: JSON.stringify({
              action,
              expected_state_version: runtimeTaskControls?.state_version,
              idempotency_key: `workspace_${action}_${crypto.randomUUID()}`,
              data: payload || {},
            }),
          }
        : payload
          ? { body: JSON.stringify(payload) }
          : {}),
    };
    const task = await api(runtimeTaskControlUrl(action), options);
    if (!learningControl) state.currentTask = task;
    if (action === "input") $("#runtime-task-input").value = "";
    await refreshRuntimeTaskControls(state.currentTask?.id || state.taskId);
    toast(action === "pause" ? "已提交暂停请求，将在安全边界暂停。" : action === "resume" ? "已提交恢复请求。" : action === "approve" ? "审批已提交，任务将从断点继续。" : "补充信息已提交，任务将从断点继续。");
  } catch (error) {
    const status = Number(error?.status);
    const message = status === 403
      ? "当前身份无权执行该 Runtime 控制操作。"
      : status === 409
        ? "Runtime 状态已变化，请刷新后重试。"
        : error?.message || "Runtime 控制操作未完成。";
    toast(message, "failed");
    await refreshRuntimeTaskControls(taskId);
  } finally {
    runtimeTaskControlsBusy = false;
    renderRuntimeTaskControls();
  }
}

async function submitRuntimeTaskInput(event) {
  event.preventDefault();
  const text = $("#runtime-task-input").value.trim();
  if (!text) {
    $("#runtime-task-input").focus();
    toast("请先填写要补充给 Runtime 的信息。", "degraded");
    return;
  }
  await submitRuntimeTaskControl("input", {
    expected_state_version: runtimeTaskControls?.state_version,
    data: { text },
  });
}

function prepareTaskFeedback(task) {
  const panel = $("#task-feedback-panel");
  if (!panel) return;
  if (state.feedbackEnabled !== true) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  panel.dataset.taskId = task.id;
  $("#task-feedback-message").textContent = "";
  $("#submit-task-feedback").disabled = false;
}

async function loadFeedbackFeatureStatus() {
  try {
    const status = await api("/api/v1/feedback/status");
    state.feedbackEnabled = status.enabled === true;
  } catch (_error) {
    state.feedbackEnabled = true;
  }
  if (state.currentTask) prepareTaskFeedback(state.currentTask);
}

async function submitTaskFeedback() {
  if (!state.currentTask?.id) {
    toast("请先完成一道题或一次知识问答", "degraded");
    return;
  }
  const resolvedValue = $("#task-feedback-resolved").value;
  const satisfaction = $("#task-feedback-satisfaction").value || null;
  const problemType = $("#task-feedback-problem-type").value || null;
  const manualReview = $("#task-feedback-review").checked;
  const comment = $("#task-feedback-comment").value.trim();
  if (!resolvedValue && !satisfaction && !problemType && !manualReview && !comment) {
    toast("请至少选择一项反馈", "degraded");
    return;
  }
  const button = $("#submit-task-feedback");
  button.disabled = true;
  try {
    await api("/api/v1/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_id: state.currentTask.id,
        resolved: resolvedValue === "" ? null : resolvedValue === "true",
        satisfaction,
        problem_type: problemType,
        manual_review_required: manualReview,
        comment,
      }),
    });
    $("#task-feedback-message").textContent = "反馈已记录，可继续修改后重新提交。";
    toast("反馈已记录");
  } catch (error) {
    $("#task-feedback-message").textContent = error.message;
    toast(error.message, "failed");
  } finally {
    button.disabled = false;
  }
}

function renderResult(task) {
  const renderStarted = performance.now();
  const result = task.result_content || {}; const structured = result.structured_result || {};
  const presentation = presentationFor(task, result);
  const summary = structured.execution_summary || {};
  const evidence = structured.evidence_view || [];
  const externalItems = structured.external_search_view || structured.external_retrieval?.items || [];
  state.lastAnswer = displayAnswer(task, result);
  state.currentTask = task;
  prepareTaskFeedback(task);
  void refreshRuntimeTaskControls(task.id);
  $("#answer-panel").hidden = false;
  $("#answer-status").textContent = presentation.status_label || "已完成";
  $("#answer-title").textContent = presentation.title;
  $("#answer-source-chip").textContent = presentation.source_summary;
  $("#context-task-title").textContent = presentation.title;
  renderMarkdown($("#answer-text"), state.lastAnswer);
  renderTeachingLoop(structured);
  void loadLearningProgress(task);
  renderBusinessView(structured.business_view || researchBriefView(structured.research_brief), state.lastAnswer, structured);
  const notices = [];
  if (summary.mock || result.provider === "mock" || result.mock_used) notices.push({ status: "mock", text: "当前为开发态模拟结果，不代表正式智能能力输出。" });
  if (presentation.answer_quality_message) notices.push({
    status: presentation.requires_review ? "warning" : "",
    text: presentation.answer_quality_message,
  });
  if (presentation.fallback_message) notices.push({ status: "warning", text: presentation.fallback_message });
  if (presentation.evidence_message) notices.push({ status: "", text: presentation.evidence_message });
  const scenarioReview = structured.scenario_evidence_review || {};
  if (["pending_manual_review", "needs_manual_review"].includes(scenarioReview.status)) {
    notices.push({
      status: "warning",
      text: "当前场景要求人工复核外部证据；系统不会把合成资料或未核验来源当作正式结论。",
    });
  } else if (scenarioReview.status === "rejected") {
    notices.push({
      status: "warning",
      text: "当前场景的外部证据未通过审查，请先替换或核验来源后再用于正式交付。",
    });
  }
  if (structured.teaching?.warning) notices.push({ status: "warning", text: structured.teaching.warning });
  if (structured.teaching?.teaching_mode === "check_my_work") notices.push({ status: "warning", text: structured.teaching.diagnostic_scope });
  if (structured.student_attempt_review?.feedback?.length) notices.push({ status: "", text: structured.student_attempt_review.feedback.join("；") });
  $("#answer-notices").replaceChildren(...notices.map((item) => el("div", { class: `notice ${item.status}`, text: item.text })));
  const relatedImages = [
    ...(structured.related_images || []),
    ...(result.related_images || []),
    ...(structured.knowledge?.images || []),
  ];
  const executionSteps = presentation.execution_steps?.length
    ? presentation.execution_steps
    : intentPlanSteps(structured.intent_plan);
  if (state.liveProcessSteps.size && ["completed", "failed"].includes(task.status)) {
    state.liveProcessSteps.forEach((step) => {
      if (["started", "running", "planned"].includes(step.status)) {
        step.status = task.status === "completed" ? "completed" : "failed";
      }
    });
  }
  const finalSteps = state.liveProcessSteps.size
    ? [...state.liveProcessSteps.values()]
    : executionSteps;
  renderEvidence(evidence, presentation, relatedImages, externalItems); renderProcess(finalSteps);
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
  const sessionId = state.sessionId;
  const requestSequence = ++state.historyRequestSequence;
  const isCurrent = () => requestSequence === state.historyRequestSequence && state.sessionId === sessionId;
  try {
    const messages = await api(`/api/v1/sessions/${sessionId}/messages?user_id=${encodeURIComponent(state.userId)}&limit=100`);
    if (!isCurrent()) return;
    if (!messages.length) return;

    const latestAssistantTask = [...messages].reverse().find((item) => item.role === "assistant" && item.source_task_id);
    let restoredTask = null;
    if (latestAssistantTask) {
      try {
        const candidate = await api(ownedTaskUrl(latestAssistantTask.source_task_id));
        if (isCurrent() && candidate.status === "completed") restoredTask = candidate;
      } catch (_error) {
        restoredTask = null;
      }
    }
    if (!isCurrent()) return;

    $("#welcome").hidden = true;
    const renderedAssistantTaskIds = new Set();
    messages.forEach((message) => {
      if (message.role === "user") {
        const article = addMessage(message.content_text, "user", message.source_task_id || "");
        appendStoredAttachmentImages(article, message.attachment_ids || []);
      } else if (message.role === "assistant") {
        const taskId = message.source_task_id || "";
        if (taskId && (taskId === restoredTask?.id || renderedAssistantTaskIds.has(taskId))) return;
        const body = el("div", { class: "message-body" }, [
          el("span", { class: "message-meta", text: message.status === "completed" ? "已完成" : message.status }),
          el("div", { class: "markdown-view" }),
        ]);
        renderMarkdown(body.lastElementChild, message.content_text);
        $("#messages").append(el("article", { class: "conversation-message assistant", "data-task-id": taskId }, [
          el("span", { class: "message-role", text: "芯智导学" }), body,
        ]));
        if (taskId) {
          renderedAssistantTaskIds.add(taskId);
          state.archivedTaskIds.add(taskId);
        }
      } else if (message.role === "system_event") {
        addMessage(message.content_text, "system", message.source_task_id || "");
      }
    });
    const latest = messages[messages.length - 1];
    state.lastQuestion = [...messages].reverse().find((item) => item.role === "user")?.content_text || "";
    if (latest.role === "user" && latest.source_task_id) {
      const latestTask = await api(ownedTaskUrl(latest.source_task_id));
      if (!isCurrent()) return;
      if (["created", "queued", "running"].includes(latestTask.status)) {
        state.taskId = latestTask.id;
        setBusy(true);
        try {
          const finishedTask = await waitForTask(latestTask.id, requestSequence);
          if (finishedTask && isCurrent()) renderResult(finishedTask);
        } finally {
          if (isCurrent()) { state.taskId = ""; setBusy(false); }
        }
      }
    }
    if (restoredTask && isCurrent()) renderResult(restoredTask);
  } catch (error) {
    if (!isCurrent()) return;
    try {
      const tasks = await api(`/api/v1/sessions/${sessionId}/tasks?limit=50`);
      if (!isCurrent()) return;
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

function businessContentValues(value) {
  if (Array.isArray(value)) return value.flatMap(businessContentValues);
  if (value && typeof value === "object") return Object.values(value).flatMap(businessContentValues);
  return value == null ? [] : [String(value)];
}

function businessSectionAlreadyInAnswer(answer, section) {
  const normalizedAnswer = String(answer || "").replace(/\s+/g, " ").trim();
  const values = businessContentValues(section.content)
    .map((value) => value.replace(/\s+/g, " ").trim())
    .filter((value) => value.length >= 4);
  return values.length > 0 && values.every((value) => normalizedAnswer.includes(value));
}

function businessSectionText(section) {
  if (section.key === "analysis_status") {
    return {
      plan: "分析方案",
      interpreted: "已完成解释",
      insufficient_data: "数据不足",
    }[String(section.content)] || String(section.content || "");
  }
  if (Array.isArray(section.content)) {
    return section.content.map((item) => {
      if (item && typeof item === "object") {
        const reviewId = item.review_id || item.id || "item";
        const question = item.question || item.label || item.title || "";
        const status = item.status ? ` [${item.status}]` : "";
        return `- ${reviewId}${status}：${question || JSON.stringify(item)}`;
      }
      return `- ${String(item)}`;
    }).join("\n");
  }
  if (section.content && typeof section.content === "object") {
    return Object.entries(section.content)
      .map(([key, value]) => `- ${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`)
      .join("\n");
  }
  return String(section.content ?? "");
}

function researchBriefView(brief = {}) {
  if (!brief || !brief.executive_summary) return {};
  const sections = [
    { key: "research_summary", label: "研究摘要", content: brief.executive_summary },
    { key: "research_findings", label: "关键发现与证据", content: (brief.key_findings || []).map((item, index) => `${index + 1}. **${item.claim}** ${(item.evidence_ids || []).map((id) => `[${id}]`).join(" ")}\n   - 意义：${item.why_it_matters || "待结合原文判断"}\n   - 置信度：${item.confidence || "medium"}`).join("\n\n") },
    { key: "research_timeline", label: "时间线", content: (brief.timeline || []).map((item) => `- **${item.date_label}**：${item.event} ${(item.evidence_ids || []).map((id) => `[${id}]`).join(" ")}`).join("\n") },
    { key: "research_open_questions", label: "开放问题", content: (brief.open_questions || []).map((item) => `- ${item}`).join("\n") },
    { key: "research_next_steps", label: "延展检索建议", content: (brief.next_steps || []).map((item) => `- ${item}`).join("\n") },
  ].filter((section) => section.content);
  return { renderer_type: "research_brief", sections };
}

function researchAnalysisV2Summary(view) {
  const sections = Object.fromEntries((view.sections || []).map((section) => [section.key, section.content]));
  const plan = sections.plan && typeof sections.plan === "object" ? sections.plan : {};
  const quality = sections.data_quality && typeof sections.data_quality === "object" ? sections.data_quality : {};
  const review = sections.review_checklist && typeof sections.review_checklist === "object" ? sections.review_checklist : {};
  const statusLabels = {
    planning: "计划中",
    quality_blocked: "质量门禁阻断",
    ready_for_execution: "可执行待确认",
    executed: "本地计算完成",
    needs_review: "需要人工复核",
    insufficient_data: "数据不足",
    failed: "执行失败",
  };
  const designLabels = {
    experimental_comparison: "两组实验比较",
    small_sample: "小样本两组比较",
    multigroup_comparison: "多组比较",
    repeated_measures: "重复测量比较",
    observational_regression: "观察性回归",
    time_series: "时间序列",
    prediction: "预测分析",
    unknown: "尚未确定",
  };
  const qualityLabels = {
    passed: "通过",
    needs_review: "需要复核",
    blocked: "未通过",
    not_checked: "尚未检查",
  };
  const metric = (label, value, tone = "") => el("div", { class: `research-v2-metric ${tone}` }, [
    el("span", { text: label }),
    el("strong", { text: String(value || "待补") }),
  ]);
  return el("section", { class: "research-v2-summary", "aria-label": "科研分析 V2 摘要" }, [
    el("div", { class: "research-v2-summary-heading" }, [
      el("div", {}, [
        el("strong", { text: "科研分析 V2 审查摘要" }),
        el("small", { text: "确定性本地分析 · 不替代研究者签字" }),
      ]),
      el("span", { class: "status-badge status-warning", text: statusLabels[String(sections.status)] || String(sections.status || "待定") }),
    ]),
    el("div", { class: "research-v2-metrics" }, [
      metric("研究设计", designLabels[plan.design] || "尚未确定"),
      metric("质量门禁", qualityLabels[quality.status] || "尚未检查", quality.status === "blocked" ? "danger" : ""),
      metric("诊断条目", Array.isArray(sections.diagnostics) ? sections.diagnostics.length : 0),
      metric("稳健性条目", Array.isArray(sections.robustness_findings) ? sections.robustness_findings.length : 0),
      metric("复核状态", review.ready_for_signoff === true ? "待签字" : "未通过签字门禁", "danger"),
    ]),
  ]);
}

function renderBusinessView(view, answer = "", structured = {}) {
  const root = $("#business-result"); root.replaceChildren();
  if (view.banner) root.append(el("div", { class: "notice warning", text: view.banner }));
  const isResearchAnalysisV2 = structured.analysis_v2 === true
    || (view.sections || []).some((section) => section.key === "review_checklist")
    || (view.sections || []).some((section) => section.key === "effect_estimates" && section.content);
  if (isResearchAnalysisV2) root.append(researchAnalysisV2Summary(view));
  const hiddenResearchFields = new Set([
    "analysis_steps",
    "reproducibility_requirements",
    "design_assessment",
    "data_quality",
    "status",
    "plan",
    "primary_result",
    "effect_estimates",
    "uncertainty_summary",
    "diagnostics",
    "robustness_findings",
    "interpretation",
    "limitations",
    "provenance",
    "artifacts",
    "review_checklist",
    "evidence_ids",
    "evidence_references",
  ]);
  const sections = (view.sections || []).filter((section, index, allSections) => {
    if (isResearchAnalysisV2 && hiddenResearchFields.has(section.key)) {
      return false;
    }
    if (view.renderer_type === "lesson_prep" && section.key === "activities") {
      const flow = allSections.find((candidate) => candidate.key === "lesson_flow");
      if (flow && JSON.stringify(flow.content) === JSON.stringify(section.content)) return false;
    }
    // Some local agents intentionally return both a readable Markdown answer
    // and a structured business view. Keep one representation in the UI.
    return !businessSectionAlreadyInAnswer(answer, section);
  });
  sections.forEach((section) => {
    const card = el("section", { class: `business-section business-${section.key}` });
    card.append(el("h3", { text: section.label }));
    const content = businessSectionText(section);
    card.append(el("div", { class: "markdown-view" })); renderMarkdown(card.lastElementChild, content);
    root.append(card);
  });
}

function selectedMaterialFiles() {
  return [...pendingMaterialFiles];
}

function validateMaterialFiles(files) {
  const allowed = ["image/jpeg", "image/png", "image/webp", "text/plain", "text/markdown", "text/csv", "text/tab-separated-values", "application/json", "application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.apache.parquet"];
  if (files.length > maxMultiImageFiles) throw new Error(`一次最多上传 ${maxMultiImageFiles} 个材料`);
  files.forEach((file) => {
    if (!allowed.includes(file.type) && !/\.(md|txt|csv|json|pdf|doc|docx|xlsx|parquet)$/i.test(file.name)) throw new Error(`暂不支持材料类型：${file.name}`);
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
    if (["failed", "processing", "pending"].includes(uploaded.ingestion_status)) throw new Error(uploaded.extraction_error || `材料解析失败：${file.name}`);
    materials.push({ uploaded, extractedText: uploaded.extracted_text || "", originalType: file.type });
  }
  return materials;
}
function attachmentRef(file) { return { file_id: file.id, filename: file.filename, content_type: file.content_type, size_bytes: file.size_bytes, storage_key: file.storage_key, checksum_sha256: file.checksum_sha256 }; }

async function waitForTask(id, runSequence) {
  state.liveProcessSteps.clear();
  return new Promise((resolve, reject) => {
    let settled = false; let pollTimer = null; const events = new EventSource(`/api/v1/tasks/${id}/stream`);
    const cleanup = () => {
      events.close();
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      if (state.activeTaskWait?.runSequence === runSequence) state.activeTaskWait = null;
    };
    const cancel = () => { if (settled) return; settled = true; cleanup(); resolve(null); };
    state.activeTaskWait = { runSequence, cancel };
    const finish = async () => { if (settled) return; try { const task = await api(ownedTaskUrl(id)); if (["completed", "failed", "cancelled"].includes(task.status)) { settled = true; cleanup(); resolve(task); } } catch (error) { settled = true; cleanup(); reject(error); } };
    ["task.completed", "task.failed", "task.cancelled"].forEach((name) => events.addEventListener(name, finish));
    events.addEventListener("intent.recognized", () => addMessage("已识别用户意图，正在选择能力与执行方式…", "system"));
    events.addEventListener("plan.created", () => { addMessage("已生成执行计划，按依赖关系调度本地 Agent 与检索能力…", "system"); selectContextTab("process"); });
    events.addEventListener("agent.started", () => addMessage("已完成能力编排，内部 Agent 正在协作处理…", "system"));
    events.addEventListener("knowledge.retrieved", () => { addMessage("已完成课程资料检索，正在整理本次证据…", "system"); selectContextTab("process"); });
    const progressEventLabels = {
      "plan.node_started": "\u6b63\u5728\u6267\u884c\u8ba1\u5212\u8282\u70b9",
      "plan.node_completed": "\u8ba1\u5212\u8282\u70b9\u5df2\u5b8c\u6210",
      "knowledge.query_normalized": "\u5df2\u5b8c\u6210\u77e5\u8bc6\u68c0\u7d22\u5b9a\u4f4d",
      "knowledge.context_built": "\u5df2\u7ec4\u88c5\u8bfe\u7a0b\u8bc1\u636e",
      "knowledge.insufficient": "\u8bfe\u7a0b\u8bc1\u636e\u4e0d\u8db3\uff0c\u8fdb\u5165\u4fdd\u5b88\u56de\u7b54",
      "external_retrieval.started": "\u6b63\u5728\u68c0\u7d22\u5916\u90e8\u8bc1\u636e",
      "external_retrieval.completed": "\u5916\u90e8\u8bc1\u636e\u68c0\u7d22\u5b8c\u6210",
      "external_retrieval.failed": "\u5916\u90e8\u8bc1\u636e\u68c0\u7d22\u672a\u5b8c\u6210",
    };
    Object.entries(progressEventLabels).forEach(([name, label]) => {
      events.addEventListener(name, (event) => {
        const data = liveProgressData(event);
        const terminal = name.endsWith(".completed") || name.endsWith(".failed")
          || name === "knowledge.context_built" || name === "knowledge.insufficient";
        updateLiveProgress(data, {
          stage_id: String(data.stage_id || data.node_id || name),
          status: terminal
            ? (name.endsWith(".failed") || name === "knowledge.insufficient" ? "failed" : "completed")
            : "running",
          label,
        });
        void refreshRuntimeTaskControls(id);
      });
    });
    events.addEventListener("agent.progress", (event) => {
      updateLiveProgress(liveProgressData(event));
      void refreshRuntimeTaskControls(id);
    });
    events.onerror = () => {
      if (settled) return;
      events.close();
      if (pollTimer) return;
      pollTimer = setInterval(async () => {
        if (settled) return;
        try {
          const task = await api(ownedTaskUrl(id));
          if (["completed", "failed", "cancelled"].includes(task.status)) { settled = true; cleanup(); resolve(task); }
        } catch (error) { settled = true; cleanup(); reject(error); }
      }, 900);
    };
  });
}

function setBusy(busy) {
  $("#send-button").disabled = busy; $("#stop-button").disabled = !busy; $("#question-input").disabled = busy; $("#student-attempt-input").disabled = busy; $("#teaching-mode").disabled = busy; $("#image-input").disabled = busy; $("#remove-image").disabled = busy;
  $("#teaching-response-input").disabled = busy;
  $("#submit-teaching-response").disabled = busy;
  $("#request-more-hint").disabled = busy;
  $("#switch-direct-answer").disabled = busy;
}

function markAnswerPending() {
  $("#context-task-title").textContent = "正在处理当前任务";
  $("#answer-panel").hidden = false;
  $("#answer-status").textContent = "\u6b63\u5728\u6267\u884c";
  $("#answer-title").textContent = "\u6b63\u5728\u7ec4\u7ec7\u56de\u7b54";
  $("#answer-source-chip").textContent = "\u7b49\u5f85\u672c\u8f6e\u7ed3\u679c";
}

function markAnswerCancelled() {
  $("#answer-panel").hidden = false;
  $("#answer-status").textContent = "\u5df2\u505c\u6b62";
  $("#answer-title").textContent = "\u4efb\u52a1\u5df2\u505c\u6b62";
  $("#answer-source-chip").textContent = "\u672a\u751f\u6210\u65b0\u7ed3\u679c";
  $("#context-task-title").textContent = "\u4efb\u52a1\u5df2\u505c\u6b62";
  renderMarkdown($("#answer-text"), "");
  $("#answer-notices").replaceChildren(el("div", {
    class: "notice warning",
    text: "\u672c\u6b21\u4efb\u52a1\u5df2\u505c\u6b62\uff0c\u672a\u751f\u6210\u65b0\u56de\u7b54\u3002",
  }));
  renderProcess([{ label: "\u672c\u6b21\u4efb\u52a1\u5df2\u505c\u6b62", status: "skipped" }]);
}

async function submit(event) {
  event.preventDefault(); if (state.taskId) return;
  await identityReady;
  await scenarioRoleRequest;
  if (!scenarioRoleAllowed()) {
    $("#form-error").textContent = scenarioRoleMessage();
    return;
  }
  const runSequence = state.runSequence + 1;
  state.runSequence = runSequence;
  state.cancelRequested = false;
  $("#form-error").textContent = "";
  const question = $("#question-input").value.trim(); const course = selectedCourse();
  const teachingMode = $("#teaching-mode").value;
  const studentAttempt = $("#student-attempt-input").value.trim();
  const learningFollowUp = pendingLearningFollowUp;
  const requestedCourse = learningFollowUp?.course_id || course;
  const requestedIntent = learningFollowUp?.intent || state.intentOverride || "unknown";
  const selectedFiles = selectedMaterialFiles();
  if (!question && !selectedFiles.length) { $("#form-error").textContent = "请输入题目或上传材料"; return; }
  if (teachingMode === "check_my_work" && !studentAttempt) { $("#form-error").textContent = "请填写你的解题过程或答案"; return; }
  state.lastQuestion = question; state.activeMemoryIds.clear(); setBusy(true);
  markAnswerPending();
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
    const tabularMaterials = materials.filter((item) => researchTabularFormat(item));
    if (tabularMaterials.length === 1) {
      canonical.data_description = [
        question ? `用户分析说明：${question}` : "",
        uploadedText || `已上传结构化数据文件：${tabularMaterials[0].uploaded.filename}`,
      ].filter(Boolean).join("\n\n");
    }
    const options = { request_id: `student_${crypto.randomUUID()}`, response_depth: $("#depth-select").value, teaching_mode: teachingMode, student_attempt: teachingMode === "check_my_work" ? { raw_text: studentAttempt } : undefined, prefer_internal_agents: true, use_local_rag: true, allow_cloud: false, source_task_id: learningFollowUp?.source_task_id || "", learning_action: learningFollowUp?.action || "" };
    const researchAnalysis = buildResearchAnalysisV2(question, materials);
    if (researchAnalysis) options.research_analysis_v2 = researchAnalysis;
    const payload = { session_id: state.sessionId, user_id: state.userId, user_role: state.userRole, scene: "dispatch", course_id: requestedCourse, intent: requestedIntent, scenario_id: scenarioId || null, canonical_input: canonical, attachments: materials.map((item) => attachmentRef(item.uploaded)), context_refs: [], options };
    const task = await api("/api/v1/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    pendingLearningFollowUp = null;
    state.taskId = task.id; state.currentTask = task; localStorage.setItem("xinzhi_last_task", task.id); addMessage("已识别：自动识别", "system");
    void refreshRuntimeTaskControls(task.id);
    const finishedTask = await waitForTask(task.id, runSequence);
    if (!finishedTask || runSequence !== state.runSequence || state.cancelRequested) return;
    renderResult(finishedTask); await loadSessionList();
    $("#question-input").value = ""; $("#student-attempt-input").value = ""; autoGrow(); clearImage();
  } catch (error) { $("#form-error").textContent = `${error.message}。请检查本地服务后重试。`; }
  finally { if (runSequence === state.runSequence) { state.taskId = ""; setBusy(false); } }
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
function applyParams() { if (params.get("course")) $("#course-select").value = params.get("course"); if (params.get("prompt")) $("#question-input").value = params.get("prompt"); updateResearchAnalysisPanel(); }

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
    if (result.runtime_run_id && state.currentTask?.id) {
      await refreshRuntimeTaskControls(
        state.currentTask.id,
        result.runtime_run_id,
      );
    }
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

window.addEventListener("DOMContentLoaded", () => {
  initShell({ page: "workspace", title: "智能任务工作台", description: "内部 Agent 与本地课程资料协同", context: "自动编排 · 本地知识增强", audience: requestedWorkspaceRole });
  applyParams(); updateShell(); updateTeachingMode(); autoGrow(); initializeResizablePanels();
  identityReady = initIdentityGate({ next: `${location.pathname}${location.search}` }).then((identity) => {
    state.userRole = effectiveWorkspaceRole(identity);
    if (identity?.user_id || identity?.id) {
      const identityId = identity.user_id || identity.id;
      if (state.userId !== identityId) {
        state.sessionId = "";
        localStorage.removeItem("xinzhi_student_session");
      }
      state.userId = identityId;
      localStorage.setItem("xinzhi_student_user", state.userId);
    }
    const schedule = window.requestIdleCallback
      ? (callback) => window.requestIdleCallback(callback, { timeout: 1200 })
      : (callback) => window.setTimeout(callback, 80);
    schedule(() => {
      void loadCapabilities();
      void loadSessionHistory();
      void loadSessionList();
      void loadFeedbackFeatureStatus();
    });
    return identity;
  });
  scenarioRoleRequest = identityReady.then(loadScenarioRolePolicy);
  if (innerWidth <= 1180 && !document.body.classList.contains("presentation-mode")) setContextOpen(false);
  all("[data-prompt]").forEach((button) => button.addEventListener("click", () => { $("#question-input").value = button.dataset.prompt; $("#course-select").value = button.dataset.course || "AUTO"; state.intentOverride = button.dataset.intent || ""; updateResearchAnalysisPanel(); updateShell(); autoGrow(); $("#question-input").focus(); }));
  all("[data-context-tab]").forEach((button) => button.addEventListener("click", () => selectContextTab(button.dataset.contextTab)));
  $("#student-form").addEventListener("submit", submit);
  $("#submit-task-feedback").addEventListener("click", () => submitTaskFeedback());
  $("#runtime-task-pause").addEventListener("click", () => submitRuntimeTaskControl("pause"));
  $("#runtime-task-resume").addEventListener("click", () => submitRuntimeTaskControl("resume"));
  $("#runtime-task-approve").addEventListener("click", () => submitRuntimeTaskControl("approve", {
    decision: "approved",
    expected_state_version: runtimeTaskControls?.state_version,
  }));
  $("#runtime-task-reject-proposal").addEventListener("click", () => submitRuntimeTaskControl("reject", {
    reason: "The proposed Runtime recovery plan was rejected from the workspace.",
  }));
  $("#runtime-task-input-form").addEventListener("submit", submitRuntimeTaskInput);
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
  $("#stop-button").addEventListener("click", () => {
    const taskId = state.taskId;
    if (!taskId) return;
    state.cancelRequested = true;
    const stopSequence = state.runSequence + 1;
    state.runSequence = stopSequence;
    state.activeTaskWait?.cancel();
    state.activeTaskWait = null;
    state.taskId = "";
    setBusy(false);
    markAnswerCancelled();
    $("#form-error").textContent = "已立即停止当前等待，正在后台提交取消请求…";
    void api(`/api/v1/tasks/${taskId}/cancel`, { method: "POST" })
      .then(() => { if (state.runSequence === stopSequence) $("#form-error").textContent = "停止请求已提交，任务不会继续刷新结果。"; })
      .catch((error) => { if (state.runSequence === stopSequence) $("#form-error").textContent = `停止请求未确认：${error.message}`; });
  });
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
