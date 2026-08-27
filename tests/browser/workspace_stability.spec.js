"use strict";

// The acceptance runner owns the isolated FastAPI server and browser lifecycle.
// Keep this thin entry point so CI and local checks have a stable tests/browser path.
const { spawnSync } = require("node:child_process");
const path = require("node:path");

const root = path.resolve(__dirname, "..", "..");
const result = spawnSync(
  process.execPath,
  [path.join(root, "scripts", "run_web_ui_browser_acceptance.js")],
  { cwd: root, stdio: "inherit", env: process.env, windowsHide: true },
);

process.exit(result.status ?? 1);
