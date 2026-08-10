const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const python = path.join(root, ".venv", "Scripts", "python.exe");
const port = process.env.XINZHI_TEACHER_BROWSER_PORT || "8022";
const baseURL = `http://127.0.0.1:${port}`;
const testDatabasePath = path.join(
  os.tmpdir(),
  `xinzhi-teacher-browser-${process.pid}.db`,
);
const testDatabaseURL = `sqlite+aiosqlite:///${testDatabasePath.replaceAll("\\", "/")}`;
const outputDir = path.resolve(
  process.env.XINZHI_TEACHER_BROWSER_OUTPUT
    || `.local_outputs/runtime_teacher_browser_acceptance_${process.pid}`,
);
const providerProfile = process.env.XINZHI_TEACHER_BROWSER_PROVIDER_PROFILE || "mock";
const useRealLocalProviders = providerProfile === "real_local";
const scenarioName = process.env.XINZHI_TEACHER_BROWSER_SCENARIO || "lesson_prep";
const scenarioDefinitions = {
  lesson_prep: {
    capability: "lesson_prep",
    agentId: "TEACH_01_LESSON_PREP_V1",
    prompt: "Design a privacy-safe circuit-theory lesson on Kirchhoff laws with learning goals, formative assessment, and teacher review points.",
  },
  assignment_review: {
    capability: "assignment_review",
    agentId: "TEACH_02_ASSIGNMENT_REVIEW_V1",
    prompt: "Review this anonymized assignment response: a 10V source in series with a 5 ohm resistor has student answer I=10/5=2A. Identify correct parts, risks, and feedback.",
  },
  academic_writing: {
    capability: "academic_writing",
    agentId: "RESEARCH_02_ACADEMIC_WRITING_V1",
    prompt: "Rewrite this sentence in rigorous academic language: the experiment shows that the filter works very well. Do not invent measurements or citations.",
  },
  course_qa: {
    capability: "course_qa",
    agentId: "GENERAL_QUESTION_V1",
    prompt: "Explain why capacitor voltage cannot change instantaneously, using a concise course-grounded explanation.",
  },
};
const scenario = scenarioDefinitions[scenarioName];
if (!scenario) {
  throw new Error(`unsupported teacher browser scenario: ${scenarioName}`);
}
const adminLogin = "runtime_teacher_acceptance_admin";
const adminPassword = "RuntimeTeacherAcceptance2026!";

const runtimeLaunchModes = useRealLocalProviders
  ? `${scenario.agentId}=default`
  : [
      "ACADEMIC_PROBLEM_SOLVER",
      "GENERAL_QUESTION_V1",
      "LEARN_01_LOCAL_RETRIEVAL_V1",
      "TEACH_01_LESSON_PREP_V1",
      "TEACH_02_ASSIGNMENT_REVIEW_V1",
      "RESEARCH_01_ACADEMIC_SEARCH_V1",
      "RESEARCH_02_ACADEMIC_WRITING_V1",
    ].map((agentId) => `${agentId}=default`).join(",");

const serverEnvironment = {
  ...process.env,
  APP_ENV: "test",
  TEST_DATABASE_URL: testDatabaseURL,
  AUTH_REQUIRED: "true",
  AUTH_ALLOW_GUEST: "false",
  DEFAULT_AGENT_PROVIDER: "mock",
  ALLOW_AGENT_MOCKS: useRealLocalProviders ? "false" : "true",
  XINGCHEN_ENABLED: "false",
  IFLYTEK_SPARK_ENABLED: useRealLocalProviders ? "true" : "false",
  DASHSCOPE_ENABLED: useRealLocalProviders ? "true" : "false",
  SPARK_ENABLED: "false",
  OVERALL_ROUTING_ENABLED: "false",
  RAG_ENABLED: "false",
  RAG_WARMUP_ON_STARTUP: "false",
  RESEARCH_KNOWLEDGE_ENABLED: "false",
  RESEARCH_KNOWLEDGE_MAINTENANCE_ENABLED: "false",
  IMAGE_EMBEDDING_ENABLED: "false",
  RERANKER_ENABLED: "false",
  MINIO_ENDPOINT: "127.0.0.1:1",
  AGENT_RUNTIME_DEFAULT_ENABLED: "true",
  AGENT_RUNTIME_SOLVER_ENABLED: "true",
  AGENT_RUNTIME_GENERAL_ENABLED: "true",
  AGENT_RUNTIME_KNOWLEDGE_QA_ENABLED: "true",
  AGENT_RUNTIME_TEACHING_ENABLED: "true",
  AGENT_RUNTIME_ACADEMIC_WRITING_ENABLED: "true",
  AGENT_RUNTIME_EXTERNAL_RESEARCH_ENABLED: "true",
  AGENT_RUNTIME_LAUNCH_MODES: runtimeLaunchModes,
  AGENT_RUNTIME_RELEASE_GATE_REQUIRED: "false",
  AGENT_RUNTIME_PLAN_PROPOSALS_ENABLED: "true",
};

