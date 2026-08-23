# Phase D0：Phase C Release Checkpoint

## 目标
Phase D 开始前确认 Phase C 已真正完成远端发布和 CI 验证。

## 必须完成
1. 检查 Phase C branch 和工作树。
2. 确认 Phase C final commit 已包含 C6/C7 全部修改。
3. 若 final commit 尚未 push，先完成 Phase C 大阶段提交与 push。
4. 验证 remote SHA。
5. 检查 GitHub Actions backend-ci / frontend。
6. 若 CI 失败，先做最小修复并重新通过。
7. 从 Phase C final SHA 创建本地 `agentic/phase-d-reflection`。
8. D0-D6 不逐步提交。

## 交付物
本地生成 `docs/audits/phase_d0_phase_c_release_checkpoint.md`，记录 Phase C local/remote SHA、CI、Phase D base SHA、branch。

## 结束条件
只有 Phase C final remote + CI PASS 后才能继续 D1。
