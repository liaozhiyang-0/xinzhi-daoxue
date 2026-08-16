const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const {
  assertPortAvailable,
  parseBrowserPort,
  waitForSpawnedHealth,
} = require("./browser_server_guard");

const root = path.resolve(__dirname, "..");
const python = path.join(root, ".venv", "Scripts", "python.exe");
const port = process.env.XINZHI_BROWSER_PORT || "8021";
const portNumber = parseBrowserPort(port, "browser acceptance");
const baseURL = `http://127.0.0.1:${port}`;
const testDatabasePath = path.join(
  os.tmpdir(),
  `xinzhi-browser-acceptance-${process.pid}.db`,
);
const testDatabaseURL = `sqlite+aiosqlite:///${testDatabasePath.replaceAll("\\", "/")}`;
let server = null;

async function startServer() {
  await assertPortAvailable(portNumber, "browser acceptance");
  server = spawn(python, ["-m", "uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "127.0.0.1", "--port", port], {
    cwd: root,
    windowsHide: true,
    stdio: "ignore",
    env: { ...process.env, APP_ENV: "test", TEST_DATABASE_URL: testDatabaseURL, DEFAULT_AGENT_PROVIDER: "mock", IFLYTEK_SPARK_ENABLED: "false", DASHSCOPE_ENABLED: "false", SPARK_ENABLED: "false", OVERALL_ROUTING_ENABLED: "false", RAG_ENABLED: "false", RAG_WARMUP_ON_STARTUP: "false", RESEARCH_KNOWLEDGE_ENABLED: "false", RESEARCH_KNOWLEDGE_MAINTENANCE_ENABLED: "false", IMAGE_EMBEDDING_ENABLED: "false", RERANKER_ENABLED: "false", ALLOW_AGENT_MOCKS: "true", IFLYTEK_SPARK_API_KEY: "", DASHSCOPE_API_KEY: "", MINIO_ENDPOINT: "127.0.0.1:1" },
  });
  await waitForSpawnedHealth({ server, baseURL, label: "browser acceptance" });
}

async function stopServer() {
  if (server && server.exitCode === null && !server.killed) {
    const exited = new Promise((resolve) => server.once("exit", resolve));
    server.kill();
    await Promise.race([
      exited,
      new Promise((resolve) => setTimeout(resolve, 2000)),
    ]);
  }
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

(async () => {
  try {
    await startServer();
    const preflight = spawnSync(python, [path.join(root, "scripts", "demo_cli.py"), "preflight", "--base-url", baseURL], {
      cwd: root, windowsHide: true, stdio: "inherit", env: process.env,
    });
    if (preflight.status !== 0) throw new Error("demo preflight failed");
    const result = spawnSync(process.execPath, [path.join(root, "scripts", "student_browser_smoke.js")], {
      cwd: root, windowsHide: true, stdio: "inherit",
      env: { ...process.env, XINZHI_BROWSER_BASE_URL: baseURL, XINZHI_BROWSER_TEST_IMAGE: path.join(root, "docs", "reviews", "web_ui_baseline", "student-before.png") },
    });
    process.exitCode = result.status ?? 1;
  } finally {
    await stopServer();
  }
})().catch((error) => { console.error(error.stack || error.message); process.exit(1); });
