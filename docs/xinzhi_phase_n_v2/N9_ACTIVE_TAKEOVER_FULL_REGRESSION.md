# N9：Active Takeover + Full Regression

## 目标

Planner 成为默认生产控制面。

## Active 条件

必须先满足：
- N5 controlled 稳定；
- N6 old routing 退出；
- N7 legacy invocation = 0；
- N8 presentation parity PASS。

## 回归

### Phase M 必保留

Frontend：
- typecheck
- math:check（31+）
- demo:check
- smoke
- build

Backend：
- 六案例 matrix
- AC-01 image route
- TP-01 waiting_review
- unified web UI
- SSE
- checkpoint/resume

### Architecture

- route mutation after plan = 0
- OverallRouter production call = 0
- legacy runtime invocation = 0
- fixed agent route dependency = 0

### Full suite

重新跑全量 pytest。

如果仍失败：
必须区分：
- Phase N regression
- unresolved baseline drift
- unrelated current-worktree issue

不得笼统宣称 PASS。

本阶段不 commit。
