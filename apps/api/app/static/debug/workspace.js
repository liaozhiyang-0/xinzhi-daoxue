import { createMaterialManager } from "./ts/materials.js";
import { createTaskTransport } from "./ts/task-transport.js";
import { buildStudentTaskPayload } from "./ts/workspace-contracts.js?v=20260826-circuit-toggle-v2";

const { $, all, api, el, initIdentityGate, initShell, renderMarkdown, toast } = XinzhiUI;
const params = new URLSearchParams(location.search);
const scenarioId = params.get("scenario_id") || "";
const courseLabels = {
  AUTO: "自动识别",
  UNKNOWN: "待定课程",
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
  tavily: "Tavily",
  brave: "Brave",
  serpapi: "SerpApi",
  searxng: "SearXNG",
  aliyun_iqs: "阿里云 IQS",
  bocha: "Bocha",
  news_rss: "Google News RSS",
};
const externalProviderStatusLabels = {
  completed: "已返回",
  partial: "部分返回",
  failed: "失败",
  rate_limited: "被限流",
  timeout: "超时",
  request_failed: "连接失败",
  invalid_json: "返回格式错误",
  invalid_xml: "返回格式错误",
};
const primaryAcademicProviders = new Set(["openalex", "crossref", "arxiv"]);
const taskLabels = {
  explain_concept: "知识理解与关联",
  general_qa: "综合知识支持",
  solve_problem: "学科分析与验证",
  lesson_prep: "教学设计与课程组织",
  assignment_review: "学习证据与作业诊断",
  academic_search: "科研证据与前沿检索",
  academic_writing: "学术写作与引用校验",
  data_analysis: "研究设计与数据分析",
};
const intentLabels = {
  unknown: "自动识别",
  explain_concept: "概念理解",
  general_qa: "综合知识支持",
  solve_problem: "问题分析与验证",
  lesson_prep: "教学设计",
  assignment_review: "学习证据诊断",
  academic_search: "科研前沿检索",
  academic_writing: "学术写作",
  data_analysis: "数据分析",
};
const ragLabels = { grounded_generation: "课程资料支撑", method_reference: "方法参考", reference_only: "资料参考", user_sources_only: "用户材料", data_context_only: "数据上下文", no_rag: "无需课程检索" };
const maxMultiImageFiles = 8;
const researchTabularExtensions = new Set(["csv", "tsv", "json", "xlsx", "parquet"]);
const panelWidthStorage = {
  left: "xinzhi_workspace_left_width",
  right: "xinzhi_workspace_right_width",
};
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
  submitInFlight: false,
  activeCourse: "AUTO",
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
  activeScenarioId: scenarioId,
  activeScenarioPrompt: "",
  userRole: "student",
};
const materialManager = createMaterialManager({
  api,
  maxFiles: maxMultiImageFiles,
  onChanged: (files) => showMaterialPreview(files),
});
let materialPreviewUrls = [];
let circuitArtifactZoom = 1;
let identityReady = Promise.resolve();
localStorage.setItem("xinzhi_student_user", state.userId);

function effectiveWorkspaceRole(identity) {
  const role = String(identity?.role || "").trim().toLowerCase();
  return role === "admin" ? "admin" : "student";
}

function selectedCourse() {
  return "AUTO";
}

function inferLearningMode(question = "", studentAttempt = "") {
  const normalized = String(question || "").toLowerCase();
  if (String(studentAttempt || "").trim()) return "check_my_work";
  // Planning, diagnosis, and governance prompts need their complete result.
  // Do not infer an interactive hint loop from generic words such as
  // “练习” or “学习路径”; only an explicit student attempt opts into review.
  if (normalized.trim()) return "direct_answer";
  return "direct_answer";
}

const showcaseScenarioByCapability = {
  lesson_prep: "faculty_course_copilot_v1",
  assignment_review: "assessment_diagnosis_v1",
  student_learning_path: "student_learning_path_v1",
  academic_search: "research_frontier_radar_v1",
  knowledge_governance: "department_knowledge_governance_v1",
};

function inferCoursePreview(question = "", hasMaterials = false) {
  const normalized = String(question || "").toLowerCase();
  if (!normalized.trim() && !hasMaterials) return "等待提问";
  if (/科研|论文|doi|arxiv|前沿|学术|research|paper/i.test(normalized)) return "科研任务";
  if (/模拟电子|运算放大器|晶体管|负反馈|滤波器/i.test(normalized)) return courseLabels.AE;
  if (/数字电子|逻辑门|触发器|锁存器|时序/i.test(normalized)) return courseLabels.DE;
  if (/信号与系统|傅里叶|采样|连续时间/i.test(normalized)) return courseLabels.SS;
  if (/通信|调制|信道|讯号/i.test(normalized)) return courseLabels.COMM;
  if (/电路|电阻|电容|电感|节点电压|kcl|kvl|电流/i.test(normalized)) return courseLabels.CT;
  return hasMaterials ? "根据附件识别" : "等待系统识别";
}

function updateAutoDetection(
  question = $("#question-input")?.value || "",
  studentAttempt = $("#student-attempt-input")?.value || "",
) {
  const mode = inferLearningMode(question, studentAttempt);
  const modeLabels = {
    direct_answer: "综合回答",
    guided_learning: "引导学习",
    check_my_work: "检查与诊断",
  };
  const descriptions = {
    direct_answer: "系统会组织知识、证据和可执行建议。",
    guided_learning: "系统会分阶段给出提示、检查点和下一步行动。",
    check_my_work: "系统会优先核对已有步骤，并标出需要人工复核的部分。",
  };
  const hiddenMode = $("#teaching-mode");
  if (hiddenMode) hiddenMode.value = mode;
  const attemptPanel = $("#student-attempt-panel");
  if (attemptPanel) attemptPanel.hidden = mode !== "check_my_work";
  const modeNode = $("#detected-learning-mode");
  if (modeNode) modeNode.textContent = `学习方式：${modeLabels[mode] || "综合回答"}`;
  const courseNode = $("#detected-course");
  if (courseNode) courseNode.textContent = `课程：${inferCoursePreview(question, selectedMaterialFiles().length > 0)}`;
  const boundary = $("#teaching-mode-boundary");
  if (boundary) boundary.textContent = descriptions[mode] || descriptions.direct_answer;
  return mode;
}

function researchAnalysisQuestionDetected(text = "") {
  const normalized = String(text || "").toLowerCase();
  return /数据分析|研究设计|数据质量|效应量|置信区间|不确定性|诊断结果|结论边界|双臂实验|处理组|对照组|treatment|control|effect size|confidence interval/.test(normalized);
}

function researchAnalysisV2Enabled(text = "") {
  const question = text || $("#question-input")?.value || "";
  return params.get("analysis_v2") === "1"
    || state.activeScenarioId === "research_data_workbench_v1"
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
  return updateAutoDetection();
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
    body: JSON.stringify({ user_id: state.userId, course_id: "UNKNOWN", title: "" }),
  });
  state.sessionId = session.id;
  localStorage.setItem("xinzhi_student_session", session.id);
  await loadSessionList();
  return session.id;
}

