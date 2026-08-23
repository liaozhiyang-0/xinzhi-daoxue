import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const source = readFileSync(resolve(process.cwd(), "src/math/fixtures.ts"), "utf8");
const fixtures = [...source.matchAll(/String\.raw`/g)];
assert.ok(fixtures.length >= 30, `公式 fixture 数量不足：${fixtures.length}`);
for (const required of ["Z_C", "y(t)", "i_C", "\\partial", "X[k]", "bmatrix", "cases", "aligned", "angle30"]) {
  assert.ok(source.includes(required), `缺少公式 fixture：${required}`);
}
console.log(`math fixtures passed: ${fixtures.length}`);
