"use strict";

const { chromium } = require("playwright");

const baseURL = process.env.XINZHI_BROWSER_BASE_URL || "http://127.0.0.1:8021";
const imageFixture = {
  name: "browser-fixture.png",
  mimeType: "image/png",
  buffer: Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  ),
};

async function openWorkspace(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  page.setDefaultTimeout(30_000);
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto(`${baseURL}/workspace`, { waitUntil: "networkidle" });
  const gate = page.locator(".identity-gate");
  if (await gate.isVisible().catch(() => false)) {
    await page.locator("[data-guest-entry]").click();
    await gate.waitFor({ state: "detached" });
  }
  await page.locator("#app-sidebar .brand-lockup").waitFor();
  return { context, page, pageErrors };
}

async function submit(page, question) {
  await page.locator("#question-input").fill(question);
  await page.locator("#send-button").click();
  await page.waitForFunction(
    () => document.querySelector("#question-input").value === "",
  );
}

async function waitForIdle(page) {
  await page.waitForFunction(
    () => !document.querySelector("#send-button").disabled,
    null,
    { timeout: 120_000 },
  );
}

async function assertTaskHttpFailure(browser, status) {
  const { context, page, pageErrors } = await openWorkspace(browser);
  await page.route("**/api/v1/tasks", (route) =>
    route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify({ detail: `synthetic server failure ${status}` }),
    }),
  );
  await submit(page, `浏览器故障测试：模拟服务端 ${status}。`);
  await page.waitForFunction(
    (expected) => document.querySelector("#form-error").textContent.includes(expected),
    String(status),
  );
  const errorText = await page.locator("#form-error").textContent();
  if (!errorText.includes(String(status))) throw new Error(`missing ${status} error message`);
  if (await page.locator("#send-button").isDisabled()) throw new Error(`send button stayed disabled after ${status}`);
  if (pageErrors.length) throw new Error(`page errors after ${status}: ${pageErrors.join("; ")}`);
  await context.close();
}

async function assertDelayedSubmit(browser) {
  const { context, page, pageErrors } = await openWorkspace(browser);
  await page.route("**/api/v1/tasks", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1_200));
    await route.continue();
  });
  const request = page.waitForRequest(
    (item) => item.url().endsWith("/api/v1/tasks") && item.method() === "POST",
  );
  await submit(page, "浏览器故障测试：模拟 API 延迟时保持状态正确。 ");
  await request;
  if (await page.locator("#send-button").isDisabled() !== true) throw new Error("delay did not enter busy state");
  await waitForIdle(page);
  if (pageErrors.length) throw new Error(`page errors during delay: ${pageErrors.join("; ")}`);
  await context.close();
}

async function assertSseDisconnectRecovery(browser) {
  const { context, page, pageErrors } = await openWorkspace(browser);
  let streamAttempts = 0;
  await page.route("**/api/v1/tasks/*/stream", async (route) => {
    streamAttempts += 1;
    if (streamAttempts === 1) return route.abort();
    return route.continue();
  });
  await submit(page, "浏览器故障测试：首个 SSE 连接中断后应能恢复。 ");
  await waitForIdle(page);
  if (streamAttempts < 1) throw new Error("SSE route was not observed");
  if (pageErrors.length) throw new Error(`page errors during SSE recovery: ${pageErrors.join("; ")}`);
  await context.close();
}

async function assertAttachmentAndSessionRestore(browser) {
  const { context, page, pageErrors } = await openWorkspace(browser);
  await submit(page, "浏览器故障测试：先建立会话再验证刷新恢复。 ");
  await waitForIdle(page);
  await page.locator("#image-input").setInputFiles(imageFixture);
  await page.locator("#image-preview").waitFor({ state: "visible" });
  const before = await page.evaluate(() => localStorage.getItem("xinzhi_student_session"));
  await page.reload({ waitUntil: "networkidle" });
  await page.locator("#app-sidebar .brand-lockup").waitFor();
  const after = await page.evaluate(() => localStorage.getItem("xinzhi_student_session"));
  if (before !== after) throw new Error("session identity was not restored");
  if (pageErrors.length) throw new Error(`page errors during attachment/session: ${pageErrors.join("; ")}`);
  await context.close();
}

