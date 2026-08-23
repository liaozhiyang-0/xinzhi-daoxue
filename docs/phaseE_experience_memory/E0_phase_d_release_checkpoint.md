# Phase E0：Phase D Release Checkpoint

## 目标
确认 Phase D 已完成大阶段 release，再开始 Experience Memory。

## 必须完成
1. 检查 Phase D branch / final commit。
2. 确认 `feat(agent): complete phase D reflection loop` 或等价 release commit 已 push。
3. 核对 Phase D closeout、D6 report 是否包含在远端 commit。
4. 检查 GitHub Actions。
5. 若 CI 失败，区分 Phase D regression 与 pre-existing unrelated issue。
6. Phase D regression 必须先修复。
7. 若存在确认无关的历史失败，记录 evidence，不允许静默忽略。
8. 从 Phase D final SHA 创建本地 `agentic/phase-e-experience-memory`。
9. E0-E6 不逐阶段 commit。

## 交付物
`docs/audits/phase_e0_phase_d_release_checkpoint.md`

记录：
- Phase D SHA
- remote SHA
- CI result
- known unrelated failures
- Phase E base SHA
- branch

## 结束条件
Phase D release 状态明确且可回滚，方可进入 E1。
