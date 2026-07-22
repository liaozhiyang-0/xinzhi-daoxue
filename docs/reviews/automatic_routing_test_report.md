# 自动路由测试报告

测试日期：2026-07-20。数据集为 `evaluation/automatic_routing/cases.json`，共 70 条；每条包含 case_id、用户输入、会话、附件、期望 Agent/Intent/状态、required_fields、forbidden_agent_ids 和人工复核标记。

## 结果

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_automatic_routing_fixture.py -q
```

结果：72 个测试通过（70 条参数化路由 + fixture 结构/数量 + 延迟断言中的合并计数），无错误路由。与结果治理测试合并运行时为 76 passed。

| 期望目标 | 用例数 | 正确 | 准确率 |
|---|---:|---:|---:|
| LEARN | 10 | 10 | 100% |
| SOLVER_CT | 10 | 10 | 100% |
| TEACH_01 | 11 | 11 | 100% |
| TEACH_02 | 11 | 11 | 100% |
| RESEARCH_02 | 11 | 11 | 100% |
| RESEARCH_03 | 12 | 12 | 100% |
| unresolved | 5 | 5 | 100% |
| 总计 | 70 | 70 | 100%（fixture 内） |

65 条直接选择，5 条因模糊/冲突且 Router 未配置而 unresolved。明确请求本地直接决定比例为 92.86%；实际云端 Router 调用比例为 0%，不是因为绕过 Router，而是当前 `XINGCHEN_FALLBACK_ROUTER_FLOW_ID` 未配置。若配置可用，这 5 条是 Router 候选，占 7.14%。

## 覆盖

- 六个业务 Agent 各至少 10 条，包含课程边界、材料不足、恶意要求和负向规则。
- 10 条模糊、多意图和追问；其中 2 条明确数据分析→学术写作流水线。
- 34 条标记人工复核。
- AE/DE 完整求解禁止交给 LEARN；无 rubric、虚构引用、虚构统计量由 Validator 测试覆盖。
- 一次重路由路径记录 `visited_agents` 和 `reroute_count`；没有 A→B→A 路径。

## 修复前后

修改前没有这套 70 条统一自动路由 fixture，因此没有可比较的历史准确率，不能虚构“提升百分比”。本轮基线的 34 个聚焦测试通过；新增实现后，70 条 fixture 全部通过，相关路由/前端/Debug/非阻塞测试另有 30 passed。

fixture 结果只证明确定性预期，不代表真实用户分布准确率。上线前应保留人工复核字段并用脱敏真实请求扩展数据集。

全量回归：`255 passed, 13 skipped`，覆盖率 82%。跳过项为需要真实 RAG 模型或由专用脚本单独执行的真实星辰测试；六业务工作流的最小真实检查结果见接入审计报告。
