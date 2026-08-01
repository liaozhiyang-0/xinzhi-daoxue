const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const python = path.join(root, ".venv", "Scripts", "python.exe");
const port = process.env.XINZHI_AUTH_BROWSER_PORT || "8033";
const baseURL = `http://127.0.0.1:${port}`;
const databasePath = path.join(os.tmpdir(), `xinzhi-auth-browser-${process.pid}.db`);
const databaseURL = `sqlite+aiosqlite:///${databasePath.replaceAll("\\", "/")}`;
const suffix = `${Date.now()}`;
const adminLogin = `browser-admin-${suffix}@example.com`;
const adminPassword = "BrowserAdmin!2026";
const studentLogin = `browser-student-${suffix}@example.com`;
const studentPassword = "BrowserStudent!2026";
const managedLogin = `browser-managed-${suffix}@example.com`;
const managedPassword = "BrowserManaged!2026";
const resetPassword = "BrowserReset!2026";
const serverEnv = {
  ...process.env,
  APP_ENV: "test",
  TEST_DATABASE_URL: databaseURL,
  AUTH_REQUIRED: "true",
  AUTH_ALLOW_REGISTRATION: "true",
  AUTH_ALLOW_GUEST: "true",
  AUTH_GUEST_SIGNING_KEY: "browser-acceptance-signing-key",
  DEFAULT_AGENT_PROVIDER: "mock",
  ALLOW_MOCK_FALLBACK: "true",
  XINGCHEN_ENABLED: "false",
  RAG_ENABLED: "false",
  IMAGE_EMBEDDING_ENABLED: "false",
  RERANKER_ENABLED: "false",
  MINIO_ENDPOINT: "127.0.0.1:1",
};
const server = spawn(python, ["-m", "uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "127.0.0.1", "--port", port], {
  cwd: root,
  windowsHide: true,
  stdio: "ignore",
  env: serverEnv,
});

const checks = [];
const browserErrors = [];

function assert(condition, message) {
  if (!condition) throw new Error(message);
  checks.push(message);
}

async function waitForServer() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(`${baseURL}/api/v1/health`);
      if (response.ok) return;
    } catch (_error) {}
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("browser acceptance server did not become ready");
}

