# 会议自然语言自动调度演示指南

## 会前检查

```powershell
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\validate_completed_workflows.py
.\.venv\Scripts\python.exe scripts\validate_completed_workflows.py --live
```

打开 `/demo`，六个场景都跳转到同一个 `/workspace`，不手动指定 Agent。确认课程索引可用；当前 Router Flow 未配置，TEACH_01/02 云端真实检查为空回答，会议中若未修复只能演示明确标记的 unresolved/fallback，不能说云端成功。

## 场景

1. “为什么负反馈能够稳定放大倍数？”：自动 AE → LEARN → 课程证据与引用检查。
2. “给大二学生设计一节90分钟的负反馈放大电路课程……”：TEACH_01、字段提取、AE RAG、教案时间线；当前预期可能走模板 fallback。
3. 带题目、学生答案、rubric 和满分的批改文本：TEACH_02；强调建议分和人工复核；当前预期可能走 review fallback。
4. 论文段落改写：RESEARCH_02；展示课程 RAG 关闭和引用边界。
5. 数据分析方法请求：RESEARCH_03；无数据时显示 plan，不生成 p 值。
6. 完整 CT 数值题：SOLVER_CT；在 Execution Debug 展示选择原因和最多一次重路由字段。

每次完成后点击演示中心“读取最近真实执行”，展示真实 Trace。若要演示数据分析→写作流水线，明确输入“先给分析计划，再把计划写成方法段”，界面应显示两个阶段且不得把计划写成已完成结果。
