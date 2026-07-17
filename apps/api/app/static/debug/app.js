const form = document.querySelector("#task-form");
const submitButton = document.querySelector("#submit-button");
const submitLabel = document.querySelector("#submit-label");
const errorBox = document.querySelector("#error");
const eventsList = document.querySelector("#events");
const attachmentsInput = document.querySelector("#attachments");
const imageField = document.querySelector("#image-field");
const imagePreviewWrap = document.querySelector("#image-preview-wrap");
const imagePreview = document.querySelector("#image-preview");
const imageName = document.querySelector("#image-name");
const providerBadge = document.querySelector("#provider-badge");
const currentStep = document.querySelector("#current-step");
const elapsedTime = document.querySelector("#elapsed-time");
const intentSelect = document.querySelector("#intent");

let sessionId = null;
let taskId = null;
let eventSource = null;
let imagePreviewUrl = null;
let timerId = null;
let startedAt = null;
let activeInputMode = "text";

const eventLabels = {
  "task.created": "任务已创建",
  "route.selected": "已路由到电路理论解题 Agent",
  "task.queued": "任务正在排队",
  "task.running": "任务开始运行",
  "agent.started": "星辰工作流开始求解",
  "knowledge.retrieved": "已读取本地方法参考",
  "agent.output": "正在整理答案",
  "artifact.created": "回答产物已保存",
  "task.completed": "任务已完成",
  "task.failed": "任务执行失败",
  "task.cancelled": "任务已取消"
};

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body?.error?.message || `服务请求失败（HTTP ${response.status}）`;
    throw new Error(readableError(message));
  }
  return body;
}

function readableError(message) {
  const text = String(message || "未知错误");
  if (text.includes("超时")) return "星辰工作流响应超时，请稍后重试；图片题通常需要更长时间。";
  if (text.includes("连接")) return "暂时无法连接星辰服务，请检查网络后重试。";
  if (text.includes("配置不完整")) return "星辰服务尚未完成运行配置，请联系演示环境维护者。";
  if (text.includes("后台任务执行失败")) return "任务执行失败，请稍后重试并查看服务日志。";
  return text;
}

function selectedMode() {
  return document.querySelector('input[name="input-mode"]:checked').value;
}

function setBusy(busy) {
  submitButton.disabled = busy;
  submitLabel.textContent = busy ? "解题中，请稍候…" : "开始解题";
}

function setStep(label) {
  currentStep.textContent = label;
}

function startTimer() {
  clearInterval(timerId);
  startedAt = performance.now();
  elapsedTime.textContent = "0.0 秒";
  timerId = setInterval(() => {
    elapsedTime.textContent = `${((performance.now() - startedAt) / 1000).toFixed(1)} 秒`;
  }, 100);
}

function stopTimer() {
  clearInterval(timerId);
  timerId = null;
}

function setProvider(provider) {
  providerBadge.className = "provider-badge";
  if (provider === "xingchen") {
    providerBadge.classList.add("xingchen");
    providerBadge.textContent = "真实星辰";
  } else if (provider === "mock") {
    providerBadge.classList.add("mock");
    providerBadge.textContent = "Mock 演示结果";
  } else if (provider === "local") {
    providerBadge.classList.add("local");
    providerBadge.textContent = "本地知识库";
  } else {
    providerBadge.classList.add("idle");
    providerBadge.textContent = "等待运行";
  }
}

function renderList(element, values, emptyText) {
  element.replaceChildren();
  const items = Array.isArray(values) ? values.filter(Boolean) : [];
  if (!items.length) {
    const item = document.createElement("li");
    item.className = "placeholder";
    item.textContent = emptyText;
    element.append(item);
    return;
  }
  for (const value of items) {
    const item = document.createElement("li");
    item.textContent = String(value);
    element.append(item);
  }
}

function renderText(elementId, value, emptyText) {
  const element = document.querySelector(elementId);
  element.textContent = value || emptyText;
  element.classList.toggle("placeholder", !value);
}

