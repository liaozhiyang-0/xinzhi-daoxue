# 芯智导学完整测试路线总规划

## 1. 总目标

项目已经完成 Planner、Skill、Reflection、Experience Memory、Evaluation Loop 等架构阶段，后续测试不再围绕“模块是否存在”，而围绕：

> 系统是否真的能稳定、准确、可解释地完成电子信息课程群真实任务。

完整测试路线：

```text
T0 测试环境与基线冻结
        ↓
T1 336-case 当前架构全量 Baseline
        ↓
T2 Failure Attribution 与 Top Failure Patterns
        ↓
T3 Targeted 专项测试集建设
        ↓
T4 定向优化 Replay / Counterfactual Test
        ↓
T5 Expanded Benchmark 500–800 cases
        ↓
T6 Hidden Holdout 泛化测试
        ↓
T7 Robustness / Fault / Stress Test
        ↓
T8 Real Provider Controlled Evaluation
        ↓
T9 Final Acceptance Benchmark
        ↓
长期 Iteration Loop
```

## 2. 三个核心原则

1. 先整体，再专项：Full Benchmark → 找问题 → Targeted Test → 修改 → Targeted Replay → Full Regression。
2. 测试集与调优集分离：Development / Regression / Hidden Holdout / Real-world。
3. 证据等级严格分离：L0 synthetic_provider_free / L1 offline_real_case / L2 real_provider_test / L3 controlled_canary / L4 production。

## 3. 指标体系

答案质量：correctness、completeness、derivation quality、numerical/unit correctness、factuality、citation validity、evidence grounding、answer usability。

Agent 决策：route accuracy、planner validity、skill selection accuracy、tool selection accuracy、RAG trigger accuracy、fallback correctness、reflection trigger accuracy。

系统稳定性：timeout、retry、resume、checkpoint、duplicate side effect、runtime/provider fallback。

性能：latency p50/p95/p99、token usage、model calls、cost、RAG latency、tool latency。

## 4. Git 规则

每个大测试阶段只提交一次，不对子步骤单独提交。

## 5. 最终必须回答

- 当前整体准确率是多少？
- 各课程、难度、输入模态表现如何？
- 最主要失败类型是什么？
- 优化前后提升多少？
- 是否有课程退化？
- Reflection/Experience 是否真的带来收益？
- 异常时是否安全降级？
- 真实 Provider 成本和延迟是多少？
