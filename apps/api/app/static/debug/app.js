const form = document.querySelector("#task-form");
const errorBox = document.querySelector("#error");
const eventsList = document.querySelector("#events");
const resultBox = document.querySelector("#result");
const summary = document.querySelector("#task-summary");
const cancelButton = document.querySelector("#cancel");
const retryButton = document.querySelector("#retry");
const knowledgeForm = document.querySelector("#knowledge-form");
const knowledgeResult = document.querySelector("#knowledge-result");

let sessionId = null;
let taskId = null;
let eventSource = null;

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body?.error?.message || `HTTP ${response.status}`);
  }
  return body;
}

function renderTask(task) {
  taskId = task.id;
  summary.innerHTML = `
    <dt>task_id</dt><dd>${task.id}</dd>
    <dt>status</dt><dd>${task.status}</dd>
    <dt>provider</dt><dd>${task.provider}</dd>
    <dt>agent</dt><dd>${task.agent_id}</dd>
    <dt>route</dt><dd>${task.route_status}: ${task.route_reason}</dd>
    <dt>attempt</dt><dd>${task.attempt}</dd>`;
  cancelButton.disabled = ["completed", "failed", "cancelled"].includes(task.status);
  retryButton.disabled = !["failed", "cancelled"].includes(task.status);
}

async function ensureSession() {
  if (sessionId) return sessionId;
  const session = await api("/api/v1/sessions", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      user_id: document.querySelector("#user-id").value,
      course_id: document.querySelector("#course-id").value,
      title: "本地调试会话"
    })
  });
  sessionId = session.id;
  return sessionId;
}

async function uploadAttachments() {
  const refs = [];
  for (const file of document.querySelector("#attachments").files) {
    const body = new FormData();
    body.append("upload", file);
    refs.push(await api("/api/v1/files", {method: "POST", body}));
  }
  return refs.map(file => ({
    file_id: file.id,
    filename: file.filename,
    content_type: file.content_type,
    size_bytes: file.size_bytes,
    storage_key: file.storage_key,
    provider_file_id: null,
    checksum_sha256: file.checksum_sha256
  }));
}

function connectEvents(id) {
  eventSource?.close();
  eventsList.replaceChildren();
  eventSource = new EventSource(`/api/v1/tasks/${id}/stream`);
  const eventNames = [
    "task.created", "route.selected", "route.unsupported", "task.queued", "task.running", "agent.started",
    "agent.progress", "knowledge.query_normalized", "knowledge.retrieved", "knowledge.context_built",
    "knowledge.insufficient", "answer.retrieval_only_created", "agent.output", "artifact.created", "cancel.requested",
    "task.cancelled", "task.completed", "task.failed", "task.retry_created"
  ];
  for (const name of eventNames) {
    eventSource.addEventListener(name, async event => {
      const item = document.createElement("li");
      item.textContent = `#${event.lastEventId} ${name} ${event.data}`;
      eventsList.append(item);
      if (["task.completed", "task.failed", "task.cancelled"].includes(name)) {
        eventSource.close();
        const task = await api(`/api/v1/tasks/${id}`);
        renderTask(task);
        const providerLabel = task.provider === "xingchen"
          ? "真实星辰工作流结果"
          : task.provider === "mock" ? "当前为 Mock 结果" : "本地知识库结果";
        resultBox.textContent = `${providerLabel}\n\n` + JSON.stringify(task.result_content || {
          error: task.error_message
        }, null, 2);
        if (task.artifact_ids?.length) {
          const artifact = await api(`/api/v1/artifacts/${task.artifact_ids[0]}`);
          resultBox.textContent += `\n\nArtifact:\n${JSON.stringify(artifact, null, 2)}`;
        }
      }
    });
  }
  eventSource.onerror = () => {
    if (eventSource.readyState === EventSource.CLOSED) return;
    errorBox.textContent = "SSE 暂时断开，浏览器将自动重连。";
  };
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  errorBox.textContent = "";
  resultBox.textContent = "任务已提交，等待后台执行…";
  try {
    const attachments = await uploadAttachments();
    const task = await api("/api/v1/tasks", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        session_id: await ensureSession(),
        user_id: document.querySelector("#user-id").value,
        course_id: document.querySelector("#course-id").value,
        scene: document.querySelector("#intent").value === "solve_problem" ? "solving" : "learning",
        intent: document.querySelector("#intent").value,
        canonical_input: {text: document.querySelector("#question").value},
        attachments,
        options: {mock_delay_seconds: Number(document.querySelector("#delay").value)}
      })
    });
    renderTask(task);
    connectEvents(task.id);
  } catch (error) {
    errorBox.textContent = error.message;
  }
});

cancelButton.addEventListener("click", async () => {
  try {
    renderTask(await api(`/api/v1/tasks/${taskId}/cancel`, {method: "POST"}));
  } catch (error) {
    errorBox.textContent = error.message;
  }
});

retryButton.addEventListener("click", async () => {
  try {
    const task = await api(`/api/v1/tasks/${taskId}/retry`, {method: "POST"});
    renderTask(task);
    connectEvents(task.id);
  } catch (error) {
    errorBox.textContent = error.message;
  }
});

knowledgeForm.addEventListener("submit", async event => {
  event.preventDefault();
  knowledgeResult.textContent = "正在检索…";
  try {
    const response = await api("/api/v1/knowledge/search", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        query: document.querySelector("#knowledge-query").value,
        course_ids: [document.querySelector("#knowledge-course").value],
        top_k: 5
      })
    });
    knowledgeResult.textContent = JSON.stringify(response, null, 2);
  } catch (error) {
    knowledgeResult.textContent = error.message;
  }
});
