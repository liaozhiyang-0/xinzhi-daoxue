const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");

const baseURL = process.env.XINZHI_BROWSER_BASE_URL || "http://127.0.0.1:8021";
const outputDir = process.env.XINZHI_SCREENSHOT_DIR || path.resolve("docs/reviews/web_ui_screenshots");
const imagePath = process.env.XINZHI_BROWSER_TEST_IMAGE;
fs.mkdirSync(outputDir, { recursive: true });
const results = [];

async function shot(page, name, fullPage = true) {
  await page.screenshot({ path: path.join(outputDir, `${name}.png`), fullPage });
  results.push(name);
}

async function load(page, route) {
  await page.goto(`${baseURL}${route}`, { waitUntil: "networkidle" });
  await page.locator("#app-sidebar .brand-lockup").waitFor();
}

(async () => {
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: "light" });
  page.setDefaultTimeout(45000);
  const errors = [];
  page.on("pageerror", (error) => errors.push(`${page.url()}: ${error.message}`));

  await load(page, "/");
  await shot(page, "01-home-light");
  await page.locator('[data-theme-choice="dark"]').click();
  await shot(page, "02-home-dark");

  await load(page, "/student");
  await page.evaluate(() => localStorage.removeItem("xinzhi_theme"));
  await page.reload({ waitUntil: "networkidle" });
  await shot(page, "03-student-empty");
  await page.locator("#course-select").selectOption("CT");
  await page.locator("#question-input").fill("为什么电容电压不能突变？");
  await page.locator("#send-button").click();
  await page.waitForFunction(() => !document.querySelector("#send-button").disabled, null, { timeout: 90000 });
  await page.locator("#answer-panel").waitFor({ state: "visible" });
  await shot(page, "04-student-completed-answer");

  await page.locator('[data-mode="solve"]').click();
  if (imagePath && fs.existsSync(imagePath)) {
    await page.locator("#image-input").setInputFiles({ name: "demo-circuit.png", mimeType: "image/png", buffer: fs.readFileSync(imagePath) });
    await page.locator("#image-preview").waitFor({ state: "visible" });
  }
  await shot(page, "05-student-image-solver");

  await load(page, "/debug/rag");
  await shot(page, "06-rag-overview");
  await page.locator("#run-button").click();
  await page.waitForFunction(() => !document.querySelector("#run-button").disabled, null, { timeout: 90000 });
  await page.locator("[data-tab-target=process]").click();
  await shot(page, "07-rag-retrieval-results");

  await load(page, "/debug/agents");
  await page.locator("#agent-grid tr[data-agent]").first().waitFor();
  await shot(page, "08-agent-list");
  await page.locator("#agent-grid tr[data-agent]").first().click();
  await page.locator("[data-tab-target=contract]").click();
  await shot(page, "09-agent-detail");

  await load(page, "/system");
  await page.waitForFunction(() => document.querySelectorAll("#service-grid .metric-card").length >= 3);
  await shot(page, "10-system-status");
  await load(page, "/demo");
  await shot(page, "11-demo-center");
  await load(page, "/demo?presentation=1");
  await shot(page, "12-presentation-mode");

  await page.setViewportSize({ width: 1366, height: 768 });
  await load(page, "/student");
  await shot(page, "13-laptop-1366x768", false);
  await page.setViewportSize({ width: 390, height: 844 });
  await load(page, "/");
  await shot(page, "14-mobile-390x844", false);

  if (errors.length) throw new Error(`browser errors:\n${errors.join("\n")}`);
  console.log(JSON.stringify({ screenshots: results, count: results.length, errors: [] }, null, 2));
  await browser.close();
})().catch((error) => { console.error(error.stack || error.message); process.exit(1); });
