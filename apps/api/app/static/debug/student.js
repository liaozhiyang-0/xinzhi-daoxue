const { $, all, api, badge, el, initShell, renderMarkdown, toast } = XinzhiUI;
const params = new URLSearchParams(location.search);
const state = {
  mode: params.get("mode") === "solve" ? "solve" : "learn",
  sessionId: localStorage.getItem("xinzhi_student_session") || "",
  userId: localStorage.getItem("xinzhi_student_user") || `student_${crypto.randomUUID()}`,
  taskId: "", activeCourse: params.get("course") || localStorage.getItem("xinzhi_student_course") || "CT",
  lastQuestion: "", lastAnswer: "",
};
localStorage.setItem("xinzhi_student_user", state.userId);

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
function sourceCard(hit, course) {
  const card = el("article", { class: "source-card" });
  card.append(el("div", { class: "source-card-heading" }, [el("strong", { text: hit.title || hit.chapter || "课程资料" }), badge("ready", hit.course_id || course || "课程")]), el("p", { text: hit.snippet || hit.text_preview || hit.chapter || "已用于本次回答的课程证据。" }));
  const meta = [hit.chapter, hit.content_type].filter(Boolean).join(" · "); if (meta) card.append(el("small", { text: meta }));
  if (hit.source_ref || hit.source_uri) card.append(el("code", { class: "source-ref", text: hit.source_ref || hit.source_uri }));
  return card;
}
function renderResult(task) {
  const result = task.result_content || {}; const structured = result.structured_result || {}; const knowledge = structured.knowledge || {}; const hits = knowledge.hits || result.citations || [];
  state.lastAnswer = result.answer || task.error_message || "未返回回答";
  $("#answer-panel").hidden = false; $("#answer-agent").textContent = task.agent_id || "统一运行框架";
  const statusBadge = badge(task.status === "completed" ? (result.fallback_used ? "degraded" : "success") : "failed", task.status === "completed" ? (result.fallback_used ? "降级完成" : "已完成") : "未完成");
  statusBadge.id = "answer-status"; $("#answer-status").replaceWith(statusBadge);
  const courseName = { CT: "电路理论", AE: "模拟电子技术", DE: "数字电子技术" }[task.course_id || selectedCourse()] || task.course_id || "课程";
  $("#answer-route").textContent = `${state.mode === "solve" ? "电路解题" : "知识问答"} · ${courseName}`;
  renderMarkdown($("#answer-text"), state.lastAnswer);
  const notices = [];
  if (result.provider === "mock" || result.mock_used) notices.push({ status: "mock", text: "当前为开发态 Mock 结果，不代表正式云端工作流输出。" });
  if (result.fallback_used) notices.push({ status: "degraded", text: `云端服务暂不可用，本次回答由本地知识库生成。${result.fallback_reason ? ` 原因：${result.fallback_reason}` : ""}` });
  (result.warnings || []).filter((item) => !String(item).includes("mock_result")).forEach((item) => notices.push({ status: "warning", text: item }));
  $("#answer-notices").replaceChildren(...notices.map((item) => el("div", { class: `notice ${item.status}`, text: item.text })));
  $("#source-summary").textContent = `参考课程资料 ${hits.length}`;
  $("#source-list").replaceChildren(...(hits.length ? hits.map((hit) => sourceCard(hit, task.course_id)) : [el("div", { class: "empty-state", text: "本次回答没有可展示的课程资料来源。" })]));
  const images = $("#show-images").checked ? (result.related_images || []) : [];
  $("#related-images").replaceChildren(...images.map((item) => { const src = imageUrl(item.resource_uri); return src ? el("figure", { class: "image-thumbnail" }, [el("img", { src, alt: item.caption || "相关教材图片", loading: "lazy" }), el("figcaption", { text: item.caption || "相关教材图片" })]) : null; }).filter(Boolean));
  $("#answer-panel").scrollIntoView({ behavior: "smooth", block: "nearest" });
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
    let settled = false; const events = new EventSource(`/api/v1/tasks/${id}/stream`);
    const finish = async () => { if (settled) return; try { const task = await api(`/api/v1/tasks/${id}`); if (["completed", "failed", "cancelled"].includes(task.status)) { settled = true; events.close(); resolve(task); } } catch (error) { settled = true; events.close(); reject(error); } };
    ["task.completed", "task.failed", "task.cancelled"].forEach((name) => events.addEventListener(name, finish));
    events.addEventListener("agent.started", () => addMessage("已完成路由，正在生成回答…", "system"));
    events.onerror = () => { events.close(); const timer = setInterval(async () => { try { const task = await api(`/api/v1/tasks/${id}`); if (["completed", "failed", "cancelled"].includes(task.status)) { clearInterval(timer); if (!settled) { settled = true; resolve(task); } } } catch (error) { clearInterval(timer); if (!settled) { settled = true; reject(error); } } }, 900); };
  });
}
async function submit(event) {
  event.preventDefault(); $("#form-error").textContent = "";
  const question = $("#question-input").value.trim(); const course = selectedCourse();
  if (state.mode === "solve" && course !== "CT") { $("#form-error").textContent = "该课程完整解题工作流尚未开放"; return; }
  if (!question && !$("#image-input").files[0]) { $("#form-error").textContent = "请输入题目或上传图片"; return; }
  state.lastQuestion = question; $("#send-button").disabled = true; $("#stop-button").disabled = false;
  try {
    await ensureSession(); state.activeCourse = course; localStorage.setItem("xinzhi_student_course", course); if (question) addMessage(question);
    const file = state.mode === "solve" ? await uploadImage() : null;
    const payload = { session_id: state.sessionId, user_id: state.userId, user_role: "student", scene: state.mode === "solve" ? "solving" : "learning", course_id: course, intent: state.mode === "solve" ? "solve_problem" : "general_qa", canonical_input: { text: question }, attachments: file ? [attachmentRef(file)] : [], context_refs: [], options: { request_id: `student_${crypto.randomUUID()}`, response_depth: $("#depth-select").value } };
    const task = await api("/api/v1/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    state.taskId = task.id; addMessage("请求已提交，本地检索与专业工作流正在处理…", "system"); renderResult(await waitForTask(task.id));
    $("#question-input").value = ""; clearImage();
  } catch (error) { $("#form-error").textContent = `${error.message}。请检查本地服务后重试。`; }
  finally { state.taskId = ""; $("#send-button").disabled = false; $("#stop-button").disabled = true; }
}
function clearImage() { $("#image-input").value = ""; $("#image-preview").hidden = true; $("#preview-image").removeAttribute("src"); $("#image-name").textContent = ""; }
function applyParams() {
  if (params.get("course")) $("#course-select").value = params.get("course");
  if (params.get("prompt")) $("#question-input").value = params.get("prompt");
  if (params.get("image") === "1") setMode("solve");
}
window.addEventListener("DOMContentLoaded", () => {
  initShell({ page: "student", title: "智能学习", description: "课程问答与电路理论解题", context: "知识问答 · 电路理论" }); applyParams(); setMode(state.mode);
  all("[data-mode]").forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
  all("[data-prompt]").forEach((button) => button.addEventListener("click", () => { $("#question-input").value = button.dataset.prompt; $("#course-select").value = button.dataset.course; state.activeCourse = button.dataset.course; if (button.dataset.promptMode) setMode(button.dataset.promptMode); updateShell(); $("#question-input").focus(); }));
  $("#student-form").addEventListener("submit", submit);
  $("#question-input").addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("#student-form").requestSubmit(); } });
  $("#course-select").addEventListener("change", () => { if ($("#course-select").value !== "AUTO") state.activeCourse = $("#course-select").value; updateShell(); });
  $("#image-input").addEventListener("change", (event) => { const file = event.target.files[0]; if (!file) return clearImage(); $("#image-name").textContent = file.name; $("#preview-image").src = URL.createObjectURL(file); $("#image-preview").hidden = false; });
  $("#remove-image").addEventListener("click", clearImage);
  $("#stop-button").addEventListener("click", async () => { if (state.taskId) await api(`/api/v1/tasks/${state.taskId}/cancel`, { method: "POST" }); });
  $("#new-session").addEventListener("click", () => { state.sessionId = ""; localStorage.removeItem("xinzhi_student_session"); $("#messages").replaceChildren(); $("#answer-panel").hidden = true; $("#welcome").hidden = false; toast("已新建本地会话"); });
  $("#toggle-sources").addEventListener("click", () => { $("#source-details").open = !$("#source-details").open; });
  $("#copy-answer").addEventListener("click", async () => { await navigator.clipboard.writeText(state.lastAnswer); toast("回答已复制"); });
  $("#follow-up").addEventListener("click", () => { $("#question-input").focus(); $("#question-input").placeholder = "继续追问这一回答…"; });
  $("#reask").addEventListener("click", () => { $("#question-input").value = state.lastQuestion; $("#question-input").focus(); });
});
