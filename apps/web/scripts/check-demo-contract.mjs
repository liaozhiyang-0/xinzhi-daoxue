import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const scenarios = readFileSync(resolve(process.cwd(), "src/demo/scenarios.ts"), "utf8");
const requiredIds = [
  "faculty_course_copilot_v1",
  "assessment_diagnosis_v1",
  "student_learning_path_v1",
  "research_frontier_radar_v1",
  "department_knowledge_governance_v1",
  "academic_visual_problem_solver_v1",
];
assert.equal((scenarios.match(/id: "[^"]+"/g) || []).filter((value) => requiredIds.some((id) => value.includes(id))).length, 6);
for (const id of requiredIds) assert.ok(scenarios.includes(`id: "${id}"`), `缺少示范场景：${id}`);
assert.match(scenarios, /runtimeScenarioId: null/);
assert.match(scenarios, /analog-opamp\.jpg/);
assert.match(scenarios, /任务规划/);
assert.match(scenarios, /证据治理/);
assert.match(scenarios, /边界验证/);
console.log("demo contract passed: six real scenario entries");
