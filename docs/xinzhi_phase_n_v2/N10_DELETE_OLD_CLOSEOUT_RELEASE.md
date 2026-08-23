# N10：删除旧路径、文档收口与 Git Release

## 删除候选

仅在 usage/importer/regression 条件满足后删除：

- OverallRoutingService production path
- legacy-runtime execution
- fixed Agent workflow routing
- obsolete route reconciliation
- duplicate context rebuild
- IntentPlanCompiler normal-production path
- duplicate fallback router
- obsolete feature flags
- zero-importer compatibility adapters

## 保留

- old checkpoint reader（如仍需）
- migration history
- frozen audit baselines
- necessary legacy API adapter
- safety / evidence / permission / verification
- Phase M frontend display standard
- MarkdownRenderer / math fixtures
- six scenario metadata

## 文档同步

必须更新：
README
developer_code_navigation
architecture guide
runtime flow
Agent/Skill docs
six scenario guide

文档不得再写：
“Overall Router retired”但代码仍调用；
“Legacy removed”但 runtime 仍可执行。

## 最终架构

Unified Ingress
→ GoalContract
→ Preflight
→ Planner
→ Capability + Skill
→ CanonicalPlan
→ Runtime
→ Verification
→ Reflection
→ Governance/Human Review
→ Result/SSE/React

## 最终验证

Ruff
Mypy
dependency constraints
runtime/API/SSE
checkpoint/resume
Planner/Skill
Reflection/Experience
six Demo
math fixtures
frontend typecheck/build/smoke
full pytest
repo drift
config validation
legacy telemetry

## Git

```text
git add <Phase N files only>
git commit -m "refactor(agent): converge on planner-driven control plane"
git push origin agentic/planner-control-plane
```

验证 remote SHA + CI。

完成后停止。

下一步重新启动：
T0 Baseline Freeze → T1 336 Full Benchmark → T2 Failure Analysis。
