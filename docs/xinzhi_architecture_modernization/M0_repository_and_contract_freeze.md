# M0：Repository / Contract Freeze

## 目标
在迁移前冻结行为边界，不跑完整 336 Benchmark。

## 记录
- current branch / HEAD SHA / git status
- public API routes
- OpenAPI snapshot
- SSE event names/order
- Task status lifecycle
- DB migration head
- generated api-types checksum
- existing frontend smoke behavior

## 建议分支
`refactor/platform-modernization`

## 最小迁移前回归
- frontend typecheck/build/smoke
- task create/complete
- SSE order
- session continuity
- attachment upload
- Markdown/LaTeX render smoke
- learning action
- retry/resume fixtures
- API contract generation/drift

输出：`docs/modernization/m0_contract_freeze.md`

若基础主链已不稳定，先修 blocking baseline 再继续。
本阶段不 commit。
