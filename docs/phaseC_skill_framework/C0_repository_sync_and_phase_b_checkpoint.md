# Phase C0：Repository Sync 与 Phase B GitHub Checkpoint

## 目标
在 Phase C 开发前，确保 Phase B 成果已经进入 GitHub，并建立干净、可回滚的 Phase C 起点。

## 必须完成
1. 检查 current branch、git status、git log、remote。
2. 确认 Phase B 实现、测试和 closeout 文档是否已 commit。
3. 若尚未 commit：保留所有用户修改，只安全整理 Phase B 相关变更，禁止混入 unrelated changes。
4. push Phase B commit 到 GitHub。
5. 验证远端 SHA。
6. 从完整 Phase B commit 创建 `agentic/phase-c-skill-framework`。
7. push Phase C branch。
8. 生成 `docs/audits/phase_c0_repository_checkpoint.md`，记录 base/local/remote SHA、branch、dirty files 和 push 结果。

## 禁止
- git reset --hard
- git clean -fd
- force push
- 未审查地 git add -A
- Phase B 未远端保存就开始 Phase C

## Commit
`chore(agent): checkpoint phase B before skill framework`

## 结束条件
Phase B 已存在远端，Phase C branch 已 push。完成后立即停止。