function resetOutput() {
  document.querySelector("#task-id").textContent = "正在创建任务…";
  renderText("#problem-summary", "", "工作流返回后显示");
  renderText("#answer-text", "", "等待解题结果…");
  renderText("#final-answer", "", "暂无");
  renderList(document.querySelector("#key-equations"), [], "暂无");
  renderList(document.querySelector("#risk-list"), [], "暂无");
  renderList(document.querySelector("#source-list"), [], "本次未使用");
  eventsList.replaceChildren();
  setProvider(null);
}

function appendProgress(eventName) {
  const label = eventLabels[eventName];
  if (!label) return;
  const item = document.createElement("li");
  item.textContent = label;
  if (["task.completed", "task.failed", "task.cancelled"].includes(eventName)) {
    item.classList.add(eventName === "task.completed" ? "success" : "failed");
  }
  eventsList.append(item);
}

async function loadRuntimeStatus() {
  const status = document.querySelector("#runtime-status");
  const text = document.querySelector("#runtime-text");
  try {
    const health = await api("/health");
    status.className = "runtime-status healthy";
    const provider = health.active_provider === "xingchen" ? "真实星辰已连接" : `${health.active_provider} 模式`;
    text.textContent = `服务正常 · ${provider}`;
  } catch (error) {
    status.className = "runtime-status unhealthy";
    text.textContent = "服务不可用";
  }
}

async function ensureSession() {
  if (sessionId) return sessionId;
  const session = await api("/api/v1/sessions", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      user_id: document.querySelector("#user-id").value,
      course_id: "CT",
      title: "阶段 2.1 演示会话"
    })
  });
  sessionId = session.id;
  return sessionId;
}

async function uploadImage() {
  const file = attachmentsInput.files[0];
  if (!file) return [];
  const body = new FormData();
  body.append("upload", file);
  const uploaded = await api("/api/v1/files", {method: "POST", body});
  return [{
    file_id: uploaded.id,
    filename: uploaded.filename,
    content_type: uploaded.content_type,
    size_bytes: uploaded.size_bytes,
    storage_key: uploaded.storage_key,
    provider_file_id: null,
    checksum_sha256: uploaded.checksum_sha256
  }];
}

function renderResult(task, artifact) {
  const result = task.result_content || {};
  const structured = result.structured_result || {};
  const artifactContent = artifact?.content || {};
  const answerText = structured.answer_text || result.answer || artifactContent.answer_text || "";
  const risks = [
    ...(structured.assumptions || []).map(item => `假设：${item}`),
    ...(structured.remaining_risks || []),
    ...(result.warnings || [])
  ];
  const sources = result.citations || artifactContent.knowledge_sources || [];

  setProvider(task.provider);
  renderText("#problem-summary", structured.problem_summary, "本次工作流未提供结构化题目摘要");
  renderText("#answer-text", answerText, "工作流未返回回答文本");
  renderText("#final-answer", structured.final_answer, "请查看上方完整解答");
  renderList(document.querySelector("#key-equations"), structured.key_equations, "本次工作流未单独返回公式列表");
  renderList(document.querySelector("#risk-list"), risks, "未报告额外假设或风险");
  renderList(document.querySelector("#source-list"), sources, "本次未使用本地知识库");
}

async function finishTask(id) {
  const task = await api(`/api/v1/tasks/${id}`);
  let artifact = null;
  if (task.artifact_ids?.length) {
    artifact = await api(`/api/v1/artifacts/${task.artifact_ids[0]}`);
  }
  document.querySelector("#task-id").textContent = `任务 ${task.id}`;
  if (task.status === "completed") {
    setStep("已完成");
    renderResult(task, artifact);
  } else {
    setStep(task.status === "cancelled" ? "已取消" : "执行失败");
    errorBox.textContent = readableError(task.error_message || "任务未能完成");
    setProvider(task.provider);
  }
  stopTimer();
  setBusy(false);
}

