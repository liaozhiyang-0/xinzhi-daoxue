# Phase F：Evaluation Loop Closeout

## 统一架构

```text
Task
 ↓
Trace / Model metadata / Planner-Skill-Reflection-Experience lineage
 ↓
Existing EvaluationCase + EvaluationRunner + EvaluationScorer + SuiteReport
 ↓
EvaluationRecord adapter
 ↓
Failure Attribution
 ↓
Failure Pattern Aggregation
 ↓
ImprovementProposal (candidate only)
 ↓
Offline Replay
 ↓
Regression / Cost / Safety Gate
 ↓
Approval / PromotionDecision
 ↓
Experience candidate (Phase E lifecycle)
```

## KEEP / MERGE / FREEZE / REMOVE 更新

### KEEP

- Existing EvaluationCase/Runner/Scorer/SuiteReport 作为唯一评估 owner；
- Task/Runtime/Planner/Skill/Reflection/Experience trace 的既有 owner；
- bounded TraceStore/ModelTracer metadata；
- Phase E candidate → validated → approved → active governance；
- model-evaluation workflow 的 offline/live evidence separation。

### MERGE

- 旧评估结果通过 `EvaluationRecordAdapter` 进入统一 evidence contract；
- legacy FailureStage/error code 通过单一 Phase F taxonomy 映射；
- single failure 通过 `FailurePatternAggregator` 聚合；
- Proposal replay 和 PromotionDecision 统一连接 Experience candidate。

### FREEZE

- 自动改 Prompt/代码/Skill/Planner/Router/Tool policy；
- synthetic evidence 的生产质量结论；
- transient timeout/provider/fixture failure 的长期策略泛化；
- 新 public Agent、第二 Runtime、第二 Evaluation Framework。

### REMOVE

- Phase F 未删除现有生产模块；
- 删除的是设计层面的隐式路径：无 evidence 的归因、隐藏 degradation、评分器迎合 Proposal、直接 active promotion。

## 验收状态

已完成：

- authoritative Evaluation owner；
- EvaluationRecord / FailureRecord / Failure taxonomy；
- deterministic attribution 和 pattern aggregation；
- evidence-bound ImprovementProposal；
- fair offline replay 和 regression/cost/safety gate；
- governed PromotionDecision 和 Experience candidate bridge；
- 公开 84-case catalog validation、6 个历史失败 evidence import；
- 无自动代码、Prompt、生产配置或数据库 promotion。

## 本地验证记录

| 检查 | 结果 |
| --- | --- |
| Phase F targeted tests | PASS，4 passed |
| Evaluation/Planner/Skill/Reflection/Experience compatibility tests | PASS，46 passed |
| public evaluation catalog | PASS，84 cases validated |
| full pytest | `1929 passed, 15 skipped, 6 failed`；6 个为既有 dirty-worktree baseline |
| targeted Ruff | PASS |
| targeted Mypy | PASS |
| full Ruff | 5 个既有 `test_unified_web_ui.py` E501，Phase F 文件无错误 |
| full Mypy | 3 个既有 `rag_providers.py` / `academic_solver_service.py` 错误，Phase F 文件无错误 |
| repo drift | PASS |
| config validation | PASS |
| sensitive-file scan | PASS |
| Docker Compose config | PASS |

Full pytest 的 6 个失败为 commercial scenario coverage、offline embedding fixture、external source count、revoked-material encoding 和 demo scenario count，均未触及 Phase F 文件。

本阶段没有 public API/GraphQL/TypeScript contract 变化，因此未重复执行 OpenAPI/frontend contract drift；Phase E CI 已记录该链路 PASS。

条件项：

- 私有 balanced 336 catalog 未在当前工作区，不能伪造为已执行；
- real Provider / controlled canary / production evidence 未执行；
- 因此真实质量提升保持未声明，最终证据等级为 `STRUCTURAL_GO / CONDITIONAL_GO`。

## 后续方向

Phase F 后不增加新的控制层。下一步应针对真实高频 Failure Pattern 进行定向工程修复和真实 Provider 评测，再通过同一 Replay/Governance loop 验证。
