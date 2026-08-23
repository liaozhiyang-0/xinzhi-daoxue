# Phase D7：Phase D Closeout 与 Git Release

## 目标
完成整个 Phase D 后统一验证、统一提交、统一 push。

## 必须完成
1. 生成 `docs/audits/reflection_phase_d_closeout.md`。
2. 更新架构文档和最终控制流图。
3. 更新 KEEP / MERGE / FREEZE / REMOVE。
4. 明确 Critic 默认状态、允许 Reflection 的 capability、revision max、canary、evidence level。
5. 确认没有新 public Agent、第二 Runtime、第二 checkpoint、Experience Memory、自动 promotion、Critic 递归。
6. 排除 unrelated changes。

## 本地完整验证
```text
git diff --check
ruff
mypy
targeted reflection tests
skill/planner regression tests
full pytest
repo drift check
config validation
API/OpenAPI drift where affected
frontend typecheck/build if contract changed
```

## 大阶段统一提交
```text
git add <Phase D related files only>
git commit -m "feat(agent): complete phase D reflection loop"
git push origin agentic/phase-d-reflection
```

验证 local SHA、remote SHA、GitHub Actions。

## CI
CI 必须 PASS。若因 Phase D 回归失败，做最小修复，可追加同属 Phase D release 的 `fix(ci)` commit；不得开始 Phase E。

## 最终交付物
Phase D closeout audit、Reflection architecture doc、evaluation report、canary decision、final SHA/CI、Phase E insertion points。

## 结束条件
```text
Phase D completed.
ReflectionPolicy is integrated.
Critic is bounded and non-public.
Revision is limited and re-verified.
Deterministic/domain verification remains authoritative.
Runtime Kernel remains unchanged.
No Experience Memory was implemented.
Phase D release is pushed to GitHub and CI passes.
Phase E has NOT started.
```
