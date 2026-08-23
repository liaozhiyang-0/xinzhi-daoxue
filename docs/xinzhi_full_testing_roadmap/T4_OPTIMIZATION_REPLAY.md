# T4：定向优化 Replay / Counterfactual Test

## 目标
验证每个修改是否真的解决目标问题。

流程：
Targeted Baseline → Minimal Change → Targeted Replay → Regression → Accept/Reject。

## 每次修改记录
proposal_id、target_pattern、files_changed、baseline score、candidate score、score delta、new failures、latency delta、cost delta。

## Gate
target improvement > 0；critical regression = 0；global degradation within threshold；latency/cost acceptable。

## 优化优先顺序
1. deterministic Tool/parser
2. Skill metadata/selection
3. RAG policy
4. verification
5. prompt
6. Planner
7. model upgrade

最多 3 rounds。

## 提交
`feat(agent): complete targeted optimization replay`
