# M9：Closeout、统一 Git Release 与恢复 Benchmark

## 最终验证

Frontend：
React default workspace、typecheck/build/smoke、OpenAPI types、SSE、attachments、learning。

Backend：
single RuntimeTaskEngine、DAG、API contract、Task lifecycle、SSE order、checkpoint/resume、Planner/Skill、Reflection/Experience、RAG/Tool。

Structure：
- services 不再是默认业务落点；
- application/capability/runtime/infrastructure/governance owner 清晰；
- 无第二 runtime/planner/memory/evaluation；
- React 不复制后端业务逻辑；
- generated API types 为唯一 TS contract source。

## Closeout
生成 `docs/history/frontend-react/modernization/phase_m_closeout.md`：
before/after structure、moved files、remaining compatibility、workspace.js before/after、services before/after、tests、known failures、deferred cleanup、rollback。

## Git
整个 Phase M 现在才统一：
```text
git status
git diff --check
git add <Phase M related files only>
git commit -m "refactor(platform): complete frontend and backend modernization"
git push origin refactor/platform-modernization
```
验证 local SHA、remote SHA、GitHub Actions。
不自动 merge main。

## 恢复测试
Phase M 完成后不从 T2/T3 接着跑，而重新：
```text
Phase M release
→ T0 Baseline Freeze
→ T1 336 Full Baseline
→ T2 Failure Attribution
→ T3-T9
```

完成后停止，不自动开始 T0。
