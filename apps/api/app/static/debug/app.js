const form = document.querySelector("#task-form");
const answer = document.querySelector("#answer");
const summary = document.querySelector("#summary");
const notice = document.querySelector("#notice");

async function ensureSession() {
  const input = document.querySelector("#session-id");
  if (input.value.trim()) return input.value.trim();
  const response = await fetch("/api/v1/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: "debug-user", course_id: document.querySelector("#course").value, title: "debug" }),
  });
  const data = await response.json();
  input.value = data.id;
  return data.id;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  answer.textContent = "运行中…";
  const sessionId = await ensureSession();
  const response = await fetch("/api/v1/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      user_id: "debug-user",
      course_id: document.querySelector("#course").value,
      intent: document.querySelector("#intent").value,
      canonical_input: { text: document.querySelector("#question").value },
    }),
  });
  const task = await response.json();
  const result = task.result_content || {};
  const structured = result.structured_result || {};
  const metrics = result.metrics || {};
  notice.hidden = structured.route_source !== "cloud_fallback";
  const fields = {
    "会话 ID": task.session_id,
    input_mode: structured.input_mode,
    "路由来源": structured.route_source,
    "目标 Agent": task.agent_id,
    "课程": task.course_id,
    intent: task.intent,
    "知识库命中数": (result.citations || []).length,
    "缓存命中": metrics.cache_hit,
    Provider: task.provider,
    "当前状态": task.status,
    "运行耗时": metrics.total_latency_ms,
    "引用": (result.citations || []).join("\n"),
    "错误信息": task.error_message || "",
  };
  summary.innerHTML = Object.entries(fields).map(([key, value]) => `<dt>${key}</dt><dd>${value ?? ""}</dd>`).join("");
  answer.textContent = result.answer || task.error_message || JSON.stringify(task, null, 2);
});
