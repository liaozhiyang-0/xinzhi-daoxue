# RESEARCH_03_DATA_ANALYSIS_V2 完成审计

本文件按当前工作树和已执行命令审计 V2 目标，不把合成数据、Mock、静态检查或本地冒烟写成真实科研效果、市场结果或机构验收结论。缺少授权数据、研究者复核或外部来源的项目继续标记为“待补证据”。

## 1. 要求—证据矩阵

| 目标要求 | 当前实现/材料 | 可复核证据 | 当前结论 |
| --- | --- | --- | --- |
| 研究问题、假设、估计量、研究设计输入合同 | `apps/api/app/contracts/research_analysis.py`；`workspace.html` / `workspace.js` | 合同、验证性分析缺假设和 `estimate_effect` 缺 estimand 的阻断测试；浏览器 V2 计划提交 | 已落地（本地） |
| 数据契约与质量门禁 | `research_data_quality.py`、`research_tabular_io.py` | 缺授权、checksum、变量角色、形状、缺失策略和重复配对键的阻断测试 | 已落地（本地） |
| 分析计划冻结 | `research_analysis_planner.py` | 同请求计划 hash 稳定、计划篡改阻断、结论边界写入 Artifact | 已落地（本地） |
| 两组实验比较 | `research_local_analysis.py` | 合成执行器测试、四类演示、受控附件 HTTP 冒烟 | 已落地（确定性 MVP） |
| 观察数据回归 | `research_local_analysis.py` | 回归系数、残差、共线性/影响点边界及合成演示 | 已落地（数值 MVP） |
| 时间序列预测 | `research_local_analysis.py` | 时间排序、重复周期、两步基线和后半窗口敏感性测试 | 已落地（一阶基线 MVP） |
| 小样本实验 | `research_local_analysis.py` | 精确置换/留一法边界、有限样本限制和合成演示 | 已落地（确定性 MVP） |
| 重复测量、多组比较和 Bootstrap | `research_local_analysis.py` | 重复配对键阻断、固定种子 Bootstrap、声明式 `holm` / `none` 回归 | 已落地（扩展边界） |
| 统计/模型诊断与科学结论边界 | Planner、Local Executor、结果治理 | diagnostics、robustness、limitations、`human_review_required=true` | 已落地；不替代统计师/PI |
| 分析包与 Artifact | `analysis_bundle.json`、provenance、report、SVG | Artifact SHA-256、任务目录隔离、路径脱敏测试 | 已落地（本地） |
| 人工复核与签字持久化 | `research_analysis_review.py`、review API | 清单完整匹配、签字 hash、任务隔离测试 | 已落地；不等于机构电子签章 |
| 论文方法证据与用户数据隔离 | `ResearchEvidenceReference`、TaskRunner V2 分支 | `method_reference` 角色约束、HTTP 结果 evidence IDs、无外部数据注入 | 已落地（本地） |
| TaskRouter、TaskRunner、会话隔离 | TaskRunner、scenario catalog、session API | 场景绑定、跨用户 session 拒绝、V2 本地 Provider 回归 | 已落地（本地） |
| SSE 顺序、重连和任务状态 | 任务事件 API、SSE 测试 | `test_sse_events.py`、`test_sse_event_order.py`、`test_sse_reconnect.py` | 已落地（协议回归） |
| 前端进度、证据、报告和研究设计输入 | `workspace.html`、`workspace.js`、`workspace-v2.css` | 页面契约、Node 语法、v7 资源 200、浏览器计划提交 | 已落地（本地 UI） |
| 受控 API 执行 | 文件服务、`internal_agent_execution.py`、TaskRunner | CSV/XLSX/Parquet 上传优先交给 Qwen/Spark 直接分析；文件读取、脱敏、输入边界和结构化结果由本地治理；模型失败才回退本地计算 | 已落地（本地 HTTP + 模型主导链路） |
| 合成/边界评测和可复现演示 | `scripts/research_analysis_demo.py` | 四类 MVP 均 `executed`，网络调用 0，Artifact 生成，均要求人工复核 | 已落地（合成材料） |
| 试点输入预检 | `scripts/validate_research_pilot.py`、模板 | 合同、checksum、行列形状、依赖阻断；不调用模型/网络 | 已落地（试点前置） |

## 2. 已执行的关键验证

以下是实际执行过的命令类别和结果，不代表全仓库所有测试均通过：

```powershell
$env:APP_ENV = "test"
$env:PYTHONPATH = "apps/api"
.venv\Scripts\python.exe -m pytest --no-cov -q `
  apps/api/tests/test_research_local_analysis.py
# 12 passed

.venv\Scripts\python.exe -m pytest --no-cov -q `
  apps/api/tests/test_xingchen_cloud_policy.py
# 6 passed

.venv\Scripts\python.exe -m pytest --no-cov -q `
  apps/api/tests/test_sse_events.py `
  apps/api/tests/test_sse_event_order.py `
  apps/api/tests/test_sse_reconnect.py
# 3 passed

.venv\Scripts\python.exe -m pytest --no-cov -q `
  apps/api/tests/test_task_api.py::test_research_analysis_v2_api_persists_sanitized_provenance
# 1 passed (the complete test_task_api.py file also passes 6/6)

.venv\Scripts\python.exe -m pytest --no-cov -q `
  apps/api/tests/test_student_web.py
# 10 passed; TestClient fixture disables live external retrieval for deterministic API tests

.venv\Scripts\python.exe -m pytest --no-cov -q `
  (Get-ChildItem apps/api/tests -Filter 'test_research_*.py' |
    Select-Object -ExpandProperty FullName)
# 51 passed; two dependency deprecation warnings

node --check apps/api/app/static/debug/workspace.js
.venv\Scripts\ruff.exe check apps/api/app apps/api/tests scripts
.venv\Scripts\mypy.exe apps/api/app --no-incremental
```

真实本地 HTTP 冒烟已确认：

- `/api/v1/health`、`/workspace` 和 v7 前端资源返回 200；
- 受控多组 CSV 任务完成，Provider 为 `local_analysis_v2`；
- 模型主导时结构化结果标记 `analysis_execution_source=model_direct`，并保留 Provider、模型和人工复核风险；模型不可用时才进入本地确定性回退；
- `multiple_comparison_method=none` 时无 Holm 结果，有未调整结果和人工复核要求；
- 生成 7 个分析 Artifact；
- 浏览器计划提交包含估计量、分析单位、协议摘要和方法证据，控制台无 error/warning。

## 3. 明确未完成项

这些项目不能由本地合成测试替代：

1. 真实授权实验室数据、伦理/隐私审批、数据字典和研究协议；
2. 研究者/统计师复现日志、修改次数、实际耗时和签字记录；
3. 外部市场规模、竞品、政策、报价、采购周期和客户付费意愿；
4. 多因子、纵向、多层模型和机构级长期留存/电子签章；
5. 全仓库回归中既有材料漂移和长耗时测试片的治理。

学生端 API 的通用测试 fixture 已显式关闭实时外部检索；provider/service 层继续使用显式 fake 覆盖检索逻辑，避免测试把 arXiv/OpenAlex/Crossref 的限流或网络状态误当成路由/会话回归结果。

在上述材料补齐前，商业表述只能是“面向科研团队试点的可审查分析工作台”，不能表述为已替代统计师、已提升科研效率或已经形成收入。