async function assertRapidSubmitGuard(browser) {
  const { context, page, pageErrors } = await openWorkspace(browser);
  let taskPosts = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/api/v1/tasks") && request.method() === "POST") taskPosts += 1;
  });
  await page.locator("#question-input").fill("浏览器故障测试：连续快速点击发送。 ");
  await page.locator("#send-button").click();
  await page.evaluate(() => document.querySelector("#student-form").requestSubmit());
  await waitForIdle(page);
  if (taskPosts !== 1) throw new Error(`rapid submit created ${taskPosts} tasks`);
  if (pageErrors.length) throw new Error(`page errors during rapid submit: ${pageErrors.join("; ")}`);
  await context.close();
}

async function assertAcademicSolverDoesNotRenderDuplicateCards(browser) {
  const { context, page, pageErrors } = await openWorkspace(browser);
  await page.route("**/api/v1/tasks/*", async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (request.method() !== "GET" || !/^\/api\/v1\/tasks\/[^/]+$/.test(pathname)) {
      return route.continue();
    }
    const taskId = pathname.split("/").pop();
    const answer = [
      "### 1. 问题分析与假设",
      "这是一个共射放大电路，先按小信号模型分析。",
      "### 2. 关键推导步骤",
      "已知 $v_o = -g_m R_C v_{be}$，代入参数得到 $v_o=-2V$。",
      "### 3. 结论汇总",
      "输出电压为 $-2V$，负号表示输出相位反转。",
    ].join("\n\n");
    const task = {
      id: taskId,
      session_id: "browser-presentation-session",
      user_id: "browser-presentation-user",
      course_id: "AE",
      intent: "solve_problem",
      status: "completed",
      provider: "local_graph",
      agent_id: "ACADEMIC_PROBLEM_SOLVER",
      route_status: "selected",
      route_reason: "synthetic presentation regression",
      input_content: { canonical_input: { question: "请分析共射放大电路的输出电压" }, options: {} },
      result_content: {
        answer,
        provider: "local_graph",
        citations: [],
        metrics: {},
        structured_result: {
          business_view: {
            renderer_type: "academic_solver",
            banner: "",
            sections: [
              { key: "problem_summary", label: "题目摘要", content: "这是一个共射放大电路，要求求输出电压。" },
              { key: "key_equations", label: "关键方程", content: ["vo = -gm Rc vbe"] },
              { key: "steps", label: "分步解答", content: ["代入参数并计算输出电压"] },
              { key: "final_answer", label: "最终答案", content: answer },
              { key: "assumptions", label: "假设", content: ["small_signal_model"] },
              { key: "remaining_risks", label: "风险", content: ["小信号假设需要结合工作点复核"] },
            ],
          },
          presentation: {
            title: "学术题目求解 · 模拟电子技术",
            status_label: "已完成",
            source_summary: "暂无方法参考",
            provider_label: "内部 Agent 协作",
            answer_quality_status: "checked",
            requires_review: false,
            execution_steps: [],
          },
          execution_summary: {
            agent_label: "学术题目求解",
            rag_mode: "no_rag",
            used_evidence_count: 0,
            evidence_count: 0,
            citation_status: "not_run",
            timings: {},
          },
          evidence_view: [],
        },
      },
      error_message: null,
      retryable: false,
      attempt: 1,
      max_attempts: 1,
    };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(task) });
  });
  await submit(page, "浏览器呈现测试：完整模电解答不应再显示重复字段。");
  await waitForIdle(page);
  const duplicateCards = await page.locator("#business-result .business-section").count();
  if (duplicateCards !== 1) throw new Error(`expected only the risk card, found ${duplicateCards} business cards`);
  const businessText = await page.locator("#business-result").textContent();
  for (const key of ["problem_summary", "key_equations", "steps", "final_answer", "assumptions"]) {
    if (await page.locator(`#business-result .business-${key}`).count()) {
      throw new Error(`duplicate section remained visible: ${key}`);
    }
  }
  if (!businessText.includes("风险")) throw new Error("necessary risk card was removed");
  if (pageErrors.length) throw new Error(`page errors during presentation: ${pageErrors.join("; ")}`);
  await context.close();
}

(async () => {
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  try {
    for (const status of [500, 503, 504]) await assertTaskHttpFailure(browser, status);
    await assertDelayedSubmit(browser);
    await assertSseDisconnectRecovery(browser);
    await assertAttachmentAndSessionRestore(browser);
    await assertRapidSubmitGuard(browser);
    await assertAcademicSolverDoesNotRenderDuplicateCards(browser);
    console.log(JSON.stringify({
      scenarios: ["server_500", "server_503", "api_delay", "sse_disconnect", "attachment", "session_restore", "rapid_submit", "academic_solver_presentation"],
      errors: [],
    }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
