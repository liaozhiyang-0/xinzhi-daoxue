# 阶段 0—1.5 用户审查指南

## 优先检查

1. 确认新 PR 的 Base 是 `main`，Head 是 `feat/local-stage-0-1-clean`。
2. 查看 PR Files changed，确认没有课程资料大规模 delete、rename 或移动。
3. 确认 `.local_inputs/` 和原始星辰 YAML 没有被 Git 跟踪。
4. 搜索 `httpx.AsyncClient`，确认 `XingchenCloudProvider` 没有真实网络调用。
5. 查看 CI 的 Ruff、Mypy、Pytest、OpenAPI、配置、敏感扫描和 Compose 检查。

## 核心代码

- `apps/api/app/services/task_runner.py`
- `apps/api/app/services/task_creation_service.py`
- `apps/api/app/providers/factory.py`
- `apps/api/app/providers/xingchen.py`
- `apps/api/app/services/event_service.py`
- `apps/api/app/api/v1/tasks.py`
- `apps/api/app/contracts/agent.py`
- `apps/api/app/api/v1/files.py`
- `apps/api/app/static/debug/`

## 本机命令

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\check.ps1
.\scripts\dev.ps1
```

## 浏览器

- `http://localhost:8000/health`
- `http://localhost:8000/docs`
- `http://localhost:8000/debug`

## 暂时不要做

- 不要在审查前合并。
- 不要填写星辰 API Key。
- 不要发布原始 YAML。
- 不要修改 `SOLVER_CT v1.0`。
- 不要声称已接入真实星辰。

## 当前输入缺口

- BLOCKED：完整总体架构 Markdown 原文未随本轮附件提供。
- BLOCKED：`SOLVER_CT_电路理论专业解题_v1.0.yml` 未随本轮附件提供。

这两个缺口不影响本地 Mock 平台底座审查，但工作流 SHA-256、节点数、连线数和真实脱敏清单必须等待原始 YAML 后再确认。
