# 多学科评测框架

## 案例格式

案例位于 `evaluation/cases/`，按专业求解、知识问答和边界案例分组。每个 YAML
文件包含 `cases` 列表，字段由 `EvaluationCase` 校验。案例应声明课程、任务族、
意图、预期 Agent/CoursePack/路径、答案约束、工具、引用、容差和标签，不能在
Python Runner 中硬编码路由或答案。

首批基准集固定为 36 条：CT 8、AE 6、DE 6、SS 6、知识问答 6、边界 4。

## 运行方式

```powershell
# 只校验案例、注册表和模型路由，不创建任务或调用模型
.\.venv\Scripts\python.exe scripts\run_evaluation.py --validate-only

# 关闭星辰和国产模型 Provider，通过正式 sessions/tasks API 与 TaskRunner 执行
.\.venv\Scripts\python.exe scripts\run_evaluation.py --offline

# 课程、标签、单案例和数量过滤
.\.venv\Scripts\python.exe scripts\run_evaluation.py --course CT --max-cases 5 --offline
.\.venv\Scripts\python.exe scripts\run_evaluation.py --tag high_risk --offline
.\.venv\Scripts\python.exe scripts\run_evaluation.py --case-id CT_KCL_001 --offline
```

离线模式可以产生真实路由、RAG、工具、任务事件和评分结果，但不会证明云端答案
质量。真实模式必须同时显式提供 `--live --confirm-paid`，未指定 `--max-cases` 时
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