function connectEvents(id) {
  eventSource?.close();
  eventSource = new EventSource(`/api/v1/tasks/${id}/stream`);
  for (const eventName of Object.keys(eventLabels)) {
    eventSource.addEventListener(eventName, async () => {
      appendProgress(eventName);
      if (eventName === "task.running") {
        setStep(activeInputMode === "image" ? "正在识别并求解" : "正在求解");
      } else if (["agent.output", "artifact.created"].includes(eventName)) {
        setStep("正在整理答案");
      }
      if (["task.completed", "task.failed", "task.cancelled"].includes(eventName)) {
        eventSource.close();
        try {
          await finishTask(id);
        } catch (error) {
          errorBox.textContent = readableError(error.message);
          stopTimer();
          setBusy(false);
        }
      }
    });
  }
  eventSource.onerror = () => {
    if (eventSource.readyState !== EventSource.CLOSED) {
      errorBox.textContent = "进度连接暂时中断，页面正在自动重连。";
    }
  };
}

function updateInputMode() {
  activeInputMode = selectedMode();
  const isImage = activeInputMode === "image";
  imageField.hidden = !isImage;
  document.querySelector("#question").placeholder = isImage
    ? "可选：补充一句要求，例如“请识别并解答图片中的题目”"
    : "例如：一个 10V 电压源串联 2Ω 和 3Ω 电阻，求回路电流。";
}

document.querySelectorAll('input[name="input-mode"]').forEach(input => {
  input.addEventListener("change", updateInputMode);
});

attachmentsInput.addEventListener("change", () => {
  if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
  const file = attachmentsInput.files[0];
  if (!file) {
    imagePreviewWrap.hidden = true;
    imagePreview.removeAttribute("src");
    imageName.textContent = "";
    imagePreviewUrl = null;
    return;
  }
  imagePreviewUrl = URL.createObjectURL(file);
  imagePreview.src = imagePreviewUrl;
  imageName.textContent = `${file.name} · ${Math.ceil(file.size / 1024)} KB`;
  imagePreviewWrap.hidden = false;
});

form.addEventListener("submit", async event => {
  event.preventDefault();
  errorBox.textContent = "";
  activeInputMode = selectedMode();
  const question = document.querySelector("#question").value.trim();
  const file = attachmentsInput.files[0];
  const intent = intentSelect.value;
  if (intent !== "solve_problem" && activeInputMode === "image") {
    errorBox.textContent = "课程问答和概念讲解当前只支持文字输入。";
    return;
  }
  if (activeInputMode === "text" && !question) {
    errorBox.textContent = "请输入文字题目。";
    return;
  }
  if (activeInputMode === "image" && !file) {
    errorBox.textContent = "请选择一张电路题图片。";
    return;
  }

  setBusy(true);
  resetOutput();
  startTimer();
  try {
    let attachments = [];
    if (activeInputMode === "image") {
      setStep("正在上传图片");
      attachments = await uploadImage();
      setStep("正在识别图片");
    } else {
      setStep("正在提交文字题");
    }
    const task = await api("/api/v1/tasks", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        session_id: await ensureSession(),
        user_id: document.querySelector("#user-id").value,
        course_id: "CT",
        scene: intent === "solve_problem" ? "solving" : "learning",
        intent,
        canonical_input: {
          text: question || "请识别并解答图片中的题目。"
        },
        attachments,
        options: {mock_delay_seconds: 0.5}
      })
    });
    taskId = task.id;
    document.querySelector("#task-id").textContent = `任务 ${task.id}`;
    setProvider(task.provider);
    setStep("正在求解");
    connectEvents(task.id);
  } catch (error) {
    errorBox.textContent = readableError(error.message);
    setStep("提交失败");
    stopTimer();
    setBusy(false);
  }
});

updateInputMode();
loadRuntimeStatus();
