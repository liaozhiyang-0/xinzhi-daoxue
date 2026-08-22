# Phase F5：Offline Replay 与 Counterfactual Evaluation

## Replay contract

`ReplayResult` 保存 proposal/baseline/candidate、case count、improved/unchanged/degraded、critical regressions、score/failure/latency/token/cost/safety deltas、evidence level、condition drift 和 gate reasons。

`OfflineReplayService` 要求 baseline/candidate 使用相同 case set，并检查：

- evidence level；
- task family/course；
- planner/plan version；
- skill/tool versions；
- model/provider version；
- reflection version。

drift 不会被隐藏，而是进入 result 并阻止 GO。默认 gate 不接受 critical regression、failure-rate 增加、safety 下降或超过 20% 的成本增加；阈值是 policy contract，不为某个 Proposal 临时降低。

Baseline 与 candidate 的 scorer、case、数据快照和版本条件必须由调用方保持一致，无法固定的部分必须记录 drift。Replay 不修改 runner 或评分器，也不只选择改善样例。

## F5 结论

候选可以做公平、可比较的离线 replay；F5 完成。
