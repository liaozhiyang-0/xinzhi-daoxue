const { $, api, el, initShell, toast } = XinzhiUI;
const presentation = new URLSearchParams(location.search).get("presentation") === "1";
const readinessLabels = {
  evidence_requires_manual_review: "外部证据需要人工复核",
  demo_uses_mock_or_local_fallback: "演示使用 Mock 或本地降级能力",
  no_runtime_or_mock_available: "暂无可用的运行能力或演示 Mock",
  commercialization_plan_incomplete: "商业化交付信息尚未完整配置",
};

function formatReadinessMessage(value) {
  const message = String(value || "");
  if (readinessLabels[message]) return readinessLabels[message];
  if (message.startsWith("demo_uses_declared_fallback:")) {
    return `演示将使用已声明的降级 Agent：${message.slice("demo_uses_declared_fallback:".length)}`;
  }
  if (message.startsWith("agent_publication_status:")) {
    return `Agent 发布状态：${message.slice("agent_publication_status:".length)}`;
  }
  return message;
}

function scenarioTheme(scenario, index) {
  const demoCase = scenario.demo_cases?.[0] || {};
  const prompt = demoCase.prompt || scenario.summary;
  const href = `/workspace?prompt=${encodeURIComponent(prompt)}&intent=${encodeURIComponent(scenario.intents?.[0] || "unknown")}&course=${encodeURIComponent(demoCase.course || "AUTO")}`;
  return {
    number: String(index + 1).padStart(2, "0"),
    title: scenario.name,
    goal: `${scenario.summary} 客户：${scenario.commercialization.buyer}`,
    prompt,
    businessContext: demoCase.business_context || scenario.summary,
    expectedOutput: demoCase.expected_output || [],
    reviewBoundary: demoCase.review_boundary || "需要人工复核",
    duration: `${(demoCase.expected_output || []).length} 项结构化输出`,
    capability: demoCase.expected_agent || scenario.agent_id,
    value: scenario.commercialization.value_capture,
    readiness: "预检中",
    readinessDetail: "正在读取运行配置",
    href,
  };
}

async function scenarioWithPreflight(scenario, index, preflight = null) {
  const theme = scenarioTheme(scenario, index);
  try {
    const readiness = preflight || await api(
      `/api/v1/scenarios/${encodeURIComponent(scenario.id)}/preflight`,
      {},
      30_000,
    );
    theme.readiness = readiness.production_ready
      ? "生产可用"
      : readiness.demo_ready
        ? "Mock/降级可演示"
        : "待配置";
    theme.readinessDetail = readiness.blockers?.length
      ? `阻塞：${readiness.blockers.map(formatReadinessMessage).join("、")}`
      : (readiness.warnings || []).map(formatReadinessMessage).join("、") || "无阻塞项";
  } catch (error) {
    theme.readiness = "预检失败";
    theme.readinessDetail = error.message;
  }
  return theme;
}

function themeCard(theme) {
  const link = theme.href + (presentation ? "&presentation=1" : "");
  return el("article", { class: "demo-theme" }, [
    el("span", { class: "demo-number", text: theme.number }),
    el("h2", { text: theme.title }),
    el("p", { text: theme.goal }),
    el("p", { class: "demo-business-context", text: `业务背景：${theme.businessContext}` }),
    el("details", {}, [
      el("summary", { text: "查看完整示例问题" }),
      el("p", { class: "demo-prompt", text: theme.prompt }),
    ]),
    el("dl", {}, [
      el("div", {}, [el("dt", { text: "输出契约" }), el("dd", { text: `${theme.duration}：${theme.expectedOutput.join("、")}` })]),
      el("div", {}, [el("dt", { text: "能力绑定" }), el("dd", { text: theme.capability })]),
      el("div", {}, [el("dt", { text: "价值闭环" }), el("dd", { text: theme.value })]),
      el("div", {}, [el("dt", { text: "人工边界" }), el("dd", { text: theme.reviewBoundary })]),
      el("div", {}, [el("dt", { text: "运行预检" }), el("dd", { text: theme.readiness })]),
    ]),
    el("small", { class: "demo-readiness-detail", text: theme.readinessDetail }),
    el("a", { class: "button secondary", href: link, text: "开始场景演示" }),
  ]);
}

async function loadScenarios() {
  try {
    const [scenarios, readiness] = await Promise.all([
      api("/api/v1/scenarios", {}, 30_000),
      api("/api/v1/scenarios/readiness", {}, 30_000),
    ]);
    const readinessById = new Map(readiness.map((item) => [item.scenario_id, item]));
    const themes = await Promise.all(
      scenarios.map((scenario, index) => scenarioWithPreflight(
        scenario,
        index,
        readinessById.get(scenario.id) || null,
      )),
    );
    $("#demo-themes").replaceChildren(...themes.map(themeCard));
  } catch (error) {
    $("#demo-themes").replaceChildren(
      el("p", { class: "context-empty", text: `场景目录暂不可用：${error.message}` }),
    );
    toast(error.message, "failed");
  }
}

async function loadLastTrace() {
  const id = localStorage.getItem("xinzhi_last_task");
  if (!id) return toast("暂无最近任务，请先完成一次场景演示", "degraded");
  try {
    const data = await api(`/api/v1/debug/execution/${encodeURIComponent(id)}`);
    const steps = data.overview?.execution_steps || [];
    $("#trace-story-title").textContent = data.overview?.title || `任务 ${id}`;
    $("#open-trace").href = `/debug/execution?task_id=${encodeURIComponent(id)}`;
    $("#trace-story-steps").replaceChildren(
      ...steps.map((step, index) => el("div", { class: "story-step" }, [
        el("span", { text: String(index + 1).padStart(2, "0") }),
        el("strong", { text: step.label }),
        el("small", { text: step.status }),
      ])),
    );
    $("#trace-story").hidden = false;
    $("#trace-story").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    toast(error.message, "failed");
  }
}

window.addEventListener("DOMContentLoaded", () => {
  initShell({ page: "demo", title: "演示中心", description: "五个商业化场景与结构化演示路径" });
  if (presentation) $("#presentation-link").hidden = true;
  $("#check-last-trace").addEventListener("click", loadLastTrace);
  loadScenarios();
});
