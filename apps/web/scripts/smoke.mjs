import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = dirname(fileURLToPath(import.meta.url));
const staticRoot = resolve(webRoot, "../../api/app/static/debug");
const reactRoot = resolve(staticRoot, "react");
const sourceRoot = resolve(webRoot, "../src");
const reactIndex = readFileSync(resolve(reactRoot, "index.html"), "utf8");
assert.match(reactIndex, /\/react-assets\/assets\/index-[^"']+\.js/);
assert.match(reactIndex, /\/react-assets\/assets\/index-[^"']+\.css/);
for (const asset of reactIndex.matchAll(/\/react-assets\/assets\/([^"']+)/g)) {
  assert.ok(existsSync(resolve(reactRoot, "assets", asset[1])), `缺少 React 构建产物：${asset[1]}`);
}

const app = readFileSync(resolve(sourceRoot, "app/App.tsx"), "utf8");
const composer = readFileSync(resolve(sourceRoot, "features/chat/Composer.tsx"), "utf8");
const transport = readFileSync(resolve(sourceRoot, "task-transport.ts"), "utf8");
const contracts = readFileSync(resolve(sourceRoot, "workspace-contracts.ts"), "utf8");
assert.match(app, /ScenarioPicker/);
assert.match(app, /WorkspaceContextPane/);
assert.match(app, /getTaskRuntimeControls/);
assert.match(composer, /responseDepth/);
assert.match(composer, /composer-resize-handle/);
assert.doesNotMatch(composer, /更多选项|已有思路|学生答案/);
assert.match(transport, /new EventSource/);
assert.match(transport, /reconnectPollTimer/);
assert.match(contracts, /buildStudentTaskPayload/);

for (const file of [
  "student.html",
  "student.js",
  "workspace.html",
  "workspace.js",
  "workspace-materials.js",
  "workspace-task-transport.js",
  "workspace-v2.css",
]) {
  assert.equal(existsSync(resolve(staticRoot, file)), false, `旧 Workspace 资源仍存在：${file}`);
}

console.log("web smoke passed: React Workspace is the only student workspace implementation");
