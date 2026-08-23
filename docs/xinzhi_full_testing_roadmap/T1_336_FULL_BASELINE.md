# T1：336-case 当前架构全量 Baseline

## 目标
第一次正式测量当前完整 Agent 架构的整体表现。本阶段只测试，不优化。

## 运行范围
完整运行 336 cases，不得因失败过多提前停止。

## 每题记录
case_id、course、difficulty、input_mode、route、planner、selected skills/tools、RAG、provider/model、reflection、verification、final score、failure stage/code、latency、tokens、cost。

## 输出维度
Overall、Course、Difficulty、Input、Architecture Failure Stage。

## 禁止
不得修 Prompt、改 Skill、改 Planner、为失败题写特殊规则。只允许修 Benchmark 本身明确 bug。

## 输出
- `evaluation/reports/t1_336_baseline/`
- `docs/testing/t1_336_full_baseline.md`

作为 `Benchmark V1`。

## 提交
`test(eval): establish 336-case benchmark V1`
