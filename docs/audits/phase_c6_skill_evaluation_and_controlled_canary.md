# Phase C6 Skill Evaluation 与 Controlled Canary 审计

## 结论

Phase C6 已形成 provider-free 的结构性评测链，当前结果为 `GO`，但该结果只证明
Skill 选择、策略拒绝、既有 Handler 绑定、计划往返和 checkpoint 版本保持的结构兼容性，
不代表真实 Provider 的答案质量或生产稳定性。Controlled Canary 保持默认关闭，只有
显式 allowlist、评测 `GO`、rollback 配置和低风险范围同时满足时才允许产生“可批准”决策。
本阶段没有启用线上接管，也没有新增 Runtime、Agent、Reflection 或 SkillMemory。

## 控制链

```text
SkillEvaluationCase
  ↓
SkillRetriever → authoritative SkillRegistry → SkillPolicy
  ↓
SkillBindingService → existing RuntimeHandlerRegistry
  ↓
CanonicalPlanAdapter → existing Runtime Kernel / Tool / Worker / RAG
  ↓
plan compatibility + checkpoint version check → evaluation report
  ↓
SkillControlledCanary (default OFF, allowlist, rollback)
```

评测服务复用 C1-C5 已有 Registry、Retriever、Policy、Binding 和 Canonical Plan adapter，
没有另建评测专用注册表或执行路径。

## 评测指标

每个 case 记录 selected/approved/rejected skill、拒绝码和绑定 Handler；报告汇总：

| 类别 | 指标 |
| --- | --- |
| selection | valid、empty、fallback、invalid/unregistered |
| policy | prerequisite rejection、policy rejection |
| binding | binding success、handler mismatch、plan compatibility |
| runtime boundary | runtime failure、checkpoint/resume compatibility |
| cost | latency、token count、estimated cost |
| outcome | task outcome quality 仅在真实 Provider 证据层填写 |
| safety | rollback integrity |

## Case 覆盖

| Case | Evidence level | 结果 |
| --- | --- | --- |
| CT/KCL，既有 equation solver Tool | `synthetic_provider_free` | selected、bound、plan compatible |
| Knowledge worker 不可用 | `synthetic_provider_free` | fail-closed rejection |
| Teaching 复用 CT 前置技能 | `synthetic_provider_free` | prerequisite chain 可绑定 |
| Research 缺少 prerequisite/worker | `synthetic_provider_free` | fail-closed rejection |
| general fallback | `synthetic_provider_free` | 无 Skill 时显式 fallback |
| 未注册 Skill 注入 | `synthetic_provider_free` | `unregistered_skill` rejection |
| 已注册但 Handler 不可用 | `synthetic_provider_free` | `no_existing_runtime_handler` rejection |
| checkpointed CT skill version | `synthetic_provider_free` | resume version 保持 |

当前本地验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q --no-cov apps/api/tests/test_skill_evaluation.py
.\.venv\Scripts\ruff.exe check apps/api/app/services/skill_evaluation.py apps/api/tests/test_skill_evaluation.py
```

结果：`3 passed`，Ruff 通过。测试不调用 Provider，因此 `task_outcome_quality` 不作质量结论。

## Controlled Canary 决策

- 默认配置 `enabled=false`，结果为 `disabled/canary_default_off`。
- 启用时必须是 `controlled_canary` evidence level、评测 `GO`、非空 allowlist、rollback
  开启，且 `automatic_expansion=false`。
- rollback 只返回非活动的 rolled-back decision，不修改 Runtime、Checkpoint 或 Agent 状态。
- 当前只验证了显式 allowlist 下的政策决策，未启用生产流量，也未扩大范围。

## 边界结论

KEEP 既有 Runtime Kernel、Handler/Tool/Worker/RAG 和 Academic Solver；MERGE 的范围仅为
评测链对已有 Skill 控制面的统一观测。FREEZE Reflection、SkillMemory、公共 Agent 扩张和
自动 canary 扩容，直到另行立项。
