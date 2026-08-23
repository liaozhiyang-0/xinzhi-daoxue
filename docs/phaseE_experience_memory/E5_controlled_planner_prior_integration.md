# Phase E5：Controlled Planner Prior Integration

## 前置条件
E4 必须证明 Experience retrieval 具有可解释价值，且没有明显污染/泄露/错误策略放大。

## 目标
让 Planner 在极小范围内把 active Experience 当作 prior，而不是命令。

## Planner 可以
- 提升已注册 Skill/Tool/strategy 候选权重；
- 降低曾高频失败策略优先级；
- 调整 plan order；
- 增加 verification requirement；
- 提前选择 safer fallback。

## Planner 不可以
- 选择未注册能力；
- 跳过 evidence/verification；
- 直接复用历史答案；
- 因历史成功跳过当前验证；
- 因单次失败永久封禁能力。

## Influence Contract

```text
baseline_plan
experience_matches
influence_applied
influence_reason
final_candidate_plan
preflight_result
```

## Feature Flag
默认 OFF。

建议：
- `EXPERIENCE_PLANNER_PRIOR_ENABLED=false`
- capability allowlist
- evidence level minimum
- max influence weight
- rollback

具体配置名 Codex 可按仓库风格调整。

## Fail-safe
Experience subsystem timeout / empty / conflict / error / unavailable 时，必须退回无 Experience 的 Planner baseline。

## 本阶段不 commit
完成后继续 E6。
