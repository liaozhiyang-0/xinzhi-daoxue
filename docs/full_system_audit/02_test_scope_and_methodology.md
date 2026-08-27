# 测试范围与方法

## 范围

覆盖：浏览器工作台、游客会话、单轮和多轮任务、刷新恢复、任务创建/查询/取消、SSE 事件与 `Last-Event-ID` 重连、Agent/Scenario readiness、Router/Planner trace、知识库和研究检索、文件上传/抽取/chunk、模型/RAG 健康、任务指标、静态代码质量和前端类型检查。

计划覆盖但本轮未完整执行：20+ 次每场景稳定性矩阵、真实移动 viewport 交互、生产 Provider 的全量模型回归、Docker 重建和压力测试。未执行项标记为“未验证”，不推断为通过。

## 样本与证据规则

- 浏览器使用实际 `http://127.0.0.1:8000/workspace`，观察 DOM、渲染结果、控制台 warning/error 和刷新后恢复。
- API 请求使用临时 guest 身份；任务 ID、状态、事件和 debug execution 记录保存为审计笔记，不把 token 写入文档。
- 对 RAG 和研究检索分别使用已知相关词与随机不存在词，检查是否返回候选、是否给出低相关/无匹配警告。
- 每个问题记录复现输入、入口、观察到的状态和限制；没有确认根因时标为“根因未确认/待定位”。
- 性能只报告实际观察到的单次时长和现有指标快照，不从小样本推导 P50/P90。

## 质量检查命令

```powershell
.\.venv\Scripts\python.exe scripts/validate_config.py
.\.venv\Scripts\python.exe scripts/check_sensitive_files.py
.\.venv\Scripts\python.exe scripts/check_repo_drift.py
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy apps/api/app
.\.venv\Scripts\python.exe -m pytest apps/api/tests -q
npm --prefix apps/web run typecheck
```

已确认通过：配置、敏感文件、repo drift、Ruff、Mypy（364 files）、Web TypeScript；全套 Pytest 为 2038 passed、15 skipped、15 warnings，耗时 29 分 21 秒。

## 不允许的行为

本轮没有修改业务源码、Prompt、Agent、Skill、Router、数据库 migration、公开配置或测试 fixture；没有提交、推送、force push；没有重启或重建 Docker；没有读取或传播真实密钥。
