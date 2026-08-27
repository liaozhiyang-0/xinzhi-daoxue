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

(async () => {
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  try {
    for (const status of [500, 503, 504]) await assertTaskHttpFailure(browser, status);
    await assertDelayedSubmit(browser);
    await assertSseDisconnectRecovery(browser);
    await assertAttachmentAndSessionRestore(browser);
    await assertRapidSubmitGuard(browser);
    console.log(JSON.stringify({
      scenarios: ["server_500", "server_503", "api_delay", "sse_disconnect", "attachment", "session_restore", "rapid_submit"],
      errors: [],
    }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
