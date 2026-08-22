# Phase E2：ExperienceRecord 与治理 Contract

## 设计结论

Experience Memory 使用一个 `ExperienceRecord` contract 和一个 `experience_records` 表。`success`、`failure`、`strategy` 是同一记录模型上的类型投影，不建立三套事实源；既有 `MemoryModel` / `MemoryService` 保持独立。

```text
ExperienceRecord
  ├─ identity: experience_id / record_version
  ├─ type & lifecycle: success|failure|strategy / observed..forgotten
  ├─ scope: user|course|capability|global_deidentified
  ├─ execution binding: planner / plan / skill(+version) / tool(+version) / model
  ├─ feature & outcome: input summary / problem / risk / strategy / failure / metrics
  ├─ evidence: trace / run / eval IDs + evidence level + verification/reflection
  └─ governance: privacy / redaction / promotion / expiry / supersede / conflict
```

### 生命周期

```text
observed → candidate → validated → approved → active
                  ├→ rejected
active ───────────┼→ deprecated
active ───────────┼→ expired
active ───────────└→ forgotten
```

所有创建入口强制从 `candidate` 开始；没有 source trace/run/eval 不能写入。`active` 是唯一可被 Retriever 返回的状态。

## Scope / privacy matrix

| Scope | Owner | 允许检索范围 | 最低隐私类别 | 备注 |
| --- | --- | --- | --- | --- |
| `user_scoped` | 必须有 `scope_owner_id` | 同一 user | `user_private` | 永不跨用户；forget 按 owner 软删除为 forgotten |
| `course_scoped` | 无 user owner | 同一 course | `course_deidentified` | 只能保存脱敏结构化经验 |
| `capability_scoped` | 无 user owner | 同一 capability | `capability_deidentified` | 只绑定已注册能力 |
| `global_deidentified` | 无 owner | 全局 | `global_deidentified` | 不得含用户可识别内容 |

## Evidence level

`synthetic_provider_free`、`offline_real_case`、`real_provider_test`、`controlled_canary`、`production` 在 contract 中保持独立，不可静默升级。Provider-free/synthetic 记录可用于结构测试和 replay，但不能作为 production Success/Strategy 激活依据。

## 存储与兼容性

- 新增仅一个 additive migration `20260823_0022_experience_memory`。
- 不修改 `memories` 表，不改变 MemoryService 的 active、冲突、delete/forget 语义。
- 不新增 API，不修改 Task/AgentRequest/Runtime Plan/AgentResult/RAG/Tool public contract。
- Runtime checkpoint、Session context、Learning State 仍由原 owner 管理；Experience 仅保存 source IDs 和脱敏摘要。

## E2 状态

`PASS`。Contract、scope、evidence、lifecycle、privacy 和 additive storage boundary 已确定。