function resetConversation() {
  state.historyRequestSequence += 1;
  state.runSequence += 1;
  // Follow-up context belongs to the previous task.  Keeping it across a
  // fresh session can silently inject the previous intent into the next
  // POST, so a new question is routed as its own request.
  pendingLearningFollowUp = null;
  // A capability card sets an intent override for the current draft only.
  // Clear it when starting a fresh session so the next prompt is routed by
  // its own capability selection instead of inheriting the previous route.
  state.intentOverride = "";
  state.activeTaskWait?.cancel();
  state.activeTaskWait = null;
  state.taskId = "";
  state.submitInFlight = false;
  state.cancelRequested = false;
  setBusy(false);
  // A fresh/switched session must not inherit unsent materials from the
  // previous draft. Otherwise the next task can upload stale files again
  // (and a repeated example click can submit duplicates).
  clearImage();
  conversationMaterialUrls.forEach((url) => URL.revokeObjectURL(url));
  conversationMaterialUrls = [];
  state.currentTask = null; state.archivedTaskIds.clear(); state.liveProcessSteps.clear();
  runtimeLearningRunId = "";
  runtimeLearningTaskId = "";
  runtimeTaskControls = null;
  state.lastQuestion = ""; state.lastAnswer = "";
  state.activeCourse = "AUTO";
  state.activeScenarioId = scenarioId;
  state.activeScenarioPrompt = "";
  localStorage.removeItem("xinzhi_student_course");
  const questionInput = $("#question-input");
  if (questionInput) questionInput.value = "";
  const courseSelect = $("#course-select");
  if (courseSelect) courseSelect.value = "AUTO";
  const teachingMode = $("#teaching-mode");
  if (teachingMode) teachingMode.value = "direct_answer";
  const studentAttemptInput = $("#student-attempt-input");
  if (studentAttemptInput) studentAttemptInput.value = "";
  $("#messages").replaceChildren(); $("#answer-panel").hidden = true; $("#welcome").hidden = false;
  $("#context-task-title").textContent = "等待提问";
  updateAutoDetection("");
  updateResearchAnalysisPanel();
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

function taskHasRenderableAnswer(task, result = resultForTask(task)) {
  const structured = result?.structured_result || {};
  const mathContent = result?.math_content || structured.math_content;
  return Boolean(String(mathContent?.markdown || result?.answer || "").trim());
}

function presentationFor(task, result) {
  const structured = result.structured_result || {};
  const summary = structured.execution_summary || {};
  const raw = structured.presentation || legacyPresentation(task, result);
  const fallback = Boolean(summary.fallback || result.fallback_used);
  if (task?.status === "cancelled") {
    return {
      ...raw,
      status_label: "已停止",
      requires_review: false,
      generation_complete: false,
      answer_quality_status: "cancelled",
      answer_quality_message: "本次任务已停止，未生成新回答。",
      evidence_message: "本次任务已停止，未生成新的资料依据。",
    };
  }
  if (task?.status === "failed") {
    return {
      ...raw,
      status_label: raw.status_label === "已完成" ? "执行失败" : raw.status_label || "执行失败",
      requires_review: true,
      generation_complete: false,
      answer_quality_status: "failed",
      answer_quality_message: task.error_message || "任务未完成，请根据提示处理后重试。",
      evidence_message: "本次没有可确认的完整结果；已有资料不会被当作成功答案。",
    };
  }
  if (!fallback && task?.status === "completed" && !taskHasRenderableAnswer(task, result)) {
    return {
      ...raw,
      status_label: "结果异常",
      requires_review: true,
      answer_quality_message: "任务已记录为完成，但没有返回可展示的回答；请重新提问或联系管理员复核。",
    };
  }
  if (!fallback) return raw;
  const reason = summary.fallback_reason || result.fallback_reason || "";
  const count = Number(summary.evidence_count || 0);
  const messages = {
    route_unavailable: "这是通用模型回答；目标 Agent 不可用，专业 Agent 未完成本次任务。",
    target_agent_unavailable: "这是通用模型回答；目标 Agent 不可用，专业 Agent 未完成本次任务。",
    runtime_execution_failed: "这是通用模型回答；Runtime 执行失败，专业 Agent 未完成本次任务。",
    provider_opt_out: "已按本地 Runtime 策略处理。",
    provider_response_parse_error: "本地 Runtime 结果格式校验未通过，本次已保留安全后备结果。",
    provider_timeout: "云端响应超时，本次已切换到本地安全后备结果。",
    provider_timeout: "本地 Runtime 响应超时，本次已保留安全后备结果。",
    not_configured: "该云端能力尚未配置，本次已切换到本地安全后备结果。",
    academic_generation_direct_model: "专业求解链路未形成完整回答，已由通用模型直接完成本次回答。",
  };
  return {
    ...raw,
    provider_label: "本地安全后备",
    fallback_message: messages[reason] || "云端主能力本次未完成，已切换到本地安全后备结果。",
    source_summary: count ? `已检索 ${count} 条课程资料` : raw.source_summary,
    evidence_message: count
      ? (raw.evidence_message || "课程资料检索已完成；当前回答由本地后备模型生成，请打开证据原文复核")
      : raw.evidence_message,
  };
}

function displayAnswer(task, result) {
  const structured = result.structured_result || {};
  const mathContent = result.math_content || structured.math_content;
  if (
    task?.intent === "data_analysis"
    && task?.status === "failed"
    && !task?.result_content
  ) {
    return [
      "## 数据分析尚未执行",
      "",
      "本次仅完成入口预检，未读取或计算原始数据。请先补充研究设计、数据清单和授权信息，再进入质量门禁。",
    ].join("\n");
  }
  const answer = mathContent?.markdown || result.answer || task.error_message || "";
  if (!answer.trim() && task?.status === "cancelled") {
    return [
      "## 任务已停止",
      "",
      "本次任务已停止，未生成新回答；不会把空结果当作有效答案。",
    ].join("\n");
  }
  if (!answer.trim() && task?.status === "completed") {
    return [
      "## 结果需要复核",
      "",
      "任务已记录为完成，但没有返回可展示的回答。请重新提问；系统不会把空结果当作有效答案。",
    ].join("\n");
  }
  const safeAnswer = answer || "未返回回答";
  if (safeAnswer === "云端工作流暂不可用，已返回本地结构化模板。") {
    return [
      "## 历史任务说明",
      "",
      "> 该任务执行于本次修复之前，旧版本只保存了降级占位文本，并未生成实际教案。",
      "",
      "请点击“重新提问”使用新版的本地可编辑教案框架；已检索资料仍可在右侧查看。",
    ].join("\n");
  }
  return safeAnswer;
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

function cleanEvidenceExcerpt(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const cleanRawLatexFragments = (line) => {
    if (!/[\\{}]/u.test(line)) return line;
    return line
      .replace(/\\(?:mathrm|text|operatorname)\s*\{([^{}]*)\}/gu, "$1")
      .replace(/\\(?:mathbf|mathit|mathbb|boldsymbol)\s*\{([^{}]*)\}/gu, "$1")
      .replace(/\\(?:mathbf|mathit|mathbb|boldsymbol)([A-Za-z]+)/gu, "$1")
      .replace(/\\(?:times|cdot)/gu, " × ")
      .replace(/\\(?:frac|dfrac)\s*\{([^{}]*)\}\s*\{([^{}]*)\}/gu, "$1/$2")
      .replace(/\\(?:;|,|!|:)/gu, " ")
      .replace(/(?:^|\s)(?:t?hrm|mathrm|text|operatorname)\s*\{([^{}]*)\}/gu, " $1")
      .replace(/\{([A-Za-z](?:\s*[A-Za-z0-9]){0,3})\}/gu, "$1")
      .replace(/\{(-?(?:\d+(?:\.\d+)?|\.\d+))\}/gu, "$1")
      .replace(/[{}]/gu, "")
      .replace(/\s{2,}/gu, " ");
  };
  const cleanInlineFormulaArtifacts = (line) => {
    let cleaned = line.replace(/^\s*(?:(?:\\\]|\\\))\s*)+/u, "");
    cleaned = cleaned
      .replace(/\\(?:\]|\))/gu, "")
      .replace(/\\(?:\(|\[)/gu, "")
      .replace(/\\(?:left|right|begin|end)\b(?:\{[^}]*\})?/gu, "");
    return cleaned;
  };
  const cleanMarkdownImageLinks = (text) => text.replace(
    /!\[([^\]]*)\]\((?:<[^>]+>|[^)\s]+)(?:\s+"[^"]*")?\)/gu,
    (_match, alt) => String(alt || "").trim(),
  );
  const isOrphanFormulaLine = (line) => {
    const text = line.trim();
    if (!text) return true;
    if (/^(?:-{2,3}|[}\]]|\\(?:\]|\)|right|end\{[^}]+\}))+$/u.test(text)) return true;
    if (/[\u4e00-\u9fff]/u.test(text)) return false;
    return text.split("}").length - 1 > text.split("{").length - 1
      || text.split("]").length - 1 > text.split("[").length - 1
      || (text.includes("\\right") && !text.includes("\\left"))
      || (text.includes("\\]") && !text.includes("\\["));
  };
  const lines = cleanMarkdownImageLinks(raw).split(/\r?\n/u);
  while (lines.length && isOrphanFormulaLine(lines[0])) lines.shift();
  const cleaned = lines
    .filter((line) => !["--", "---", "\\]", "\\)"].includes(line.trim()))
    .map((line) => cleanRawLatexFragments(cleanInlineFormulaArtifacts(line)))
    .join("\n")
    .trim();
  return cleaned || raw;
}

function cleanEvidenceCaption(value) {
  return String(value || "")
    .replace(/\\(?:\]|\))/gu, "")
    .replace(/-{3,}/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
}

function evidenceDisplayExcerpt(value) {
  // Source-anchor cleanup must not alter the user-facing evidence card.
  // Keep the retrieved fragment intact when formula parsing is unavailable.
  return String(value || "").trim();
}

