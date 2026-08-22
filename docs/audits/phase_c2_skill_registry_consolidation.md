# Phase C2 Skill Registry Consolidation

## 结论

`apps/api/app/services/skill_registry.py::SkillRegistry` 仍是系统唯一
authoritative registry。没有新增 `SkillRegistry`、数据库表、Provider 调用或
Planner 责任。

现有 `config/skills/*.yaml` 继续是 manifest 来源。加载器从目录发现 catalog，
所以未来课程/领域只需增加兼容 YAML，而不需要复制注册表；当前实际注册：

- CT：10 个既有电路 Skill；
- AE：10 个既有模拟电子 Skill；
- DE：10 个既有数字电子 Skill；
- RESEARCH：query planning、evidence review、evidence synthesis；
- KNOWLEDGE：query rewrite、grounded explanation。

Research/Knowledge 条目只声明现有 worker、证据和校验要求，不声明新的 Agent
ID，也不意味着它们已经被 Planner 或 Runtime 执行。

## Registry contract

| 能力 | 实现 |
|---|---|
| identity | `skill_id` 全局唯一；旧 CT/AE/DE IDs 原样保留；未知 ID fail-closed |
| version | catalog 和 item 的 `version` 必须匹配；`resolve(id, version=...)` 校验版本 |
| status | `active` / `experimental` / `frozen` / `deprecated`，默认 `active` |
| load | YAML 目录发现、Pydantic 结构校验、课程/领域问题类型校验 |
| prerequisite | 加载时校验 ID、跨域边界和 DAG；运行时 `validate_prerequisites` 返回缺失项 |
| query | `get`、`resolve`、`list_for_course`、`list`（course/status/domain filter） |
| serialization | `serialize(skill_id)` 输出版本化 metadata；不输出执行状态 |
| compatibility | `SkillMappingResult`、`SolutionPacket` 和已有教学链路继续使用 stable IDs |

## Fail-closed rules

启动时拒绝：重复 ID、catalog/item 版本不一致、无效版本格式、未知能力、无效
问题类型、缺失先修 Skill、跨 course 先修或循环先修。查询时未知 ID、版本不匹配
和未加载 catalog 不会被模糊创建或自动补全。

## Scope boundary

```text
SkillRegistry  -> identity, metadata, version, prerequisite DAG
SkillRetriever -> candidate ranking and bounded context match (C3)
SkillPolicy    -> eligibility/risk/evidence/budget decision (C3)
Planner        -> canonical plan selection (C4)
Runtime        -> existing handler/tool/worker/RAG execution (C5)
```

Registry 不执行 Provider、不生成 Planner、不保存 outcome memory、不拥有
checkpoint/lifecycle，也不承担 SkillMemory、Reflection 或 public Agent 语义。

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q --no-cov `
  apps/api/tests/test_skill_registry.py `
  apps/api/tests/test_skill_contract_phase_c.py `
  apps/api/tests/test_solution_packet_adapter.py `
  apps/api/tests/test_course_asset_audit.py
```

Result: `18 passed, 2 warnings`.
