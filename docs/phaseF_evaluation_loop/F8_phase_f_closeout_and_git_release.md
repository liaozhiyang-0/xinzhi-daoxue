# Phase F8：Phase F Closeout 与 Git Release

## 目标
完成 Evaluation Loop 收口，把系统从“有评测”升级为“可证据驱动改进”。

## 必须生成
1. `docs/audits/evaluation_loop_phase_f_closeout.md`
2. unified evaluation architecture
3. failure taxonomy
4. failure pattern report
5. improvement proposal report
6. replay comparison report
7. promotion governance report
8. 336-case evaluation summary
9. KEEP / MERGE / FREEZE / REMOVE 更新

## 最终架构
```text
Task
 ↓
Trace
 ↓
Evaluation
 ↓
Failure Attribution
 ↓
Pattern Aggregation
 ↓
Improvement Proposal
 ↓
Offline Replay
 ↓
Regression / Cost / Safety Gate
 ↓
Approval / Promotion
 ↓
Experience Candidate
```

必须保持：
```text
NO automatic code mutation
NO automatic prompt mutation
NO automatic production promotion
```

## 本地完整验证
至少：
```text
git diff --check
ruff
mypy
evaluation targeted tests
planner/skill/reflection/experience regression
336-case validation
full pytest
repo drift
config validation
sensitive-file scan
OpenAPI/frontend checks if contracts changed
```

## 大阶段统一提交
```text
git add <Phase F related files only>
git commit -m "feat(agent): complete phase F evaluation loop"
git push origin agentic/phase-f-evaluation-loop
```

验证 local SHA、remote SHA、GitHub Actions。

## 最终验收
Phase F completed.
Existing Evaluation is the authoritative evaluation owner.
Failures are trace-attributed and pattern-aggregated.
Improvement proposals are evidence-bound and replay-tested.
Promotion is governed and does not mutate production automatically.
Experience Memory receives only governed candidates.
The 336-case suite is integrated into the optimization loop.
Phase F release is pushed to GitHub and CI status is recorded.

## 后续方向
Phase F 后不建议继续增加 G/H/I 控制层。下一阶段转为：
> Iteration 1：基于 Phase F 输出的 Top Failure Patterns，对真实高频问题进行定向工程优化和真实 Provider 评测。
