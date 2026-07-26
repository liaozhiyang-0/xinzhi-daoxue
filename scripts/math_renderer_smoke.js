const { chromium } = require("playwright");
const path = require("node:path");

const baseURL = process.env.XINZHI_BROWSER_BASE_URL || "http://127.0.0.1:8000";

(async () => {
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  const page = await browser.newPage({ viewport: { width: 1100, height: 760 } });
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto(`${baseURL}/workspace`, { waitUntil: "networkidle" });

  const result = await page.evaluate(() => {
    const host = document.createElement("section");
    host.id = "math-renderer-smoke";
    host.className = "markdown-view";
    host.style.width = "760px";
    host.style.padding = "24px";
    host.style.background = "var(--bg-elevated)";
    document.body.append(host);
    const source = [
      "行内计算：$I = \\frac{U}{R} = \\frac{10}{5} = 2\\,\\mathrm{A}$ [S1]",
      "",
      "$$\\int_0^\\infty v^2(t)\\,dt$$",
      "",
      "$$\\begin{bmatrix}-2 & -4\\\\1 & 0\\end{bmatrix}$$",
      "",
      "$$\\begin{aligned}x+y&=1\\\\2x-y&=3\\end{aligned}$$",
      "",
      "```text",
      "$code = \\frac{1}{2}$",
      "```",
      "",
      "| 量 | 公式 |",
      "| --- | --- |",
      "| 电流 | $I=U/R$ |",
      "",
      "$\\input{student.tex}$",
    ].join("\n");
    window.XinzhiUI.renderMarkdown(host, source);
    const summary = {
      formulas: host.querySelectorAll(".math-expression").length,
      displayFormulas: host.querySelectorAll(".math-display").length,
      katexFormulas: host.querySelectorAll(".math-expression .katex").length,
      fallbackFormulas: host.querySelectorAll("[data-latex-fallback='true']").length,
      matrices: host.querySelectorAll(".math-expression .mtable").length,
      citations: host.querySelectorAll(".citation-link").length,
      tables: host.querySelectorAll(".markdown-table").length,
      images: host.querySelectorAll("img").length,
      unsafeExecuted: Boolean(window.__mathUnsafe),
      codeText: host.querySelector("pre code")?.textContent || "",
      text: host.textContent || "",
      displayOverflow: getComputedStyle(host.querySelector(".math-display")).overflowX,
    };
    return summary;
  });

  const expected = {
    formulas: 6,
    displayFormulas: 3,
    katexFormulas: 5,
    fallbackFormulas: 1,
    matrices: 2,
    citations: 1,
    tables: 1,
    images: 0,
    unsafeExecuted: false,
  };
  for (const [key, value] of Object.entries(expected)) {
    if (result[key] !== value) throw new Error(`${key}: expected ${value}, got ${result[key]}`);
  }
  if (!result.codeText.includes("$code = \\frac{1}{2}$")) throw new Error("code block was incorrectly translated");
  if (!result.text.includes("I =") || !result.text.includes("student.tex")) throw new Error("formula text fallback is incomplete");
  if (result.displayOverflow !== "auto") throw new Error(`display overflow: expected auto, got ${result.displayOverflow}`);
  if (pageErrors.length) throw new Error(`page errors: ${pageErrors.join("; ")}`);
  await page.locator("#math-renderer-smoke").screenshot({ path: path.resolve("local_storage/math-renderer-smoke.png") });
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
