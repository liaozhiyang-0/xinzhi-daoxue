const { spawn, spawnSync } = require("node:child_process");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const python = path.join(root, ".venv", "Scripts", "python.exe");
const port = process.env.XINZHI_BROWSER_PORT || "8021";
const baseURL = `http://127.0.0.1:${port}`;
const server = spawn(python, ["-m", "uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "127.0.0.1", "--port", port], {
  cwd: root,
  windowsHide: true,
  stdio: "ignore",
  env: { ...process.env, APP_ENV: "test", DEFAULT_AGENT_PROVIDER: "mock", XINGCHEN_ENABLED: "false", RAG_ENABLED: "false", IMAGE_EMBEDDING_ENABLED: "false", RERANKER_ENABLED: "false", ALLOW_AGENT_MOCKS: "true", IFLYTEK_SPARK_API_KEY: "", DASHSCOPE_API_KEY: "", MINIO_ENDPOINT: "127.0.0.1:1" },
});

async function ready() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try { const response = await fetch(`${baseURL}/api/v1/health`); if (response.ok) return; } catch {}
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("browser acceptance server did not become ready");
}

(async () => {
  try {
    await ready();
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
    server.kill();
  }
})().catch((error) => { server.kill(); console.error(error.stack || error.message); process.exit(1); });
