const { $, el, initShell, toast } = XinzhiUI;
const presentation = new URLSearchParams(location.search).get("presentation") === "1";
const scenes = [
  { id: "knowledge", title: "知识问答与 RAG", status: "ready", summary: "电容电压为什么不能突变？", detail: "展示 CT 课程证据、云端 LEARN、合法引用与最终回答。", flow: ["用户问题", "本地 RAG", "课程证据", "云端 LEARN", "引用校验", "最终回答"], href: "/student?mode=learn&course=CT&prompt=为什么电容电压不能突变？", cloud: true, tech: "/debug/rag" },
  { id: "courses", title: "三课程能力", status: "ready", summary: "CT / AE / DE 概念题", detail: "快速切换三门课程，说明同一入口下的课程强过滤。", flow: ["选择课程", "统一任务 API", "课程过滤", "专业回答"], href: "/student?mode=learn&course=AE&prompt=总结负反馈的作用", cloud: true, tech: "/debug/rag" },
  { id: "solver", title: "电路理论专业解题", status: "ready", summary: "稳定文字题", detail: "进入冻结的 SOLVER_CT 文字工作流，不修改其云端协议。", flow: ["文字题", "路由检查", "SOLVER_CT", "结构化答案"], href: "/student?mode=solve&course=CT&prompt=一个10V电压源串联5Ω电阻，求回路电流。", cloud: true, tech: "/debug/agents" },
  { id: "image", title: "单图片解题", status: "ready", summary: "上传一张清晰题目图片", detail: "载入解题页面并打开图片上传；不会硬编码本机私有路径。", flow: ["图片预览", "安全上传", "单图工作流", "答案"], href: "/student?mode=solve&course=CT&image=1", cloud: true, tech: "/debug/agents" },
  { id: "boundary", title: "工作流边界", status: "ready", summary: "复杂整题不会交给知识问答越界求解", detail: "展示 LEARN 的 misrouted 边界与本地路由约束。", flow: ["复杂整题", "能力检查", "misrouted", "引导专业解题"], href: "/student?mode=learn&course=CT&prompt=请完整计算含受控源电路的所有支路电流并写出全过程", cloud: true, tech: "/debug/agents" },
  { id: "fallback", title: "稳定降级", status: "degraded", summary: "受控故障模拟", detail: "进入 RAG 调试页使用受控本地降级，不修改真实 .env。", flow: ["模拟云端不可用", "本地知识库", "免责声明", "可用结果"], href: "/debug/rag?scenario=fallback", cloud: false, tech: "/debug/rag" },
  { id: "agents", title: "多 Agent 框架", status: "mock", summary: "已发布 / Mock ready / Planned", detail: "展示配置驱动接入、契约测试与执行计划。Mock 始终明确标记。", flow: ["AgentDefinition", "输入映射", "执行计划", "Provider / Mock", "统一结果"], href: "/debug/agents", cloud: false, tech: "/debug/agents" },
];
let selected = null;

function loadScene(scene) {
  selected = scene;
  $("#demo-preview").hidden = false;
  $("#preview-title").textContent = scene.title;
  $("#preview-description").textContent = scene.detail;
  $("#preview-flow").replaceChildren(...scene.flow.map((step, index) => el("div", { class: "timeline-step" }, [el("span", { text: String(index + 1) }), el("strong", { text: step })])));
  $("#technical-link").href = scene.tech;
  $("#cloud-warning").textContent = scene.cloud ? "本场景将调用星辰 API，预计等待约 20 秒；开始前会再次确认。" : "本场景不消耗云端额度。";
  $("#demo-preview").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderScenes() {
  $("#demo-scenes").replaceChildren(...scenes.map((scene, index) => el("article", { class: "card demo-scene", "data-scene": scene.id }, [
    el("div", { class: "scene-number", text: String(index + 1).padStart(2, "0") }),
    el("div", { class: "scene-copy" }, [el("span", { class: `status-badge status-${scene.status}`, text: scene.status === "mock" ? "开发模拟" : scene.status === "degraded" ? "降级演示" : "可演示" }), el("h2", { text: scene.title }), el("strong", { text: scene.summary }), el("p", { text: scene.detail })]),
    el("div", { class: "scene-actions" }, [el("button", { class: "button secondary", type: "button", text: "查看说明", onclick: () => loadScene(scene) }), el("button", { class: "button primary", type: "button", text: "载入示例", onclick: () => loadScene(scene) })]),
  ])));
}

window.addEventListener("DOMContentLoaded", () => {
  initShell({ page: "demo", title: "演示中心", description: "会议场景与稳定演示路径" });
  if (presentation) $("#presentation-link").hidden = true;
  renderScenes();
  $("#reset-demo").addEventListener("click", () => { selected = null; $("#demo-preview").hidden = true; toast("演示场景已重置"); });
  $("#start-demo").addEventListener("click", () => {
    if (!selected) return;
    if (selected.cloud && !window.confirm("本场景将调用星辰 API，预计等待约 20 秒并可能消耗额度。确认继续？")) return;
    const join = selected.href.includes("?") ? "&" : "?";
    location.href = selected.href + (presentation ? `${join}presentation=1` : "");
  });
});
