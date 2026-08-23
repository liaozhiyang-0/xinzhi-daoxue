const fs = require("fs");
const path = require("path");
const katex = require(path.resolve(__dirname, "..", "apps", "api", "app", "static", "debug", "vendor", "katex", "katex.min.js"));

const input = process.argv[2];
const output = process.argv[3];
if (!input || !output) {
  process.stderr.write("usage: node render_katex_samples.js INPUT_JSONL OUTPUT_JSONL\n");
  process.exit(2);
}
const rows = fs.readFileSync(input, "utf8").split(/\r?\n/u).filter(Boolean);
const rendered = [];
for (const line of rows) {
  const item = JSON.parse(line);
  const displayMode = item.delimiter === "display" || item.delimiter === "display_dollar";
  try {
    katex.renderToString(item.body, {
      displayMode,
      throwOnError: true,
      strict: "warn",
      trust: false,
      output: "htmlAndMathml",
      maxExpand: 1000,
      maxSize: 20,
    });
    rendered.push({ formula_hash: item.hash, status: "passed", version: katex.version });
  } catch (error) {
    rendered.push({
      formula_hash: item.hash,
      status: "failed",
      version: katex.version,
      error: error instanceof Error ? error.message : String(error),
    });
  }
}
fs.writeFileSync(output, rendered.map((item) => JSON.stringify(item)).join("\n") + (rendered.length ? "\n" : ""), "utf8");