function isOrphanFormulaLineForDocument(text) {
  if (/^(?:-{2,3}|[}\]]|\\(?:\]|\)|right|end\{[^}]+\}))+$/u.test(text)) return true;
  if (/[\u4e00-\u9fff]/u.test(text)) return false;
  return text.split("}").length - 1 > text.split("{").length - 1
    || text.split("]").length - 1 > text.split("[").length - 1
    || (text.includes("\\right") && !text.includes("\\left"))
    || (text.includes("\\]") && !text.includes("\\["));
}

function cleanKnowledgeDocumentContent(value) {
  const htmlParser = new DOMParser();
  const htmlImageMarkdown = (markup) => {
    const image = htmlParser.parseFromString(markup, "text/html").querySelector("img");
    if (!image) return "";
    const source = image.getAttribute("src") || "";
    const alt = image.getAttribute("alt") || image.getAttribute("title") || "课程资料图片";
    return source ? `![${alt}](${source})` : alt;
  };
  const htmlTableMarkdown = (markup) => {
    const table = htmlParser.parseFromString(markup, "text/html").querySelector("table");
    if (!table) return "";
    const rows = all("tr", table).map((row) => [...row.children]
      .filter((cell) => ["TH", "TD"].includes(cell.tagName))
      .map((cell) => cell.textContent.replace(/\s+/gu, " ").trim().replace(/\|/gu, "\\|"))
      .filter((cell) => cell.length));
    if (!rows.length) return "";
    const width = Math.max(...rows.map((row) => row.length));
    const padded = rows.map((row) => [...row, ...Array(Math.max(0, width - row.length)).fill("")]);
    const row = (cells) => `| ${cells.join(" | ")} |`;
    return [row(padded[0]), row(padded[0].map(() => "---")), ...padded.slice(1).map(row)].join("\n");
  };
  let normalized = String(value || "")
    .replace(/<img\b[^>]*>/giu, (markup) => htmlImageMarkdown(markup))
    .replace(/<table\b[\s\S]*?<\/table>/giu, (markup) => htmlTableMarkdown(markup))
    .replace(/<br\s*\/?>/giu, "\n")
    .replace(/<\/(?:p|div|section|article|li|ul|ol|h[1-6])\s*>/giu, "\n")
    .replace(/<[^>]+>/gu, "");
  normalized = htmlParser.parseFromString(normalized, "text/html").body.textContent || normalized;
  return normalized.split(/\r?\n/u).filter((line) => {
    const text = line.trim();
    return !text || !isOrphanFormulaLineForDocument(text);
  }).map((line) => {
    let cleaned = line.replace(/^\s*(?:(?:\\\]|\\\))\s*)+/u, "");
    return cleaned
      .replace(/\\(?:\]|\))/gu, "")
      .replace(/\\(?:\(|\[)/gu, "")
      .replace(/\\(?:left|right|begin|end)\b(?:\{[^}]*\})?/gu, "")
      .replace(/\\(?:mathrm|text|operatorname)\s*\{([^{}]*)\}/gu, "$1")
      .replace(/\\(?:mathbf|mathit|mathbb|boldsymbol)\s*\{([^{}]*)\}/gu, "$1")
      .replace(/\\(?:mathbf|mathit|mathbb|boldsymbol)([A-Za-z]+)/gu, "$1")
      .replace(/\\(?:times|cdot)/gu, " × ")
      .replace(/\\(?:frac|dfrac)\s*\{([^{}]*)\}\s*\{([^{}]*)\}/gu, "$1/$2")
      .replace(/\\(?:;|,|!|:)/gu, " ")
      .replace(/(?:^|\s)(?:t?hrm|mathrm|text|operatorname)\s*\{([^{}]*)\}/gu, " $1")
      .replace(/\{([A-Za-z](?:\s*[A-Za-z0-9]){0,3})\}/gu, "$1")
      .replace(/\{(-?(?:\d+(?:\.\d+)?|\.\d+))\}/gu, "$1")
      .replace(/[{}]/gu, "")
      .replace(/\s{2,}/gu, " ");
  }).join("\n");
}

function preserveKnowledgeDocumentContent(value) {
  const htmlParser = new DOMParser();
  const imageMarkdown = (markup) => {
    const image = htmlParser.parseFromString(markup, "text/html").querySelector("img");
    if (!image) return "";
    const source = image.getAttribute("src") || "";
    const alt = image.getAttribute("alt") || image.getAttribute("title") || "课程资料图片";
    return source ? `![${alt}](${source})` : alt;
  };
  let normalized = String(value || "")
    .replace(/<img\b[^>]*>/giu, (markup) => imageMarkdown(markup))
    .replace(/<br\s*\/?>/giu, "\n")
    .replace(/<\/(?:p|div|section|article|li|ul|ol|h[1-6])\s*>/giu, "\n")
    .replace(/<[^>]+>/gu, "");
  normalized = htmlParser.parseFromString(normalized, "text/html").body.textContent || normalized;
  return normalized;
}

async function loadEvidenceDocumentPage(item, offset = null) {
  const anchor = offset == null ? cleanEvidenceExcerpt(item.summary) : "";
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
        preserveKnowledgeDocumentContent(
        page.content || "这部分原文没有可显示的文本。",
        ),
        page,
      ),
      { preserveRaw: true },
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
    const fallbackCount = all(".math-latex-fallback", content).length;
    if (fallbackCount > 0) {
      note.textContent = `原文中有 ${fallbackCount} 个公式按原始文本保留，未丢失内容；可结合上下文核对原文。`;
      note.hidden = false;
    }
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
  const summary = evidenceDisplayExcerpt(item.summary);
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

