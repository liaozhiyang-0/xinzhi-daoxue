# Testing Guide

```powershell
.\scripts\check.ps1
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy apps/api/app
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-local
.\.venv\Scripts\python.exe scripts/run_regression.py
.\.venv\Scripts\python.exe scripts/check_environment.py
.\.venv\Scripts\python.exe scripts/check_sensitive_files.py
docker compose config
```

真实 Spark/Qwen、Embedding 和 Docker 检查需要本机凭据、已下载模型或 Docker Desktop；没有执行时不能报告为通过。Provider 单元测试使用 MockTransport，不消耗云端额度。仓库不再提供外部工作流压力测试入口。

## 内部模型 Agent

离线门禁不发送真实请求：

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_model_agents.py --dry-run
.\.venv\Scripts\python.exe -m pytest -q `
  apps/api/tests/test_internal_agents.py `
  apps/api/tests/test_model_agent_evaluation.py `
  apps/api/tests/test_model_registry_service.py `
  apps/api/tests/test_spark_llm_provider.py
```

真实评测会消耗 Spark/百炼额度。先跑单一 Agent 或 case，查看脱敏报告后再扩大范围：

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_model_agents.py `
  --agent COURSE_CLASSIFIER_LOCAL_V1 `
  --max-total-tokens 1200 --max-output-tokens 160

.\.venv\Scripts\python.exe scripts\evaluate_model_agents.py `
  --case circuit_plan_missing_direction `
  --max-total-tokens 1800 --max-output-tokens 384
```

通过条件包括：进程退出码为 0；报告 `errors=0`、`quality_failed=0`；每个 case 状态为 `passed`；报告没有完整输入、输出、Key 或图片 Base64。不同模型的 Provider Token 口径可能不同，只能在各自账单口径内比较。

## Workspace 与内部 Agent 集成

下面的测试使用内存数据库、替身 Agent 和 MockTransport，不发送真实模型请求：

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  apps/api/tests/test_internal_agent_execution.py `
  apps/api/tests/test_student_web.py `
  apps/api/tests/test_task_presentation.py `
  apps/api/tests/test_task_api.py
```

重点检查：学生端没有 Provider 或原始 Agent ID；六类能力均经 `POST /api/v1/tasks` 创建非阻塞任务；内部 Agent 结果沿用既有 SSE 事件顺序；备课任务只使用同一执行链返回的 `RetrievalContextPacket`；作业初审保持 reference-only。
