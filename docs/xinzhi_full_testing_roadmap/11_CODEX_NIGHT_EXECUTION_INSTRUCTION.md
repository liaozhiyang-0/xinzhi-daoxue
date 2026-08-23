# Codex 全测试阶段执行总指令

你现在进入“芯智导学 Benchmark & Optimization Testing”阶段。

严格按：
T0 → T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9
顺序执行。

## 总规则
1. 不再新增 Agent 架构层。
2. 每个大测试阶段完成后才 commit/push 一次。
3. 不得为了分数删除失败 case。
4. 不得修改 expected answer 迎合模型。
5. synthetic / offline / real-provider 必须分级。
6. Real Provider 没有明确预算时跳过。
7. 不允许 force push / reset --hard / clean -fd。
8. 不自动 merge main。
9. 不自动开启 production/canary。
10. critical regression 出现时停止。
11. 允许按仓库实际调整脚本、目录和 case 数量，但大方向不能改变。
12. 每阶段必须生成报告。
13. T4 才允许真正的针对性代码优化。
14. T1/T2/Holdout 阶段主要测试分析，不得边跑边改。
15. Hidden Holdout 不能被日常 Codex 调优读取完整答案。

## Real Provider
只有同时具备 API key、明确预算、max cases、max cost 才执行，否则标记 SKIPPED_WITH_REASON。

## 最终输出
生成 `docs/testing/testing_campaign_summary.md`，列出：
每阶段状态、benchmark results、top failure patterns、optimization results、regression、hidden holdout、robustness、provider cost、final acceptance、remaining limitations。