let server;

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function waitForHealth() {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    try {
      const response = await fetch(`${baseURL}/api/v1/health`);
      if (response.ok) return;
    } catch {}
    await sleep(500);
  }
  throw new Error("teacher browser acceptance server did not become ready");
}

function createAdmin() {
  const result = spawnSync(
    python,
    [
      path.join(root, "scripts", "create_admin.py"),
      "--login",
      adminLogin,
      "--display-name",
      "Runtime Teacher Acceptance",
      "--password-stdin",
    ],
    {
      cwd: root,
      windowsHide: true,
      env: serverEnvironment,
      input: `${adminPassword}\n${adminPassword}\n`,
      encoding: "utf8",
      stdio: ["pipe", "ignore", "pipe"],
    },
  );
  if (result.status !== 0) {
    throw new Error(`isolated admin creation failed with exit code ${result.status}`);
  }
}

async function stopServer() {
  if (!server || server.exitCode !== null) return;
  if (process.platform === "win32" && server.pid) {
    spawnSync("taskkill", ["/PID", String(server.pid), "/T", "/F"], {
      windowsHide: true,
      stdio: "ignore",
    });
  } else {
    server.kill("SIGTERM");
  }
  await sleep(500);
}

function removeTemporaryDatabase() {
  for (const target of [
    testDatabasePath,
    `${testDatabasePath}-shm`,
    `${testDatabasePath}-wal`,
  ]) {
    try {
      fs.rmSync(target, { force: true });
    } catch {}
  }
}

async function readJson(page, url) {
  return page.evaluate(async (resource) => {
    const response = await fetch(resource);
    if (!response.ok) throw new Error(`${resource}: HTTP ${response.status}`);
    return response.json();
  }, url);
}

async function waitForRuntimeApproval(page, taskId, observations) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const projection = await readJson(
      page,
      `/api/v1/tasks/${encodeURIComponent(taskId)}/runtime-controls`,
    );
    const task = await readJson(page, `/api/v1/tasks/${encodeURIComponent(taskId)}`);
    observations.push({
      attempt,
      task_status: task.status,
      runtime_status: projection.status,
      control_scope: projection.control_scope,
      plan_proposal_id: projection.plan_proposal?.proposal_id || null,
      controls: projection.controls || [],
      approve_visible: await page.locator("#runtime-task-approve").isVisible().catch(() => false),
      approve_enabled: await page.locator("#runtime-task-approve").isEnabled().catch(() => false),
    });
    if (["completed", "failed", "cancelled"].includes(task.status)) return task;
    if (projection.status === "waiting_approval") {
      const approve = page.locator("#runtime-task-approve");
      await approve.waitFor({ state: "visible", timeout: 15_000 });
      if (await approve.isDisabled()) throw new Error("teacher approval control is disabled");
      await approve.click();
      await sleep(900);
    } else {
      await sleep(500);
    }
  }
  throw new Error("runtime approval did not reach a terminal task state within the bounded wait");
}

async function collectEvidence(page, taskId) {
  const [identity, task, events, controls] = await Promise.all([
    readJson(page, "/api/v1/auth/me"),
    readJson(page, `/api/v1/tasks/${encodeURIComponent(taskId)}`),
    readJson(page, `/api/v1/tasks/${encodeURIComponent(taskId)}/events`),
    readJson(page, `/api/v1/tasks/${encodeURIComponent(taskId)}/runtime-controls`),
  ]);
  let debug = null;
  try {
    debug = await readJson(
      page,
      `/api/v1/debug/execution/${encodeURIComponent(taskId)}`,
    );
  } catch {}
  const sequences = events.map((event) => Number(event.sequence));
  const runtime = debug?.runtime || {};
  const runtimeNodes = Array.isArray(runtime.observability?.nodes)
    ? runtime.observability.nodes
      .filter((node) => node && typeof node === "object")
      .map((node) => ({
        node_id: node.node_id || null,
        status: node.status || null,
        error_code: node.error_code || null,
      }))
    : [];
  const runtimeChildren = Array.isArray(runtime.children)
    ? runtime.children.map((child) => ({
      run_id: child.run_id || null,
      parent_node_id: child.parent_node_id || null,
      status: child.status || null,
      state_version: child.state_version || null,
    }))
    : [];
  return {
    identity: { role: identity.role, user_id: identity.user_id || identity.id },
    task: {
      id: task.id,
      status: task.status,
      agent_id: task.agent_id,
      result_provider: task.result_content?.provider || null,
      error_message: task.error_message || null,
      failure_category: task.failure_category || null,
    },
    runtime_controls: {
      status: controls.status,
      control_scope: controls.control_scope,
      runtime_run_id: controls.runtime_run_id,
    },
    runtime_budget: runtime.budget || null,
    runtime_nodes: runtimeNodes,
    runtime_children: runtimeChildren,
    event_count: events.length,
    event_sequences_strictly_increasing: sequences.every(
      (value, index) => index === 0 || value > sequences[index - 1],
    ),
  };
}

