# Phase E2：ExperienceRecord 与治理 Contract

## 目标
建立唯一 Experience contract 和治理边界。

## ExperienceRecord 建议字段

```text
experience_id
record_version
experience_type: success | failure | strategy
lifecycle_status
scope
course_id
capability_id
skill_ids
tool_ids
planner_version
plan_signature
input_feature_summary
problem_type
risk_level
strategy_summary
failure_stage
error_codes
verification_result
reflection_result
outcome_metrics
evidence_level
source_trace_ids
source_run_ids
source_eval_ids
confidence
created_at
expires_at
supersedes
conflicts_with
privacy_class
redaction_status
promotion_provenance
```

字段可根据仓库实际调整，但语义必须保留。

## Scope

至少区分：
```text
user_scoped
course_scoped
capability_scoped
global_deidentified
```

默认：
- user-specific 学习经验不跨用户；
- 系统策略经验只允许使用脱敏、聚合、可评测记录。

## Evidence level

沿用：
```text
synthetic_provider_free
offline_real_case
real_provider_test
controlled_canary
production
```

不能把低级别 evidence 静默升级。

## 生命周期

```text
observed
candidate
validated
approved
active
rejected
deprecated
expired
forgotten
```

## 存储策略
优先复用现有持久化基础设施。

如果确实需要新表：
- 只允许 additive migration；
- 不修改现有 Memory 表语义；
- 先给 migration justification；
- 不为 Success/Failure/Strategy 建三张表。

## 隐私
禁止默认保存：
- 完整学生原始答案
- 联系方式/账号
- 不必要的原始聊天
- 未脱敏附件内容

允许保存：
- 抽象错误类型
- 题型特征
- strategy skeleton
- verification/critic code
- 版本/provenance

## 本阶段不 commit
完成后继续 E3。
