# Phase E4：ExperienceRetriever 与 Planner Shadow

## 检索边界

`ExperienceRetriever` 先做确定性过滤，再评分并限制 top-k。过滤条件为：`active`、未过期、scope compatible、user owner compatible、planner version compatible、global 记录已脱敏；冲突记录不静默选择。排序特征依次覆盖 capability/course/problem type、skill/tool overlap、risk 和 failure warning。

返回 `ExperienceMatch`，只包含 experience ID、type、score、match reasons、strategy skeleton/failure warning、evidence、confidence、scope 和版本，不返回历史答案。

```text
CanonicalGoal + course/capability/problem/skills/risk/budget/version
                              ↓
             deterministic filter + bounded scoring
                              ↓
                     ExperienceMatch[top-k]
```

## Planner shadow

```text
baseline Planner plan ───────────────┐
                                     ├─ ExperienceInfluence (shadow)
baseline + Retriever prior ──────────┘
```

`ExperiencePlannerPrior.shadow` 同时保留 `baseline_plan`、`experience_matches`、`influence_applied`、`influence_reason`、`final_candidate_plan` 和 `preflight_result`。默认 `influence_applied=false`，真实 Runtime 继续使用 baseline；检索失败、冲突、空结果和超时都回到 baseline。

禁止经验指定未注册 Skill/Tool、覆盖 TaskRouter preflight、绕过 SkillPolicy、跨用户检索或直接复用历史答案。

## E4 状态

`PASS (shadow-only)`。确定性检索、top-k、scope/version 隔离、conflict exclusion 和 Planner shadow contract 已落地；尚未改变默认真实 plan。
