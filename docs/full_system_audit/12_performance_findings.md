# 性能与可观测性发现

## 实测与快照

| 指标 | 观测 |
|---|---:|
| 浏览器普通问题端到端 | 单次约 12 s，非统计基准 |
| knowledge.execute 节点 | 单次约 3254 ms |
| RAG 初始 warmup | 83258 ms，总计；文本约 63089 ms，图像约 20169 ms，CPU |
| 现有任务 p95 | 65715 ms，含历史和审计任务 |
| 现有模型调用总延迟 | 279817 ms / 23 calls，不能直接当本轮 p95 |
| 队列 pending/dead-letter/attempts | 0 / 0 / 0 |

本轮样本太少，没有推导 P50/P90，也没有执行压力测试、并发测试或冷启动重复测试。

## P2：失败 trace 的时延不可解释

对失败 tasks 的 debug execution 观察到 waterfall 多个阶段 duration 为 0、total_ms 为 0，且 workflow parser/status 未报告；但同一任务实际在 knowledge 节点运行约 3254 ms，端到端约 4.5 s。失败路径没有保留关键阶段时延，导致运维无法判断是排队、检索、Agent、验证还是序列化耗时。

## 其他风险

- CPU 上加载文本/图像模型的初始 warmup 超过 83 秒；首次用户请求需要明确预热状态或队列化提示。
- Provider health 是 available 但 live=false；性能/可用性看板容易给出矛盾判断。
- `planner_active_count` 等指标是累计或当前快照，若未按 task/route 维度关联，难以定位具体用户失败。

## 结论

当前更需要补齐可观测性字段和冷启动 UX，而不是先做盲目性能优化。所有终态都应记录 queue、retrieval、model、tool、validation、render 的真实 duration 和 error category。
