const { $, api, el, initShell, toast } = XinzhiUI;
const presentation = new URLSearchParams(location.search).get("presentation") === "1";

function scenarioTheme(scenario, index) {
  const prompt = scenario.demo_steps?.[0] || scenario.summary;
  const href = `/workspace?scenario_id=${encodeURIComponent(scenario.id)}&prompt=${encodeURIComponent(prompt)}`;
  return {
    number: String(index + 1).padStart(2, "0"),
    title: scenario.name,
    goal: `${scenario.summary} 客户：${scenario.commercialization.buyer}`,
    duration: `${scenario.demo_steps?.length || 0} 个演示步骤`,
    capability: scenario.agent_id,
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
      ? `阻塞：${readiness.blockers.join("、")}`
      : (readiness.warnings || []).join("、") || "无阻塞项";
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
    el("dl", {}, [
      el("div", {}, [el("dt", { text: "执行步骤" }), el("dd", { text: theme.duration })]),
      el("div", {}, [el("dt", { text: "能力绑定" }), el("dd", { text: theme.capability })]),
      el("div", {}, [el("dt", { text: "价值闭环" }), el("dd", { text: theme.value })]),
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
  initShell({ page: "demo", title: "演示中心", description: "六个商业化场景与真实任务 Trace" });
  if (presentation) $("#presentation-link").hidden = true;
  $("#check-last-trace").addEventListener("click", loadLastTrace);
  loadScenarios();
});
