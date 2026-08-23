# Phase F0：Phase E Release Checkpoint

## 目标
确认 Phase E 已真正完成 release，再进入 Evaluation Loop。

## 必须完成
1. 检查 Phase E branch 与 final commit。
2. 确认 `feat(agent): complete phase E experience memory` 或等价 release commit 已 push。
3. 确认 E6/E7 和 migration 已包含。
4. 验证 remote SHA 与 GitHub Actions。
5. 区分 Phase E regression 与 known pre-existing failure。
6. Phase E regression 必须修复。
7. 将已有 6 个历史失败建立 baseline list。
8. 从 Phase E final SHA 创建本地 `agentic/phase-f-evaluation-loop`。

## 交付物
`docs/audits/phase_f0_phase_e_release_checkpoint.md`

## 本阶段不单独 commit
完成后继续 F1。
