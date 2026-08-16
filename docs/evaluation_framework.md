# 多学科评测框架

## 案例格式

案例位于 `evaluation/cases/`，按专业求解、知识问答和边界案例分组。每个 YAML
文件包含 `cases` 列表，字段由 `EvaluationCase` 校验。案例应声明课程、任务族、
意图、预期 Agent/CoursePack/路径、答案约束、工具、引用、容差和标签，不能在
Python Runner 中硬编码路由或答案。

基础专业/RAG/边界集为 36 条；教学第一阶段和第二阶段各增加 15 条 synthetic
合同案例，总计 66 条。第二阶段案例覆盖三模式、有限 CT/AE/DE 核对、H2 上限、
后端披露、标准解复用、刷新状态和跨用户隔离。新增案例全部
`official_scoring: false`，不代表真实教学效果或学科准确率。

## 运行方式

```powershell
# 只校验案例、注册表和模型路由，不创建任务或调用模型
.\.venv\Scripts\python.exe scripts\run_evaluation.py --validate-only

# 使用本地 Runtime 和 Mock Provider，通过正式 sessions/tasks API 与 TaskRunner 执行
.\.venv\Scripts\python.exe scripts\run_evaluation.py --offline

# 课程、标签、单案例和数量过滤
.\.venv\Scripts\python.exe scripts\run_evaluation.py --course CT --max-cases 5 --offline
.\.venv\Scripts\python.exe scripts\run_evaluation.py --tag high_risk --offline
.\.venv\Scripts\python.exe scripts\run_evaluation.py --case-id CT_KCL_001 --offline
.\.venv\Scripts\python.exe scripts\run_evaluation.py --tag teaching_loop_phase2 --offline --no-cache
```

离线模式可以产生真实路由、RAG、工具、任务事件和评分结果，但不会证明真实模型答案
质量。真实模型模式必须同时显式提供 `--live --confirm-paid`，未指定 `--max-cases` 时
最多执行 3 条：

```powershell
.\.venv\Scripts\python.exe scripts\run_evaluation.py --live --confirm-paid --course CT --max-cases 3
```

## 缓存、续跑与报告

缓存键包含案例内容、运行模式、模型路由、Agent 注册表、CoursePack、求解图、
服务、Runner、评分器和提示版本哈希。默认复用缓存；`--rerun-failed` 只重新执行
缓存中的失败案例，`--no-cache` 强制重跑。

报告写入：

- `evaluation/reports/latest.json`：机器统计和每题结果；
- `evaluation/reports/latest.md`：简洁摘要、课程统计、性能和失败列表。

增加案例时应使用新 `case_id`，说明来源和允许假设，先运行 `--validate-only`，再
运行离线单题。不要用降低期望或删除失败项的方式提高通过率。

只读报告 API 由 `ENABLE_EVALUATION_API` 控制，默认关闭；没有 HTTP 评测执行接口，
以避免误触发付费请求。

## 教学闭环第三阶段合成评测

`evaluation/cases/teaching_loop_phase3/` 只包含
`provenance.source_type: synthetic` 且 `official_scoring: false` 的合同案例。
它覆盖 `attempt_version_integrity`、`feedback_uptake_capture`、
`mastery_evidence_consistency`、`full_solution_dependency_handling`、
`retest_plan_correctness`、`manual_review_safety` 和
`cross_user_isolation`。

这些用例验证工程行为与安全边界，不代表真实学生学习效果、教学有效性或统计校准
后的掌握度。第三阶段验证不调用真实 Provider。
