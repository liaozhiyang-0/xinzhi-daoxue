import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const webRoot = dirname(fileURLToPath(import.meta.url));
const staticRoot = resolve(webRoot, "../../api/app/static/debug");
const generatedRoot = resolve(staticRoot, "ts");
const reactRoot = resolve(staticRoot, "react");
const workspaceSource = readFileSync(resolve(staticRoot, "workspace.js"), "utf8");

assert.match(workspaceSource, /\.\/ts\/materials\.js/);
assert.match(workspaceSource, /\.\/ts\/task-transport\.js/);
assert.match(workspaceSource, /\.\/ts\/workspace-contracts\.js/);

for (const file of ["materials.js", "task-transport.js"]) {
  assert.ok(existsSync(resolve(generatedRoot, file)), `缺少构建产物：${file}`);
}
assert.ok(existsSync(resolve(generatedRoot, "workspace-contracts.js")));
const reactIndex = readFileSync(resolve(reactRoot, "index.html"), "utf8");
assert.match(reactIndex, /\/react-assets\//);
assert.match(reactIndex, /assets\//);

const materials = await import(pathToFileURL(resolve(generatedRoot, "materials.js")));
const transport = await import(pathToFileURL(resolve(generatedRoot, "task-transport.js")));
const contracts = await import(pathToFileURL(resolve(generatedRoot, "workspace-contracts.js")));
assert.equal(typeof materials.createMaterialManager, "function");
assert.equal(typeof transport.createTaskTransport, "function");
assert.equal(typeof contracts.buildStudentTaskPayload, "function");

const changes = [];
const materialManager = materials.createMaterialManager({
  api: async () => ({}),
  maxFiles: 2,
  onChanged: (files) => changes.push(files),
});
const note = new File(["hello"], "notes.txt", { type: "text/plain" });
materialManager.append([note, note]);
assert.equal(materialManager.selected().length, 1);
assert.equal(changes.at(-1).length, 1);
assert.throws(
  () => materialManager.append([new File(["x"], "bad.exe", { type: "application/octet-stream" })]),
  /暂不支持材料类型/,
);

const payload = contracts.buildStudentTaskPayload({
  sessionId: "session-1",
  userId: "student-1",
  userRole: "student",
  courseId: "AUTO",
  intent: "unknown",
  scenarioId: null,
  canonicalInput: { text: "题目" },
  materials: [{
    uploaded: { id: "file-1", filename: "notes.txt", content_type: "text/plain" },
    extractedText: "材料",
    originalType: "text/plain",
  }],
  responseDepth: "standard",
  teachingMode: "direct_answer",
  studentAttempt: "",
  learningFollowUp: { source_task_id: "task-1", action: "continue" },
  requestId: "request-1",
});
assert.equal(payload.attachments[0].file_id, "file-1");
assert.equal(payload.options.source_task_id, "task-1");
assert.equal(payload.options.learning_action, "continue");

const taskTransport = transport.createTaskTransport({
  api: async () => ({}),
  ownedTaskUrl: (id) => `/api/v1/tasks/${id}`,
  state: { liveProcessSteps: new Map(), activeTaskWait: null },
  addMessage: () => {},
  selectContextTab: () => {},
  liveProgressData: () => ({}),
  updateLiveProgress: () => {},
  refreshRuntimeTaskControls: () => {},
  renderLongWaitNotice: () => {},
});
assert.equal(typeof taskTransport.waitForTask, "function");

console.log("web smoke passed: TS boundary modules are built and referenced by workspace.js");
