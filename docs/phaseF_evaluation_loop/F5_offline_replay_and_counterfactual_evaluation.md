# Phase F5：Offline Replay 与 Counterfactual Evaluation

## 目标
在任何 Proposal promotion 前，证明候选变化相对 baseline 有净收益。

## Replay 原则
Baseline 和 Candidate 尽可能保持：
- same cases
- same dataset snapshot
- same model/provider version
- same tool/RAG index version
- same scoring
- same random/temperature policy
- same cost accounting

无法固定时记录 drift。

## ReplayResult
至少：
```text
proposal_id
baseline_id
candidate_id
case_count
improved
unchanged
degraded
critical_regressions
score_delta
failure_rate_delta
latency_delta
token_delta
cost_delta
safety_delta
evidence_level
```

## 禁止
- 不只跑“能体现改善”的样例；
- 不改变评分器迎合 Proposal；
- 不隐藏 degradation cases；
- synthetic replay 不得宣称 production quality。

## 本阶段不 commit
完成后继续 F6。
