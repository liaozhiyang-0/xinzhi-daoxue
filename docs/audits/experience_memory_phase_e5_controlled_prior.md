# Phase E5：Controlled Planner Prior Integration

## Feature flag

配置默认关闭：

```text
EXPERIENCE_PLANNER_PRIOR_ENABLED=false
EXPERIENCE_PLANNER_CAPABILITY_ALLOWLIST=
EXPERIENCE_PLANNER_MINIMUM_EVIDENCE=offline_real_case
EXPERIENCE_PLANNER_MAX_INFLUENCE_WEIGHT=0.15
```

实现提供 `ExperiencePlannerPrior.from_settings`，只有 operator 显式打开、capability 命中 allowlist、evidence 达标且当前 preflight 已成功时，才允许产生有限 prior。即使开启，也只能在 baseline 的已注册 skill 候选中做有限重排，并强制 `verification_required=true`；不能增加未注册 target、跳过验证或复用历史答案。

## Influence contract

`ExperienceInfluence` 固定记录：

- `baseline_plan`
- `experience_matches`
- `influence_applied`
- `influence_reason`
- `final_candidate_plan`
- `preflight_result`

检索、配置、冲突或策略异常均返回 baseline，并写出 fallback reason。单次 Failure 不形成永久 blacklist；历史 Success 也不能跳过当前 Runtime verification。

## E5 状态

`PASS (controlled, default OFF)`。受控 prior contract 与 fail-safe 已完成；默认业务执行路径保持不变，未开启 Planner takeover。