(async () => {
  fs.mkdirSync(outputDir, { recursive: true });
  const report = {
    profile: "isolated_authenticated_teacher_browser",
    provider_profile: providerProfile,
    scenario: scenarioName,
    expected_agent_id: scenario.agentId,
    base_url: baseURL,
    single_api_pid: null,
    task_id: null,
    approval_observations: [],
    evidence: null,
    page_errors: [],
    request_failures: [],
    status: "failed",
  };
  let browser;
  try {
    server = spawn(
      python,
      ["-m", "uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "127.0.0.1", "--port", port],
      { cwd: root, windowsHide: true, stdio: "ignore", env: serverEnvironment },
    );
    report.single_api_pid = server.pid;
    await waitForHealth();
    createAdmin();

    browser = await chromium.launch({ channel: "msedge", headless: true });
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    page.setDefaultTimeout(60_000);
    page.on("pageerror", (error) => report.page_errors.push(error.message));
    page.on("requestfailed", (request) => report.request_failures.push(`${request.method()} ${request.url()}`));

    await page.goto(`${baseURL}/login?next=${encodeURIComponent("/workspace?role=teacher")}`, { waitUntil: "networkidle" });
    await page.locator('input[name="login"]').fill(adminLogin);
    await page.locator('input[name="password"]').fill(adminPassword);
    await page.locator("#auth-submit").click();
    await page.waitForURL("**/workspace**", { timeout: 30_000 });
    await page.locator("#app-sidebar .brand-lockup").waitFor();
    await page.waitForFunction(() => document.body.dataset.userRole === "admin" || document.body.innerText.includes("管理员"), null, { timeout: 10_000 }).catch(() => {});

    const capabilityButton = page.locator(`[data-capability="${scenario.capability}"]`);
    await capabilityButton.click();
    const selectedCapabilityPrompt = await capabilityButton.getAttribute("data-prompt");
    await page.locator("#question-input").fill(selectedCapabilityPrompt || scenario.prompt);
    await page.locator("#student-form").evaluate((form) => form.requestSubmit());
    await page.waitForFunction(() => Boolean(localStorage.getItem("xinzhi_last_task")), null, { timeout: 30_000 });
    report.task_id = await page.evaluate(() => localStorage.getItem("xinzhi_last_task"));
    if (!report.task_id) throw new Error("workspace did not publish a task id");

    await page.locator("#runtime-task-controls").waitFor({ state: "visible", timeout: 60_000 });
    await page.screenshot({ path: path.join(outputDir, "teacher-waiting-approval.png"), fullPage: true });
    await waitForRuntimeApproval(page, report.task_id, report.approval_observations);
    await page.waitForFunction(
      () => !document.querySelector("#send-button")?.disabled,
      null,
      { timeout: 120_000 },
    );
    report.evidence = await collectEvidence(page, report.task_id);
    await page.screenshot({ path: path.join(outputDir, "teacher-completed.png"), fullPage: true });
    if (report.evidence.identity.role !== "admin") throw new Error("authenticated browser identity was not admin");
    if (report.evidence.task.status !== "completed") throw new Error(`task ended as ${report.evidence.task.status}: ${report.evidence.task.error_message || "no error message"}`);
    if (report.evidence.task.agent_id !== scenario.agentId) throw new Error(`task routed to ${report.evidence.task.agent_id}, expected ${scenario.agentId}`);
    if (!report.evidence.event_sequences_strictly_increasing) throw new Error("task event sequence is not strictly increasing");
    report.status = "completed";
  } catch (error) {
    report.error = error.message;
  } finally {
    fs.writeFileSync(path.join(outputDir, "report.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8");
    if (browser) await browser.close().catch(() => {});
    await stopServer();
    removeTemporaryDatabase();
  }
  console.log(JSON.stringify(report, null, 2));
  if (report.status !== "completed") process.exitCode = 1;
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