function bootstrapAdmin() {
  const result = spawnSync(python, ["scripts/create_admin.py", "--login", adminLogin, "--display-name", "Browser Admin", "--password-stdin"], {
    cwd: root,
    env: serverEnv,
    input: [adminPassword, adminPassword].join(String.fromCharCode(10)) + String.fromCharCode(10),
    encoding: "utf8",
    windowsHide: true,
  });
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

async function loginThroughPage(page, login, password) {
  await page.locator("#login-form input[name=login]").fill(login);
  await page.locator("#login-form input[name=password]").fill(password);
  await page.locator("#login-form button[type=submit]").click();
  await page.waitForURL((url) => url.pathname === "/student");
  await page.locator("#app-sidebar .brand-lockup").waitFor();
}

async function run() {
  await waitForServer();
  bootstrapAdmin();
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  const contexts = [];
  try {
    const guestContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    contexts.push(guestContext);
    const guestPage = await guestContext.newPage();
    trackPage(guestPage, "guest");
    await goto(guestPage, "/");
    assert(await guestPage.locator("a[href*='/login?next=/student']").count() === 1, "首页提供登录/注册入口");
    assert(await guestPage.locator("a[href='/student']").count() === 1, "首页提供游客入口");
    await goto(guestPage, "/student");
    await guestPage.locator(".identity-gate").waitFor();
    assert(await guestPage.locator("[data-guest-entry]").count() === 1, "学习端首屏提供游客按钮");
    await guestPage.locator("[data-guest-entry]").click();
    await guestPage.locator(".identity-gate").waitFor({ state: "detached" });
    await guestPage.locator(".identity-control").getByText("游客模式", { exact: true }).waitFor();
    await guestPage.locator("#new-session").click();
    await guestPage.locator("#session-list .session-item").waitFor();
    assert(true, "游客模式可以创建学习会话");

    const accountContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    contexts.push(accountContext);
    const accountPage = await accountContext.newPage();
    trackPage(accountPage, "student-account");
    await goto(accountPage, "/login?mode=register&next=/student");
    await accountPage.locator("#login-form input[name=login]").fill(studentLogin);
    await accountPage.locator("#login-form input[name=display_name]").fill("Browser Student");
    await accountPage.locator("#login-form input[name=password]").fill(studentPassword);
    await accountPage.locator("#login-form button[type=submit]").click();
    await accountPage.waitForURL((url) => url.pathname === "/student");
    await accountPage.locator("#app-sidebar .brand-lockup").waitFor();
    await accountPage.locator(".identity-control").getByText("Browser Student", { exact: true }).waitFor();
    assert(true, "前端注册后自动进入学习工作台");
    await accountPage.locator("#new-session").click();
    await accountPage.locator("#session-list .session-item").waitFor();
    assert(true, "注册账号可以创建学习会话");
    await accountPage.locator(".identity-logout").click();
    await accountPage.waitForURL((url) => url.pathname === "/login");
    assert(await accountPage.locator("#login-form").isVisible(), "学习端可以退出登录");
    await loginThroughPage(accountPage, studentLogin, studentPassword);
    await accountPage.locator(".identity-control").getByText("Browser Student", { exact: true }).waitFor();
    assert(true, "前端登录后可以返回学习工作台");

    const adminContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    contexts.push(adminContext);
    const adminPage = await adminContext.newPage();
    trackPage(adminPage, "admin");
    await goto(adminPage, "/admin");
    await adminPage.locator("#admin-login").waitFor();
    await adminPage.locator("#admin-login-form input[name=login]").fill(adminLogin);
    await adminPage.locator("#admin-login-form input[name=password]").fill(adminPassword);
    await adminPage.locator("#admin-login-form button[type=submit]").click();
    await adminPage.locator("#admin-app").waitFor();
    await adminPage.locator("#admin-metrics .admin-metric").first().waitFor();
    await adminPage.locator("#account-table").getByText(studentLogin, { exact: true }).waitFor();
    assert(true, "管理员可以登录并看到账号总览");

    await adminPage.locator("#open-create-account").click();
    await adminPage.locator("#account-dialog").waitFor();
    await adminPage.locator("#account-form input[name=login]").fill(managedLogin);
    await adminPage.locator("#account-form input[name=display_name]").fill("Browser Managed");
    await adminPage.locator("#account-form select[name=role]").selectOption("student");
    await adminPage.locator("#account-form input[name=password]").fill(managedPassword);
    await adminPage.locator("#account-form button[value=create]").click();
    await adminPage.locator("#account-table").getByText(managedLogin, { exact: true }).waitFor();
    assert(true, "管理员可以通过页面创建虚拟账号");

    const managedContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    contexts.push(managedContext);
    const managedPage = await managedContext.newPage();
    trackPage(managedPage, "managed-account");
    await goto(managedPage, "/login?next=/student");
    await loginThroughPage(managedPage, managedLogin, managedPassword);
    await adminPage.locator("#admin-refresh").click();
    await adminPage.locator("#session-table").getByText(managedLogin, { exact: true }).waitFor();
    assert(true, "管理端可以看到真实登录会话");

    const managedRow = adminPage.locator("#account-table tr").filter({ hasText: managedLogin });
    await managedRow.locator("button").nth(0).click();
    await managedRow.locator('[data-status="disabled"]').waitFor();
    await managedRow.locator("button").nth(0).click();
    await managedRow.locator('[data-status="active"]').waitFor();
    assert(true, "管理员可以启用和停用账号");

    adminPage.once("dialog", (dialog) => dialog.accept(resetPassword));
    await managedRow.locator("button").nth(1).click();
    await adminPage.waitForTimeout(500);
    await goto(managedPage, "/login?next=/student");
    await loginThroughPage(managedPage, managedLogin, resetPassword);
    assert(true, "管理员重置密码后新密码可以登录");

    await adminPage.locator("#admin-refresh").click();
    const refreshedRow = adminPage.locator("#account-table tr").filter({ hasText: managedLogin });
    adminPage.once("dialog", (dialog) => dialog.accept());
    await refreshedRow.locator("button").nth(2).click();
    await adminPage.locator("#admin-refresh").click();
    await adminPage.waitForTimeout(800);
    assert(await adminPage.locator("#session-table").getByText(managedLogin, { exact: true }).count() === 0, "管理端刷新后不再显示已撤销会话");
    await goto(managedPage, "/student");
    const revokedMe = await managedPage.evaluate(async () => {
      const response = await fetch("/api/v1/auth/me");
      return { status: response.status, body: await response.text() };
    });
    assert(revokedMe.status === 401, `撤销后的认证状态为 401（实际 ${revokedMe.status}）`);
    await managedPage.locator(".identity-gate").waitFor();
    assert(true, "管理员撤销会话后原会话失效");

    await adminPage.locator('[data-tab-target="audit"]').click();
    await adminPage.locator("#audit-table .admin-table").waitFor();
    assert(true, "管理端可以查看审计日志");
    if (browserErrors.length) throw new Error(`browser errors:\n${browserErrors.join("\n")}`);
    console.log(JSON.stringify({ baseURL, virtual_accounts: [adminLogin, studentLogin, managedLogin], checks }, null, 2));
  } finally {
    await Promise.all(contexts.map((context) => context.close().catch(() => {})));
    await browser.close();
  }
}

(async () => {
  try { await run(); }
  catch (error) { console.error(error.stack || error.message); process.exitCode = 1; }
  finally {
    if (server.exitCode === null && !server.killed) server.kill();
    for (const target of [databasePath, `${databasePath}-shm`, `${databasePath}-wal`]) {
      try { fs.rmSync(target, { force: true }); } catch (_error) {}
    }
  }
})();
