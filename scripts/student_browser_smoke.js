const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");

const baseURL = process.env.XINZHI_BROWSER_BASE_URL || "http://127.0.0.1:8021";
const outputDir = process.env.XINZHI_SCREENSHOT_DIR || path.resolve("docs/reviews/workspace_v2_screenshots");
const imagePath = process.env.XINZHI_BROWSER_TEST_IMAGE;
fs.mkdirSync(outputDir, { recursive: true });
const results = [];

async function shot(page, name, fullPage = false) {
  await page.screenshot({ path: path.join(outputDir, `${name}.png`), fullPage });
  results.push(name);
}
async function load(page, route) {
  await page.goto(`${baseURL}${route}`, { waitUntil: "networkidle" });
  const identityGate = page.locator(".identity-gate");
  if (route.startsWith("/workspace") || route.startsWith("/student")) {
    const gateShown = await identityGate.waitFor({ state: "visible", timeout: 5_000 }).then(() => true).catch(() => false);
    if (gateShown) {
      await page.locator("[data-guest-entry]").click();
      await identityGate.waitFor({ state: "detached" });
    }
  }
  await page.locator("#app-sidebar .brand-lockup").waitFor();
}
async function ask(page, question, capability = "") {
  if (capability) {
    const capabilityButton = page.locator(`[data-capability="${capability}"]`);
    if (await capabilityButton.count()) await capabilityButton.click();
  }
  await page.locator("#question-input").fill(question);
  await page.locator("#send-button").click();
  await page.waitForFunction(
    () => document.querySelector("#question-input").value === "",
  );
  await page.waitForFunction(() => !document.querySelector("#send-button").disabled, null, { timeout: 120000 });
  await page.locator("#answer-panel").waitFor({ state: "visible" });
}

(async () => {
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light" });
  const page = await context.newPage(); page.setDefaultTimeout(60000);
  const errors = []; page.on("pageerror", (error) => errors.push(`${page.url()}: ${error.message}`));

  await load(page, "/workspace");
  await page.evaluate(() => { localStorage.removeItem("xinzhi_theme"); localStorage.removeItem("xinzhi_student_session"); });
  await page.reload({ waitUntil: "networkidle" });
  const navigation = await page.evaluate(() => { const entry = performance.getEntriesByType("navigation")[0]; return { dom_content_loaded_ms: Math.round(entry.domContentLoadedEventEnd), load_ms: Math.round(entry.loadEventEnd), transfer_bytes: performance.getEntriesByType("resource").reduce((sum, item) => sum + (item.transferSize || 0), 0), request_count: performance.getEntriesByType("resource").length }; });
  await shot(page, "01-workspace-empty");

  await ask(page, "为什么电容电压不能突变？");
  await shot(page, "02-ct-knowledge-answer");
  const sourceChip = page.locator("#answer-source-chip");
  if (await sourceChip.count() && await sourceChip.isVisible()) await sourceChip.click();
  await shot(page, "03-context-evidence");
  const citation = page.locator("#answer-text .citation-link").first();
  if (await citation.count()) await citation.click(); else if (await page.locator(".evidence-card").count()) await page.locator(".evidence-card").first().click();
  await shot(page, "04-evidence-linked");
  if (await page.locator("#document-dialog[open]").count()) await page.locator("#close-document-dialog").click();
  await page.locator('[data-context-tab="process"]').click();
  await shot(page, "05-process-simple");
  await page.locator('[data-context-tab="info"]').click();
  await shot(page, "06-answer-info");

  await page.locator("#new-session").click(); await ask(page, "负反馈为什么能稳定增益？");
  await shot(page, "07-ae-knowledge-answer");
  await page.locator("#new-session").click(); await ask(page, "锁存器和触发器有什么区别？");
  await shot(page, "08-de-knowledge-answer");

  await page.locator("#new-session").click(); await ask(page, "请完整列方程并求解：一个10V电压源串联5Ω电阻，求回路电流。");
  await shot(page, "09-solver-text");
  if (imagePath && fs.existsSync(imagePath)) {
    await page.locator("#new-session").click();
    await page.locator("#question-input").fill("请解答图片中的电路题。");
    await page.locator("#image-input").setInputFiles({ name: "demo-circuit.png", mimeType: "image/png", buffer: fs.readFileSync(imagePath) });
    await page.locator("#image-preview").waitFor({ state: "visible" });
    await shot(page, "10-solver-image-ready");
  }
  await shot(page, "11-mock-or-fallback-boundary");

  const lastTask = await page.evaluate(() => localStorage.getItem("xinzhi_last_task"));
  await load(page, `/debug/execution?task_id=${encodeURIComponent(lastTask)}`);
  await page.locator("#execution-console").waitFor({ state: "visible" });
  await shot(page, "12-execution-debug");
  await page.locator('[data-tab-target="retrieval"]').click();
  await shot(page, "13-evidence-flow-comparison");

  await load(page, "/demo"); await shot(page, "14-demo-center");
  await page.setViewportSize({ width: 1280, height: 720 });
  await load(page, "/workspace?presentation=1"); await shot(page, "15-presentation-1280x720");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.evaluate(() => localStorage.setItem("xinzhi_theme", "dark")); await page.reload({ waitUntil: "networkidle" }); await shot(page, "16-workspace-dark");
  await page.evaluate(() => localStorage.setItem("xinzhi_theme", "light")); await page.setViewportSize({ width: 390, height: 844 }); await load(page, "/workspace"); await shot(page, "17-workspace-mobile");

  if (errors.length) throw new Error(`browser errors:\n${errors.join("\n")}`);
  const renderMs = await page.evaluate(() => localStorage.getItem("xinzhi_last_render_ms"));
  console.log(JSON.stringify({ screenshots: results, count: results.length, errors: [], first_view: navigation, last_answer_render_ms: renderMs }, null, 2));
  await browser.close();
})().catch((error) => { console.error(error.stack || error.message); process.exit(1); });
