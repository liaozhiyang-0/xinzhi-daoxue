const { $, api, el, initShell, toast } = XinzhiUI;
const presentation = new URLSearchParams(location.search).get("presentation") === "1";
const themes = [
  { number: "01", title: "课程知识问答", goal: "自动识别 AE、运行课程 RAG、选择 LEARN 并校验引用", duration: "约 2 分钟", cloud: true, href: "/workspace?prompt=为什么负反馈能够稳定放大倍数？" },
  { number: "02", title: "教案设计", goal: "自动选择 TEACH_01，提取90分钟和学生层次并准备 AE 资料", duration: "约 3 分钟", cloud: true, href: "/workspace?prompt=给大二学生设计一节90分钟的负反馈放大电路课程，要包含例题、课堂活动和课后作业。" },
  { number: "03", title: "作业批改", goal: "从题目、学生答案与评分标准中自动选择 TEACH_02", duration: "约 3 分钟", cloud: true, href: "/workspace?prompt=请批改。题目：10V电源串联5欧电阻求电流。学生答案：2A。评分标准：列式4分，结果和单位6分。满分：10分。" },
  { number: "04", title: "学术写作", goal: "自动选择 RESEARCH_02，不使用课程 RAG，不新增引用或实验事实", duration: "约 2 分钟", cloud: true, href: "/workspace?prompt=请把这段结果改成严谨的论文表达，不新增事实：在合成测试中，方案A的指标高于方案B。" },
  { number: "05", title: "数据分析", goal: "自动选择 RESEARCH_03；无原始数据时明确为分析方案", duration: "约 2 分钟", cloud: true, href: "/workspace?prompt=这些二分类实验结果适合用什么统计方法分析？请只给分析计划，不虚构p值。" },
  { number: "06", title: "边界与一次重路由", goal: "用完整 CT 求解请求展示唯一 Solver 选择、visited_agents 与重路由上限", duration: "约 3 分钟", cloud: true, href: "/workspace?prompt=请完整列方程并求解：10V理想电压源与5欧电阻串联，求回路电流。" },
];
function themeCard(theme) { return el("article", { class: "demo-theme" }, [el("span", { class: "demo-number", text: theme.number }), el("h2", { text: theme.title }), el("p", { text: theme.goal }), el("dl", {}, [el("div", {}, [el("dt", { text: "预计时间" }), el("dd", { text: theme.duration })]), el("div", {}, [el("dt", { text: "云端调用" }), el("dd", { text: theme.cloud ? "需要，开始前确认" : "不需要" })])]), el("a", { class: "button secondary", href: theme.href + (presentation ? `${theme.href.includes("?") ? "&" : "?"}presentation=1` : ""), text: "开始演示" })]); }
async function loadLastTrace() {
  const id = localStorage.getItem("xinzhi_last_task"); if (!id) return toast("暂无最近任务，请先在工作台完成一次真实任务", "degraded");
  try {
    const data = await api(`/api/v1/debug/execution/${encodeURIComponent(id)}`); const steps = data.overview?.execution_steps || [];
    $("#trace-story-title").textContent = data.overview?.title || `任务 ${id}`; $("#open-trace").href = `/debug/execution?task_id=${encodeURIComponent(id)}`;
    $("#trace-story-steps").replaceChildren(...steps.map((step, index) => el("div", { class: "story-step" }, [el("span", { text: String(index + 1).padStart(2, "0") }), el("strong", { text: step.label }), el("small", { text: step.status })])));
    $("#trace-story").hidden = false; $("#trace-story").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) { toast(error.message, "failed"); }
}
window.addEventListener("DOMContentLoaded", () => { initShell({ page: "demo", title: "演示中心", description: "真实任务故事线与会议演示" }); $("#demo-themes").replaceChildren(...themes.map(themeCard)); if (presentation) $("#presentation-link").hidden = true; $("#check-last-trace").addEventListener("click", loadLastTrace); });