function evidenceExternalUrl(item) {
  const direct = String(item?.url || item?.canonical_url || item?.source_ref || "").trim();
  if (/^https?:\/\//i.test(direct)) return direct;
  const doiValue = String(item?.doi || direct.match(/^(?:doi:)?(10\.\d{4,9}\/\S+)$/i)?.[1] || "")
    .replace(/^https?:\/\/doi\.org\//i, "")
    .replace(/^doi:/i, "");
  if (doiValue) return `https://doi.org/${encodeURIComponent(doiValue)}`;
  const arxivValue = String(item?.arxiv_id || direct.match(/^arxiv:(.+)$/i)?.[1] || "")
    .replace(/^https?:\/\/arxiv\.org\/(?:abs|pdf)\//i, "")
    .replace(/^arxiv:/i, "")
    .replace(/\.pdf$/i, "");
  if (arxivValue) return `https://arxiv.org/abs/${encodeURIComponent(arxivValue)}`;
  return "";
}

function evidenceCard(item) {
  const role = item.role === "method_reference" ? "方法参考" : item.used_by_answer ? "已引用" : item.entered_workflow ? "进入上下文" : "补充阅读";
  const card = el("article", { class: "evidence-card", "data-evidence-id": item.evidence_id, role: "button", tabindex: "0", "aria-label": `打开资料：${item.title || item.chapter || "课程资料"}` });
  const summary = el("div", { class: "evidence-summary" });
  renderMarkdown(summary, evidenceDisplayExcerpt(item.summary) || "本条资料没有可展示摘要。");
  const isLocalKnowledge = String(item.source_ref || "").startsWith("kb://");
  const externalUrl = isLocalKnowledge ? "" : evidenceExternalUrl(item);
  const sourceLabel = isLocalKnowledge
    ? "本地只读资料"
    : externalUrl
      ? "外部来源 · 请打开原文核验"
      : "来源路径不可用";
  const sourceAction = isLocalKnowledge
    ? el("button", { type: "button", class: "evidence-open", text: "打开资料" })
    : externalUrl
      ? el("a", { class: "evidence-open external-paper-open", href: externalUrl, target: "_blank", rel: "noopener noreferrer", text: "打开原文" })
      : el("small", { text: "无法打开原文" });
  const actions = el("div", { class: "evidence-card-actions" }, [
    el("small", { text: sourceLabel }),
    sourceAction,
  ]);
  card.append(
    el("div", { class: "evidence-card-header" }, [el("span", { class: "evidence-id", text: item.evidence_id }), el("span", { class: "evidence-role", text: role })]),
    (() => { const heading = el("h3"); renderMarkdown(heading, item.title || item.chapter || "课程资料"); return heading; })(),
    el("small", { text: [courseLabels[item.course_id] || item.course_name, item.chapter, item.content_type].filter(Boolean).join(" · ") }),
    summary,
  );
  const images = (item.related_images || []).map((image) => ({ image: { ...image, caption: cleanEvidenceCaption(image.caption) }, src: imageUrl(image.resource_uri) })).filter((entry) => entry.src);
  if (images.length) {
    const row = el("div", { class: "evidence-images" });
    images.forEach(({ image, src }) => row.append(el("button", { type: "button", onclick: (event) => { event.stopPropagation(); openImage(src, image.caption || item.title); } }, el("img", { src, loading: "lazy", alt: image.caption || item.title }))));
    card.append(row);
  }
  card.append(actions);
  const open = () => { focusEvidence(item.evidence_id); void openEvidenceDocument(item); };
  if (isLocalKnowledge) {
    actions.lastElementChild.addEventListener("click", (event) => { event.stopPropagation(); open(); });
  }
  card.addEventListener("click", (event) => {
    if (!event.target.closest(".evidence-images") && !event.target.closest("a") && isLocalKnowledge) open();
  });
  card.addEventListener("keydown", (event) => {
    if (event.target !== card) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (isLocalKnowledge) open();
      else if (externalUrl) window.open(externalUrl, "_blank", "noopener,noreferrer");
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
      .map((item) => [item.resource_uri, { ...item, caption: cleanEvidenceCaption(item.caption) }]),
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

function decodeHtmlEntities(value) {
  let decoded = String(value || "");
  for (let pass = 0; pass < 2; pass += 1) {
    const probe = new DOMParser().parseFromString(decoded, "text/html").body.textContent || "";
    if (probe === decoded) break;
    decoded = probe;
  }
  return decoded;
}

function externalEvidenceUrl(item) {
  const direct = String(item.url || item.canonical_url || item.source_ref || "").trim();
  if (/^https?:\/\//i.test(direct)) return direct;
  const doi = String(item.doi || "").trim().replace(/^https?:\/\/doi\.org\//i, "");
  if (doi) return `https://doi.org/${encodeURIComponent(doi)}`;
  const arxiv = String(item.arxiv_id || "").trim().replace(/^arxiv:/i, "");
  if (arxiv) return `https://arxiv.org/abs/${encodeURIComponent(arxiv)}`;
  return "";
}

function externalEvidenceIdentityKeys(item) {
  const keys = [];
  const evidenceId = String(item.evidence_id || "").trim().toLowerCase();
  if (evidenceId) keys.push(`evidence:${evidenceId}`);
  const doi = String(item.doi || "")
    .trim()
    .replace(/^https?:\/\/doi\.org\//i, "")
    .replace(/^doi:/i, "")
    .toLowerCase();
  if (doi) keys.push(`doi:${doi}`);
  const arxiv = String(item.arxiv_id || "")
    .trim()
    .replace(/^https?:\/\/arxiv\.org\/(?:abs|pdf)\//i, "")
    .replace(/^arxiv:/i, "")
    .replace(/\.pdf$/i, "")
    .toLowerCase();
  if (arxiv) keys.push(`arxiv:${arxiv}`);
  const url = String(externalEvidenceUrl(item) || "")
    .trim()
    .toLowerCase()
    .replace(/#.*$/, "")
    .replace(/\/$/, "");
  if (url) keys.push(`url:${url}`);
  const sourceRef = String(item.source_ref || item.source_uri || "")
    .trim()
    .toLowerCase();
  if (sourceRef && !url && !doi && !arxiv) keys.push(`source:${sourceRef}`);
  if (!keys.length) {
    const title = String(item.title || "").trim().toLowerCase().replace(/\s+/g, " ");
    if (title) keys.push(`title:${title}`);
  }
  return keys;
}

function normalizedExternalItems(items) {
  const seen = new Set();
  return (Array.isArray(items) ? items : []).filter((item) => item && typeof item === "object").map((item) => {
    const url = externalEvidenceUrl(item);
    const abstract = item.abstract || item.content_excerpt || item.excerpt || "";
    return { ...item, url, abstract };
  }).filter((item) => {
    const keys = externalEvidenceIdentityKeys(item);
    if (!keys.length || keys.some((key) => seen.has(key))) return false;
    keys.forEach((key) => seen.add(key));
    return true;
  });
}

function externalItemsForDisplay(structured) {
  const view = Array.isArray(structured?.external_search_view) ? structured.external_search_view : [];
  const retrieval = Array.isArray(structured?.external_retrieval?.items) ? structured.external_retrieval.items : [];
  // The canonical retrieval packet is the source of truth.  The compact view
  // is retained only for legacy tasks that predate external_retrieval.items;
  // mixing both projections can show stale titles or citations after refresh.
  return normalizedExternalItems(retrieval.length ? retrieval : view);
}

function externalProviderStatusSummary(retrieval) {
  const statuses = retrieval?.provider_status;
  if (!statuses || typeof statuses !== "object") return "未执行";
  const entries = Object.entries(statuses).filter(([name, status]) => name && status);
  if (!entries.length) return "未记录接口状态";
  return entries.map(([name, status]) => (
    (externalProviderLabels[name] || name) + " · "
    + (externalProviderStatusLabels[status] || status)
  )).join("；");
}

function externalWarningLabel(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (text.includes("rate_limited")) return "接口触发限流，已尝试其他检索源。";
  if (text.includes("timeout")) return "接口或论文审核服务超时。";
  if (text.includes("request_failed")) return "接口连接失败。";
  if (text.includes("no records returned")) return "该接口没有返回记录。";
  if (text.includes("missing publication date")) return "候选论文缺少发布日期，无法核验时间范围。";
  if (text.includes("outside relative date window")) return "候选论文超出请求的时间范围。";
  if (text.includes("missing abstract")) return "候选论文缺少摘要，无法完成证据审核。";
  if (text.includes("topic mismatch")) return "候选结果与问题主题不匹配，已被剔除。";
  if (text.includes("paper review unavailable")) return "论文相关性审核不可用，结果需要人工核验。";
  if (text.includes("paper review rejected all")) return "论文相关性审核淘汰了全部候选结果。";
  return text.slice(0, 180);
}

function externalRetrievalDiagnostic(retrieval) {
  if (!retrieval || typeof retrieval !== "object") return null;
  const status = String(retrieval.status || "");
  const items = Array.isArray(retrieval.items) ? retrieval.items : [];
  const statuses = retrieval.provider_status && typeof retrieval.provider_status === "object"
    ? Object.entries(retrieval.provider_status).filter(([name, value]) => name && value)
    : [];
  const fallbackEntries = statuses.filter(([name]) => !primaryAcademicProviders.has(String(name).toLowerCase()));
  const warnings = Array.isArray(retrieval.warnings)
    ? retrieval.warnings.map(externalWarningLabel).filter(Boolean).filter((value, index, values) => values.indexOf(value) === index).slice(0, 3)
    : [];
  const hasProblem = !items.length && ["failed", "disabled", "partial"].includes(status);
  if (!hasProblem && !fallbackEntries.length && !warnings.length) return null;
  let text = hasProblem
    ? status === "disabled"
      ? "外部检索未启用或没有可用的检索接口。"
      : status === "partial"
        ? "外部检索只完成了部分接口，当前证据可能不完整。"
        : "外部检索已执行，但审核后没有形成可展示的合格证据。"
    : "已启用备用检索：" + fallbackEntries.map(([name]) => externalProviderLabels[name] || name).join("、") + "。";
  if (statuses.length) text += " 接口状态：" + externalProviderStatusSummary(retrieval) + "。";
  if (warnings.length) text += " 处理说明：" + warnings.join("；");
  return { status: hasProblem ? "warning" : "", text };
}

function externalEvidenceDateLabel(item) {
  const explicit = String(item.date_label || "").trim();
  if (explicit) return explicit;
  const raw = String(item.updated_at || item.published_at || "").trim();
  if (!raw) return "";
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toISOString().slice(0, 10);
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
  const dateLabel = externalEvidenceDateLabel(item);
  const metadata = [
    dateLabel ? `发表/更新 ${dateLabel}` : "时间未知",
    externalProviderLabels[item.provider] || item.provider || "学术来源",
    item.venue,
    item.citation_count != null ? `被引 ${item.citation_count} 次` : "引用数据未提供",
  ].filter(Boolean).join(" · ");
  const authors = Array.isArray(item.authors) ? item.authors.filter(Boolean).join(", ") : "";
  const abstract = decodeHtmlEntities(item.abstract || item.content_excerpt || "暂无摘要，建议打开原文查看。");
  const providerName = String(item.provider || "").trim().toLowerCase();
  const isMockSource = item.metadata?.mock === true
    || providerName === "mock"
    || providerName === "development_mock";
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
    el("small", {
      class: isMockSource ? "external-paper-provenance mock" : "external-paper-provenance",
      text: isMockSource ? "开发态 Mock · 非真实来源" : "外部来源 · 请打开原文核验",
    }),
    authors ? el("p", { class: "external-paper-authors", text: authors }) : null,
    el("p", { class: "external-paper-abstract", text: abstract }),
    el("div", { class: "external-paper-footer" }, [
      el("span", { text: item.doi ? `DOI: ${item.doi}` : item.arxiv_id ? `arXiv: ${item.arxiv_id}` : "" }),
      actions,
    ]),
  ].filter(Boolean));
}

function renderExternalPapers(items) {
  const normalized = normalizedExternalItems(items);
  if (!normalized.length) return null;
  return el("section", { class: "external-results" }, [
    el("div", { class: "external-results-heading" }, [
      el("strong", { text: `外部科研证据 ${normalized.length} 条 · 已通过相关性审核` }),
      el("span", { text: "论文、报道和会议线索均需打开原文核验" }),
    ]),
    ...normalized.map(externalPaperCard),
  ]);
}

function evidenceRelatedImages(evidence, candidates) {
  const attached = evidence.flatMap((item) => item.related_images || []);
  const attachedKeys = new Set(
    attached.map((item) => String(item.resource_uri || "").trim()).filter(Boolean),
  );
  if (!attachedKeys.size) return [];
  const merged = [...attached, ...candidates];
  return [...new Map(
    merged
      .filter((item) => attachedKeys.has(String(item.resource_uri || "").trim()))
      .map((item) => [item.resource_uri, { ...item, caption: cleanEvidenceCaption(item.caption) }]),
  ).values()];
}

function renderEvidence(items, presentation, relatedImages = [], externalItems = [], externalRetrieval = {}) {
  state.evidence = items || [];
  $("#source-summary").textContent = `参考课程资料 ${state.evidence.length}`;
  const cards = state.evidence.map(evidenceCard);
  const imageCard = relatedImageCard(relatedImages);
  if (imageCard) cards.push(imageCard);
  const external = renderExternalPapers(externalItems);
  const diagnostic = externalRetrievalDiagnostic(externalRetrieval);
  $("#context-evidence").replaceChildren(...(cards.length || external ? [...(external ? [external] : []), ...cards] : [el("div", { class: "context-empty" }, [el("strong", { text: "本次没有可展示的资料依据" }), el("p", { text: diagnostic?.text || presentation?.evidence_message || "系统不会把未使用的候选资料显示为回答依据。" })]) ]));
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
  const structured = result.structured_result || {};
  const externalEvidenceCount = externalItemsForDisplay(result.structured_result).length;
  const externalRetrieval = structured.external_retrieval && typeof structured.external_retrieval === "object"
    ? structured.external_retrieval
    : {};
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
  const collaboration = result.structured_result?.answer_mode === "generic_model"
    ? "通用模型回答"
    : result.provider === "local_agent" ? "内部 Agent 协作" : result.provider === "local" ? "本地知识增强" : result.provider === "mock" ? "开发演示" : "智能协作";
  const rows = [
    ["实际提问", taskQuestion(task).slice(0, 800)],
    ["完成能力", presentation.title || summary.agent_label || "智能任务"],
    ["协作方式", collaboration],
    ["自动识别课程", courseLabels[task.course_id] || task.course_id || "自动识别"],
    ["任务类型", intentLabels[task.intent] || "自动识别"],
    ["自动识别学习方式", intentLabels[structured.teaching?.teaching_mode] || ({
      direct_answer: "综合回答",
      guided_learning: "引导学习",
      check_my_work: "检查与诊断",
    }[structured.teaching?.teaching_mode] || "综合回答")],
    ["知识增强", ragLabels[summary.rag_mode] || "按需启用"],
    [
      externalEvidenceCount ? "外部证据" : "资料使用",
      externalEvidenceCount
        ? `${externalEvidenceCount} 条`
        : `${summary.used_evidence_count || 0} / ${summary.evidence_count || 0} 条`,
    ],
    ["检索接口", externalRetrieval.status || externalRetrieval.provider_status ? externalProviderStatusSummary(externalRetrieval) : "未执行"],
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
  const knowledge = result.structured_result?.knowledge || {};
  if (result.structured_result?.answer_mode === "generic_model" || task?.agent_id === "GENERAL_MODEL_FALLBACK_V1") {
    return {
      title: "通用模型回答",
      status_label: "通用模型回答",
      source_summary: "未使用可核验资料依据",
      provider_label: "通用模型回答",
      fallback_message: "这是通用模型回答，不代表专业 Agent 已完成任务。",
      evidence_message: "资料不可用时未生成课程、科研引用或外部链接。",
      answer_quality_status: "generic_model",
      answer_quality_message: "请人工核对后再使用；本次回答不能替代专业 Agent 结果。",
      requires_review: true,
      generation_complete: true,
      execution_steps: [{ label: "通用模型兜底", status: "completed" }],
    };
  }
  if (
    task?.status === "failed"
    && (knowledge.evidence_status || result.evidence_status) === "insufficient"
  ) {
    return {
      title: `知识问答 · ${courseLabels[task.course_id] || task.course_id}`,
      status_label: "课程依据不足",
      source_summary: `课程资料 ${knowledge.hits?.length || knowledge.evidence_count || 0}`,
      provider_label: "本地知识库检索",
      fallback_message: "本次未形成可核验的正式结论。",
      evidence_message: "当前课程资料不足，系统已阻止不相关片段作为回答依据。请补充课程范围、关键词或资料后重试。",
      answer_quality_status: "needs_review",
      answer_quality_message: "任务未通过证据核验；下面内容仅用于说明缺口，不能视为已核对答案。",
      requires_review: true,
      generation_complete: false,
      execution_steps: [{ label: "课程证据核验", status: "failed" }],
    };
  }
  if (task?.intent === "data_analysis" && task?.status === "failed") {
    return {
      title: `${taskLabels.data_analysis} · ${courseLabels[task.course_id] || task.course_id}`,
      status_label: "未执行 · 数据边界",
      source_summary: "研究设计待完善",
      provider_label: "受控数据分析入口",
      fallback_message: "",
      evidence_message: "当前仅完成研究设计入口预检；没有授权数据时不会执行原始数据分析。",
      answer_quality_status: "needs_review",
      answer_quality_message: "任务未执行，不代表分析结论失败；请先完成研究设计和数据授权门禁。",
      requires_review: true,
      generation_complete: false,
      execution_steps: [{ label: "研究设计与数据授权门禁", status: "failed" }],
    };
  }
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

const messageStatusLabels = {
  created: "已创建",
  queued: "排队中",
  running: "运行中",
  waiting_user: "等待补充信息",
  waiting_review: "等待审核",
  completed: "已完成",
  failed: "执行失败",
  cancelled: "已取消",
};

function messageStatusText(status) {
  const key = String(status || "").toLowerCase();
  return messageStatusLabels[key] || status || "任务消息";
}

function runtimeApprovalAllowed() {
  const role = String(state.userRole || "").toLowerCase();
  if (["teacher", "admin"].includes(role)) return true;
  return role === "researcher" && [
    "RESEARCH_01_ACADEMIC_SEARCH_V1",
    "RESEARCH_02_ACADEMIC_WRITING_V1",
  ].includes(String(state.currentTask?.agent_id || ""));
}

function runtimeTaskControlAvailable(action) {
  if (action === "approve" || action === "reject") {
    if (!runtimeApprovalAllowed()) return false;
    return Boolean(
      runtimeTaskControls?.control_scope === "runtime_plan_proposal"
      && runtimeTaskControls?.plan_proposal?.proposal_id,
    ) || runtimeTaskControlEntry(action)?.available === true;
  }
  return runtimeTaskControlEntry(action)?.available === true;
}

function runtimeTaskControlMessage(projection) {
  if (
    String(projection?.status || "").toLowerCase() === "waiting_approval"
    && !runtimeApprovalAllowed()
  ) {
    return "An authorized reviewer must approve this checkpoint; the task will continue from its checkpoint after review.";
  }
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
      ? runtimeApprovalAllowed()
      : runtimeTaskControlAvailable(action);
    button.hidden = !available;
    button.disabled = runtimeTaskControlsBusy || !available;
    if (proposalPending && action === "approve") button.textContent = "应用恢复计划";
    button.title = available ? "" : `${entry?.reason_code || "runtime_control_unavailable"}: ${entry?.reason || "当前状态不可用"}`;
  });
  const reject = $("#runtime-task-reject-proposal");
  if (reject) {
    reject.hidden = !proposalPending || !runtimeApprovalAllowed();
    reject.disabled = runtimeTaskControlsBusy || !proposalPending || !runtimeApprovalAllowed();
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
              ...(action === "input" ? { data: payload?.data || {} } : {}),
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
    if (["resume", "approve", "input"].includes(action)) {
      observeResumedRuntimeTask(task?.id || taskId);
    }
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

function observeResumedRuntimeTask(taskId) {
  if (!taskId || state.activeTaskWait) return;
  const runSequence = state.runSequence;
  state.taskId = taskId;
  state.currentTask = { ...(state.currentTask || {}), id: taskId };
  setBusy(true);
  void waitForTask(taskId, runSequence).then(async (finishedTask) => {
    if (!finishedTask || runSequence !== state.runSequence) return;
    renderResult(finishedTask);
    await loadSessionList();
  }).catch((error) => {
    if (runSequence === state.runSequence) {
      $("#form-error").textContent = error.message || "任务恢复监听失败";
    }
  }).finally(() => {
    if (runSequence === state.runSequence) {
      state.taskId = "";
      setBusy(false);
    }
  });
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

function renderRetryAction(task) {
  const button = $("#retry-task");
  if (!button) return;
  const available = task?.status === "failed" && task.retryable === true;
  button.hidden = !available;
  button.disabled = false;
  if (available) {
    button.textContent = `重试本次任务（${task.attempt}/${task.max_attempts}）`;
    button.title = task.failure_category || "该失败可以安全重试";
  }
}

async function retryCurrentTask() {
  const original = state.currentTask;
  if (!original?.id || original.status !== "failed" || original.retryable !== true) return;
  const runSequence = state.runSequence + 1;
  state.runSequence = runSequence;
  state.cancelRequested = false;
  state.taskId = original.id;
  setBusy(true);
  markAnswerPending();
  $("#form-error").textContent = "";
  try {
    const task = await api(`/api/v1/tasks/${original.id}/retry`, { method: "POST" });
    state.taskId = task.id;
    state.currentTask = task;
    const finishedTask = await waitForTask(task.id, runSequence);
    if (finishedTask && runSequence === state.runSequence) {
      renderResult(finishedTask);
      await loadSessionList();
    }
  } catch (error) {
    if (runSequence === state.runSequence) {
      $("#form-error").textContent = `${error.message || "重试未完成"}。请稍后再试。`;
      renderResult({ ...original, error_message: error.message || original.error_message });
    }
  } finally {
    if (runSequence === state.runSequence) {
      state.taskId = "";
      setBusy(false);
    }
  }
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

function rememberRuntimeRun(taskId, result = {}) {
  const runId = String(result.runtime_run_id || "").trim();
  if (!runId) return;
  runtimeLearningRunId = runId;
  runtimeLearningTaskId = taskId;
}

function renderResult(task) {
  const renderStarted = performance.now();
  const result = task.result_content || {}; const structured = result.structured_result || {};
  const circuitImageOnly = circuitArtifactIsImageOnly(structured);
  const presentation = presentationFor(task, result);
  const summary = structured.execution_summary || {};
  const evidence = structured.evidence_view || [];
  const externalItems = externalItemsForDisplay(structured);
  state.lastAnswer = circuitImageOnly ? "" : displayAnswer(task, result);
  state.currentTask = task;
  updateAutoDetection(taskQuestion(task), structured.teaching?.student_attempt_present ? "provided" : "");
  renderRetryAction(task);
  prepareTaskFeedback(task);
  rememberRuntimeRun(task.id, result);
  void refreshRuntimeTaskControls(task.id);
  const answerPanel = $("#answer-panel");
  answerPanel.hidden = false;
  answerPanel.classList.toggle("circuit-render-only", circuitImageOnly);
  $("#answer-status").textContent = presentation.status_label || "已完成";
  $("#answer-title").textContent = presentation.title;
  $("#answer-source-chip").textContent = presentation.source_summary;
  $("#context-task-title").textContent = presentation.title;
  renderMarkdown($("#answer-text"), state.lastAnswer);
  // The legacy hint/progress panels are intentionally not part of the
  // workspace result surface. They previously replaced complete workflow
  // answers with a generic H0 prompt and fetched unrelated learning state.
  renderBusinessView(structured.business_view || researchBriefView(structured.research_brief), state.lastAnswer, structured);
  renderCircuitArtifact(structured);
  const notices = [];
  if (summary.mock || result.provider === "mock" || result.mock_used) notices.push({ status: "mock", text: "当前为开发态模拟结果，不代表正式智能能力输出。" });
  if (presentation.answer_quality_message) notices.push({
    status: presentation.requires_review ? "warning" : "",
    text: presentation.answer_quality_message,
  });
  if (presentation.fallback_message) notices.push({ status: "warning", text: presentation.fallback_message });
  const externalDiagnostic = externalRetrievalDiagnostic(structured.external_retrieval);
  if (externalDiagnostic) notices.push(externalDiagnostic);
  else if (presentation.evidence_message) notices.push({ status: "", text: presentation.evidence_message });
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
  const relatedImageCandidates = [
    ...(structured.related_images || []),
    ...(result.related_images || []),
    ...(structured.knowledge?.images || []),
  ];
  const relatedImages = evidenceRelatedImages(evidence, relatedImageCandidates);
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
  renderEvidence(evidence, presentation, relatedImages, externalItems, structured.external_retrieval); renderProcess(finalSteps);
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

async function loadSessionHistory() {
  if (!state.sessionId) return;
  const sessionId = state.sessionId;
  const requestSequence = ++state.historyRequestSequence;
  const isCurrent = () => requestSequence === state.historyRequestSequence && state.sessionId === sessionId;
  try {
    const messages = await api(`/api/v1/sessions/${sessionId}/messages?user_id=${encodeURIComponent(state.userId)}&limit=100`);
    if (!isCurrent()) return;
    if (!messages.length) return;

    // A completed task can be committed after the user message but before the
    // assistant message is visible to a refreshed browser.  The message list
    // is therefore not a sufficient recovery index.  Ask the session task
    // history for the newest task and hydrate it through the owned task API so
    // result presentation and evidence use the same full payload as live SSE.
    let latestSessionTask = null;
    try {
      const taskHistory = await api(`/api/v1/sessions/${sessionId}/tasks?limit=50`);
      const latestSummary = Array.isArray(taskHistory) ? taskHistory.at(-1) : null;
      if (latestSummary?.id) latestSessionTask = await api(ownedTaskUrl(latestSummary.id));
    } catch (_error) {
      latestSessionTask = null;
    }

    const latestAssistantTask = [...messages].reverse().find((item) => item.role === "assistant" && item.source_task_id);
    let restoredTask = null;
    if (latestSessionTask && ["completed", "failed", "cancelled"].includes(latestSessionTask.status)) {
      restoredTask = latestSessionTask;
    } else if (latestAssistantTask) {
      try {
        const candidate = await api(ownedTaskUrl(latestAssistantTask.source_task_id));
        if (
          isCurrent()
          && ["completed", "failed", "cancelled"].includes(candidate.status)
        ) restoredTask = candidate;
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
          el("span", { class: "message-meta", text: messageStatusText(message.status) }),
          el("div", { class: "markdown-view" }),
        ]);
        renderMarkdown(
          body.lastElementChild,
          message.content_text?.trim()
            ? message.content_text
            : "## 结果需要复核\n\n任务已记录，但没有返回可展示的回答；请重新提问。",
        );
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
    const latestTask = latestSessionTask || (
      latest.role === "user" && latest.source_task_id
        ? await api(ownedTaskUrl(latest.source_task_id))
        : null
    );
    if (latestTask) {
      if (!isCurrent()) return;
      const resumableStatuses = [
        "created",
        "queued",
        "running",
        "paused",
        "waiting_user",
        "waiting_review",
      ];
      if (resumableStatuses.includes(latestTask.status)) {
        state.taskId = latestTask.id;
        if (["paused", "waiting_user", "waiting_review"].includes(latestTask.status)) {
          renderRuntimeCheckpoint(latestTask);
        } else {
          setBusy(true);
          markAnswerPending();
          try {
            const finishedTask = await waitForTask(latestTask.id, requestSequence);
            if (finishedTask && isCurrent()) renderResult(finishedTask);
          } finally {
            if (isCurrent()) { state.taskId = ""; setBusy(false); }
          }
        }
      }
    }
    if (restoredTask && isCurrent()) {
      renderResult(restoredTask);
      setBusy(false);
      state.taskId = "";
    }
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

function businessDuplicateVariants(value) {
  const text = String(value == null ? "" : value).toLowerCase().trim();
  if (!text) return [];
  const plain = text
    .replace(/\\(?:cdot|times|ast)\b/g, "*")
    .replace(/\\(?:text|mathrm|operatorname)\s*\{([^{}]*)\}/g, "$1")
    .replace(/\\[a-z]+/g, "")
    .replace(/[\\$`*_{}#[\]<>]/g, "")
    .replace(/\s+/g, "")
    .replace(/[×⋅·]/g, "*");
  const compactMath = plain.replace(/([a-z0-9])\*([a-z0-9])/g, "$1$2");
  return [...new Set([plain, compactMath].filter((item) => item.length >= 4))];
}

function businessSectionAlreadyInAnswer(answer, section) {
  const answerVariants = businessDuplicateVariants(answer);
  const values = businessContentValues(section.content)
    .map(businessDuplicateVariants)
    .filter((variants) => variants.length > 0);
  return values.length > 0 && values.every((variants) =>
    variants.some((value) => answerVariants.some((candidate) => candidate.includes(value)))
  );
}

const academicSolverDuplicateSections = new Set([
  "problem_summary",
  "key_equations",
  "steps",
  "final_answer",
  "assumptions",
]);

function academicSolverHasCanonicalAnswer(answer) {
  const text = String(answer || "").trim();
  if (text.length < 120) return false;
  const headings = text.match(/^#{2,4}\s+.+$/gm) || [];
  return headings.length >= 2 || /(?:最终答案|结论汇总|关键推导|求解步骤)/.test(text);
}

function businessSectionIsCoveredByAnswer(view, answer, section) {
  if (businessSectionAlreadyInAnswer(answer, section)) return true;
  return view.renderer_type === "academic_solver"
    && academicSolverHasCanonicalAnswer(answer)
    && academicSolverDuplicateSections.has(section.key);
}

function businessValueText(key, value) {
  const booleanLabels = {
    review_required: { true: "需要人工复核", false: "无需人工复核" },
    manual_review_required: { true: "需要人工复核", false: "无需人工复核" },
    human_review_required: { true: "需要人工复核", false: "无需人工复核" },
  };
  if (typeof value === "boolean" && booleanLabels[key]) {
    return booleanLabels[key][String(value)];
  }
  if (value && typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value ?? "");
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
      .map(([key, value]) => `- ${key}: ${businessValueText(key, value)}`)
      .join("\n");
  }
  return businessValueText(section.key, section.content);
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
    return !businessSectionIsCoveredByAnswer(view, answer, section);
  });
  sections.forEach((section) => {
    const card = el("section", { class: `business-section business-${section.key}` });
    card.append(el("h3", { text: section.label }));
    const content = businessSectionText(section);
    card.append(el("div", { class: "markdown-view" })); renderMarkdown(card.lastElementChild, content);
    root.append(card);
  });
}

function circuitArtifactStatusLabel(status) {
  return {
    rendered: "已生成",
    degraded: "降级生成",
    failed: "未生成",
  }[String(status)] || "待复核";
}

function circuitValidationLabel(validationState) {
  return {
    validated: "拓扑已校验",
    partially_validated: "部分校验",
    needs_review: "需要复核",
    invalid: "拓扑无效",
  }[String(validationState)] || "状态未知";
}

function safeCircuitSvg(svgText) {
  if (typeof svgText !== "string" || !svgText.trim()) return null;
  try {
    const documentNode = new DOMParser().parseFromString(svgText, "image/svg+xml");
    const root = documentNode.documentElement;
    if (!root || root.nodeName.toLowerCase() !== "svg") return null;
    root.querySelectorAll("script, foreignObject").forEach((node) => node.remove());
    root.querySelectorAll("*").forEach((node) => {
      [...node.attributes].forEach((attribute) => {
        const name = attribute.name.toLowerCase();
        const value = attribute.value.trim().toLowerCase();
        if (name.startsWith("on") || (name === "href" && value.startsWith("javascript:"))) {
          node.removeAttribute(attribute.name);
        }
      });
    });
    return document.importNode(root, true);
  } catch (_error) {
    return null;
  }
}

function applyCircuitArtifactZoom() {
  const content = $("#circuit-artifact-content");
  const svg = content?.querySelector("svg");
  const value = $("#circuit-zoom-value");
  if (!svg || !value) return;
  const percentage = Math.round(circuitArtifactZoom * 100);
  svg.style.width = `${percentage}%`;
  svg.style.maxWidth = "none";
  svg.style.maxHeight = circuitArtifactZoom > 1 ? "none" : "520px";
  value.textContent = `${percentage}%`;
}

function bindCircuitArtifactZoom() {
  const panel = $("#circuit-artifact-panel");
  if (!panel || panel.dataset.zoomBound === "true") return;
  panel.dataset.zoomBound = "true";
  $("#circuit-zoom-out")?.addEventListener("click", () => {
    circuitArtifactZoom = Math.max(0.6, circuitArtifactZoom - 0.2);
    applyCircuitArtifactZoom();
  });
  $("#circuit-zoom-reset")?.addEventListener("click", () => {
    circuitArtifactZoom = 1;
    applyCircuitArtifactZoom();
  });
  $("#circuit-zoom-in")?.addEventListener("click", () => {
    circuitArtifactZoom = Math.min(2.4, circuitArtifactZoom + 0.2);
    applyCircuitArtifactZoom();
  });
}

function circuitArtifactIsImageOnly(structured = {}) {
  const artifact = structured.circuit_artifact;
  return Boolean(
    artifact
      && typeof artifact === "object"
      && artifact.metadata?.presentation_mode === "image_only"
      && artifact.status !== "failed"
      && typeof artifact.svg === "string"
      && artifact.svg.trim(),
  );
}

function renderCircuitArtifact(structured = {}) {
  const panel = $("#circuit-artifact-panel");
  const content = $("#circuit-artifact-content");
  const warningList = $("#circuit-artifact-warnings");
  const artifact = structured.circuit_artifact;
  bindCircuitArtifactZoom();
  circuitArtifactZoom = 1;
  panel.hidden = !artifact || typeof artifact !== "object";
  panel.dataset.presentation = "standard";
  content.replaceChildren();
  warningList.replaceChildren();
  if (panel.hidden) return;

  const status = String(artifact.status || "failed");
  const validationState = String(artifact.validation_state || "invalid");
  $("#circuit-artifact-status").textContent = circuitArtifactStatusLabel(status);
  const validation = $("#circuit-artifact-validation");
  validation.textContent = circuitValidationLabel(validationState);
  validation.className = `status-badge ${validationState === "validated" ? "status-success" : "status-warning"}`;

  const svg = safeCircuitSvg(artifact.svg);
  if (svg && status !== "failed") {
    if (circuitArtifactIsImageOnly(structured)) panel.dataset.presentation = "image-only";
    content.append(svg);
    applyCircuitArtifactZoom();
  } else {
    content.append(el("p", {
      class: "notice warning",
      text: "电路图未生成；解题答案仍可继续查看。请根据下方提示人工复核拓扑或重新提交。",
    }));
  }
  const warnings = Array.isArray(artifact.warnings) ? artifact.warnings : [];
  warnings.slice(0, 16).forEach((warning) => {
    warningList.append(el("li", { text: String(warning) }));
  });
}

const selectedMaterialFiles = () => materialManager.selected();
const appendMaterialFiles = (files) => materialManager.append(files);
const attachExampleImage = (button) => materialManager.attachExample(button);
const uploadMaterials = () => materialManager.upload();

const taskTransport = createTaskTransport({
  api,
  ownedTaskUrl,
  state,
  addMessage,
  selectContextTab,
  liveProgressData,
  updateLiveProgress,
  refreshRuntimeTaskControls,
  renderLongWaitNotice,
});
const waitForTask = (id, runSequence) => taskTransport.waitForTask(id, runSequence);

function setBusy(busy) {
  $("#send-button").disabled = busy; $("#stop-button").disabled = !busy; $("#question-input").disabled = busy; $("#student-attempt-input").disabled = busy; $("#teaching-mode").disabled = busy; $("#image-input").disabled = busy; $("#remove-image").disabled = busy; $("#circuit-visualization-toggle").disabled = busy;
  $("#retry-task").disabled = busy;
}

function markAnswerPending() {
  state.lastAnswer = "";
  $("#answer-panel").classList.remove("circuit-render-only");
  renderCircuitArtifact({});
  renderMarkdown($("#answer-text"), "");
  $("#answer-notices").replaceChildren();
  renderBusinessView({}, "", {});
  renderEvidence([], {});
  $("#context-task-title").textContent = "正在处理当前任务";
  $("#answer-panel").hidden = false;
  $("#answer-status").textContent = "\u6b63\u5728\u6267\u884c";
  $("#answer-title").textContent = "\u6b63\u5728\u7ec4\u7ec7\u56de\u7b54";
  $("#answer-source-chip").textContent = "\u7b49\u5f85\u672c\u8f6e\u7ed3\u679c";
}

function renderLongWaitNotice(elapsedMs) {
  const elapsedSeconds = Math.floor(elapsedMs / 1000);
  if (elapsedSeconds < 15 || !$("#answer-panel") || $("#answer-panel").hidden) return;
  const waitingLabel = elapsedSeconds >= 60
    ? "模型响应较慢，仍会自动完成"
    : "正在等待模型响应";
  const waitingMessage = elapsedSeconds >= 60
    ? `已等待 ${elapsedSeconds} 秒；任务仍在后台运行，页面会自动接收结果。`
    : "任务已提交，模型正在生成结果，请不要重复提交。";
  $("#answer-title").textContent = waitingLabel;
  $("#answer-source-chip").textContent = waitingMessage;
  const runningStep = [...state.liveProcessSteps.values()].find(
    (step) => step.status === "running" || step.status === "started",
  );
  if (runningStep) {
    runningStep.label = waitingLabel;
    runningStep.detail = waitingMessage;
    renderProcess([...state.liveProcessSteps.values()]);
  }
}

function renderRuntimeCheckpoint(task) {
  const runtimeStatus = task.status === "waiting_review"
    ? "waiting_approval"
    : task.status === "waiting_user"
      ? "waiting_input"
      : task.status;
  state.currentTask = task;
  state.taskId = task.id;
  setBusy(true);
  markAnswerPending();
  $("#answer-status").textContent = runtimeTaskStatusLabels[runtimeStatus]
    || "等待 Runtime 控制";
  $("#answer-title").textContent = runtimeStatus === "paused"
    ? "任务已暂停"
    : "任务等待 Runtime 控制";
  $("#answer-source-chip").textContent = "等待 checkpoint 操作";
  $("#context-task-title").textContent = "已从持久化 checkpoint 恢复";
  renderProcess([{ label: "已从持久化 checkpoint 恢复", status: "waiting" }]);
  void refreshRuntimeTaskControls(task.id);
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
  event.preventDefault(); if (state.taskId || state.submitInFlight) return;
  state.submitInFlight = true;
  await identityReady;
  const runSequence = state.runSequence + 1;
  state.runSequence = runSequence;
  state.cancelRequested = false;
  $("#form-error").textContent = "";
  const question = $("#question-input").value.trim();
  const studentAttempt = $("#student-attempt-input").value.trim();
  const teachingMode = inferLearningMode(question, studentAttempt);
  $("#teaching-mode").value = teachingMode;
  const learningFollowUp = pendingLearningFollowUp;
  const requestedCourse = learningFollowUp?.course_id || state.activeCourse || "AUTO";
  const requestedIntent = learningFollowUp?.intent || state.intentOverride || "unknown";
  const selectedFiles = selectedMaterialFiles();
  if (!question && !selectedFiles.length) {
    $("#form-error").textContent = "请输入题目或上传材料";
    state.submitInFlight = false;
    return;
  }
  $("#question-input").value = "";
  $("#student-attempt-input").value = "";
  autoGrow();
  updateAutoDetection(question, studentAttempt);
  state.lastQuestion = question; state.activeMemoryIds.clear(); setBusy(true);
  markAnswerPending();
  renderProcess([{ label: "正在理解你的需求", status: "running" }]);
  $("#context-usage").replaceChildren(el("div", { class: "context-empty" }, [
    el("strong", { text: "正在组装本次上下文" }),
    el("p", { text: "任务完成后会展示实际使用的消息、记忆和预算。" }),
  ]));
  try {
    await ensureSession(); state.activeCourse = "AUTO"; localStorage.removeItem("xinzhi_student_course"); archiveCurrentAnswer(); if (question) addMessage(question, "user", "", selectedFiles); else addMessage(`已上传 ${selectedFiles.length} 个材料`, "user", "", selectedFiles);
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
    const researchAnalysis = buildResearchAnalysisV2(question, materials);
    const payload = buildStudentTaskPayload({
      sessionId: state.sessionId,
      userId: state.userId,
      userRole: state.userRole,
      courseId: requestedCourse,
      intent: requestedIntent,
      scenarioId: state.activeScenarioId || null,
      canonicalInput: canonical,
      materials,
      responseDepth: $("#depth-select").value,
      circuitVisualizationEnabled: $("#circuit-visualization-toggle").checked,
      teachingMode,
      studentAttempt,
      learningFollowUp,
      requestId: `student_${crypto.randomUUID()}`,
      researchAnalysis: researchAnalysis || undefined,
    });
    const task = await api("/api/v1/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    pendingLearningFollowUp = null;
    state.taskId = task.id; state.currentTask = task; localStorage.setItem("xinzhi_last_task", task.id); addMessage("已识别：课程、任务与学习方式将由系统自动协作", "system");
    void refreshRuntimeTaskControls(task.id);
    const finishedTask = await waitForTask(task.id, runSequence);
    if (!finishedTask || runSequence !== state.runSequence || state.cancelRequested) return;
    renderResult(finishedTask); await loadSessionList();
    clearImage();
  } catch (error) { $("#form-error").textContent = `${error.message}。请检查本地服务后重试。`; }
  finally {
    if (runSequence === state.runSequence) {
      state.taskId = "";
      state.submitInFlight = false;
      setBusy(false);
    }
  }
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
      materialManager.removeAt(index);
    });
    item.append(meta, remove);
    previewList.append(item);
  });
  $("#image-preview").hidden = false;
}
function clearImage() {
  materialManager.clear();
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
function applyParams() {
  if (params.get("prompt")) $("#question-input").value = params.get("prompt");
  updateResearchAnalysisPanel();
  updateAutoDetection();
}

async function loadCapabilities() {
  try {
    const payload = await api("/api/v1/capabilities");
    const features = new Map((payload.workspace_features || []).map((item) => [item.id, item]));
    all("[data-capability]").forEach((button) => {
      const feature = features.get(button.dataset.capability);
      if (!feature) return;
      button.classList.toggle("capability-unavailable", !feature.available);
      button.disabled = !feature.available;
      button.setAttribute("aria-disabled", String(!feature.available));
      const stateLabel = button.querySelector(".capability-state");
      if (stateLabel) stateLabel.textContent = feature.frozen ? "已冻结" : feature.available ? (feature.knowledge_enhanced ? "本地资料增强" : "内部 Agent 就绪") : "配置后可用";
    });
  } catch (error) {
    all("[data-capability] .capability-state").forEach((node) => { node.textContent = "状态待确认"; });
  }
}

window.addEventListener("DOMContentLoaded", () => {
  initShell({ page: "workspace", title: "智能任务工作台", description: "目标输入与学科智能体协作", context: "自动识别 · 本地知识增强", audience: "student" });
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
  if (innerWidth <= 1180 && !document.body.classList.contains("presentation-mode")) setContextOpen(false);
  all("[data-prompt]").forEach((button) => button.addEventListener("click", async () => {
    $("#question-input").value = button.dataset.prompt;
    pendingLearningFollowUp = null;
    $("#question-input").placeholder = "输入你的问题，或点击上方案例开始";
    state.activeCourse = button.dataset.course || "AUTO";
    $("#course-select").value = state.activeCourse;
    state.intentOverride = button.dataset.intent || "";
    state.activeScenarioPrompt = button.dataset.prompt || "";
    state.activeScenarioId = button.dataset.scenarioId
      || showcaseScenarioByCapability[button.dataset.capability]
      || "";
    $("#form-error").textContent = "";
    try {
      await attachExampleImage(button);
    } catch (error) {
      $("#form-error").textContent = error.message;
    }
    updateResearchAnalysisPanel(); updateAutoDetection(); updateShell(); autoGrow(); $("#question-input").focus();
  }));
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
  $("#question-input").addEventListener("input", (event) => {
    if (state.activeScenarioPrompt && event.target.value !== state.activeScenarioPrompt) {
      // A showcase contract belongs to its original prompt. Do not let a
      // later edit keep routing an unrelated question to that scenario.
      state.activeScenarioId = "";
      state.activeScenarioPrompt = "";
      state.activeCourse = "AUTO";
      state.intentOverride = "";
    }
    autoGrow(); updateAutoDetection(); updateResearchAnalysisPanel();
  });
  $("#student-attempt-input").addEventListener("input", () => updateAutoDetection());
  $("#question-input").addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("#student-form").requestSubmit(); } });
  $("#course-select").value = "AUTO";
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
    state.submitInFlight = false;
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
  $("#follow-up").addEventListener("click", () => {
    const task = state.currentTask;
    pendingLearningFollowUp = task?.id
      ? {
          course_id: task.course_id || "",
          intent: "",
          source_task_id: task.id,
          action: "follow_up",
        }
      : null;
    $("#question-input").focus();
    $("#question-input").placeholder = "继续追问这一回答…";
  });
  $("#retry-task").addEventListener("click", () => void retryCurrentTask());
  $("#reask").addEventListener("click", () => { $("#question-input").value = state.lastQuestion; autoGrow(); $("#question-input").focus(); });
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
