const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { chromium } = require("playwright");
const {
  assertPortAvailable,
  parseBrowserPort,
  waitForSpawnedHealth,
} = require("./browser_server_guard");

const root = path.resolve(__dirname, "..");
const python = path.join(root, ".venv", "Scripts", "python.exe");
const port = process.env.XINZHI_MULTIMODAL_BROWSER_PORT || "8035";
const portNumber = parseBrowserPort(port, "multimodal browser acceptance");
const baseURL = `http://127.0.0.1:${port}`;
const databasePath = path.join(os.tmpdir(), `xinzhi-multimodal-browser-${process.pid}.db`);
const materialPath = path.join(os.tmpdir(), `xinzhi-multimodal-browser-${process.pid}.txt`);
const adminLogin = `multimodal-admin-${Date.now()}@example.com`;
const adminPassword = "MultimodalAdmin!2026";
const serverEnv = {
  ...process.env,
  APP_ENV: "test",
  TEST_DATABASE_URL: `sqlite+aiosqlite:///${databasePath.replaceAll("\\", "/")}`,
  AUTH_REQUIRED: "true",
  AUTH_ALLOW_REGISTRATION: "true",
  AUTH_ALLOW_GUEST: "true",
  AUTH_GUEST_SIGNING_KEY: "multimodal-browser-acceptance-signing-key",
  DEFAULT_AGENT_PROVIDER: "mock",
  ALLOW_MOCK_FALLBACK: "true",
  IFLYTEK_SPARK_ENABLED: "false",
  DASHSCOPE_ENABLED: "false",
  SPARK_ENABLED: "false",
  OVERALL_ROUTING_ENABLED: "false",
  RAG_ENABLED: "false",
  IMAGE_EMBEDDING_ENABLED: "false",
  RERANKER_ENABLED: "false",
  MINIO_ENDPOINT: "127.0.0.1:1",
};
let server = null;
const checks = [];
const browserErrors = [];

function assert(condition, message) {
  if (!condition) throw new Error(message);
  checks.push(message);
}

async function waitForServer() {
  await assertPortAvailable(portNumber, "multimodal browser acceptance");
  server = spawn(
    python,
    ["-m", "uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "127.0.0.1", "--port", port],
    { cwd: root, windowsHide: true, stdio: "ignore", env: serverEnv },
  );
  await waitForSpawnedHealth({ server, baseURL, label: "multimodal browser acceptance", attempts: 60 });
}

function bootstrapAdmin() {
  const result = spawnSync(
    python,
    ["scripts/create_admin.py", "--login", adminLogin, "--display-name", "Multimodal Admin", "--password-stdin"],
    {
      cwd: root,
      env: serverEnv,
      input: `${adminPassword}\n${adminPassword}\n`,
      encoding: "utf8",
      windowsHide: true,
    },
  );
  if (result.status !== 0) {
    throw new Error(`admin bootstrap failed: ${result.stdout || ""}\n${result.stderr || ""}`);
  }
}

function trackPage(page, name) {
  page.setDefaultTimeout(30_000);
  page.on("pageerror", (error) => browserErrors.push(`${name}: ${error.message}`));
  page.on("response", (response) => {
    if (response.status() >= 500) browserErrors.push(`${name}: ${response.status()} ${response.url()}`);
  });
}

async function goto(page, route) {
  await page.goto(`${baseURL}${route}`, { waitUntil: "networkidle" });
}

async function run() {
  fs.writeFileSync(materialPath, "多模态材料测试\n这是通过前端文件选择器上传的文本。", "utf8");
  await waitForServer();
  bootstrapAdmin();
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  const contexts = [];
  try {
    const studentContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    contexts.push(studentContext);
    const studentPage = await studentContext.newPage();
    trackPage(studentPage, "workspace");
    await goto(studentPage, "/student");
    await studentPage.locator("[data-guest-entry]").click();
    await studentPage.locator(".identity-gate").waitFor({ state: "detached" });
    await studentPage.locator("#image-input").setInputFiles(materialPath);
    await studentPage.locator("#preview-images .upload-preview-item").waitFor();
    assert(await studentPage.locator("#image-name").textContent().then((text) => text.includes("1 个材料")), "工作台显示文本材料预览");
    await studentPage.locator("#question-input").fill("请概括上传材料");
    const uploadResponse = studentPage.waitForResponse(
      (response) => response.url().includes("/api/v1/files") && response.request().method() === "POST",
      { timeout: 30_000 },
    );
    await studentPage.locator("#send-button").click();
    const uploadedResponse = await uploadResponse;
    assert(uploadedResponse.status() === 201, `工作台上传材料接口返回 201（实际 ${uploadedResponse.status()}）`);
    const uploadedPayload = await uploadedResponse.json();
    assert(uploadedPayload.ingestion_status === "ready", "工作台上传文本材料后解析状态为已就绪");

    const adminContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    contexts.push(adminContext);
    const adminPage = await adminContext.newPage();
    trackPage(adminPage, "admin");
    await goto(adminPage, "/admin");
    await adminPage.locator("#admin-login-form input[name=login]").fill(adminLogin);
    await adminPage.locator("#admin-login-form input[name=password]").fill(adminPassword);
    await adminPage.locator("#admin-login-form button[type=submit]").click();
    await adminPage.locator("#admin-app").waitFor();
    await adminPage.locator("[data-admin-module-target=files]").click();
    await adminPage.locator("#admin-file-table").getByText("xinzhi-multimodal-browser").waitFor();
    assert(await adminPage.locator("#admin-file-table").getByText("已就绪").count() >= 1, "管理系统文件中心显示已解析材料");
    assert(await adminPage.locator("#admin-file-summary").getByText("文件总数").count() === 1, "管理系统文件中心显示统计指标");
    if (browserErrors.length) throw new Error(`browser errors:\n${browserErrors.join("\n")}`);
    console.log(JSON.stringify({ baseURL, checks }, null, 2));
  } finally {
    await Promise.all(contexts.map((context) => context.close().catch(() => {})));
    await browser.close();
  }
}

(async () => {
  try {
    await run();
  } catch (error) {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  } finally {
    if (server && server.exitCode === null && !server.killed) server.kill();
    for (const target of [databasePath, `${databasePath}-shm`, `${databasePath}-wal`, materialPath]) {
      try { fs.rmSync(target, { force: true }); } catch (_error) {}
    }
  }
})();
