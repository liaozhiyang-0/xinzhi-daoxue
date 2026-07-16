# 芯智导学：电子信息课程群多智能体平台

本仓库用于建设“芯智导学”电子信息课程群多智能体平台。原有轻量 MVP 所积累的课程知识库、Prompt、测试案例、演示资料和只读历史资料继续保留；当前新增阶段 0—1 的本地工程基线，不推翻已经在讯飞星辰平台跑通的 `SOLVER_CT_电路理论专业解题_v1.0`。

## 当前完成阶段

- 阶段 0：冻结 SOLVER_CT v1.0 基线、性能观测、节点清单模板、已知问题、发布清单与回归评测结构。
- 阶段 1：建立 FastAPI API 壳层、统一 Agent 协议、Mock Provider、星辰 Adapter 边界、数据库模型、SSE、文件存储、Docker Compose、脚本、测试与 CI。
- 真实讯飞星辰 API 尚未接入，因为正式地址、鉴权与字段定义尚未提供。未配置时系统明确使用 Mock Provider。

总体架构见 `docs/architecture/02_xinzhi_multi_agent_platform_plan_v1.0.md`。

## 目录结构

```text
apps/
  api/                       FastAPI、SQLAlchemy、Alembic 与测试
  worker/                    后续异步 Worker 预留
agent_configs/
  registry.yaml              Agent 注册表
  course_packs/              课程包配置
  workflows/                 工作流元数据
docs/
  architecture/              总体架构
  baseline/                  SOLVER_CT 冻结基线
  deployment/                本地开发说明
evaluation/circuit_theory/   电路理论回归评测结构
scripts/                     Windows 与 Linux/macOS 脚本
archive_legacy/              原有历史资料，只读保留
```

仓库中已有的课程资料、知识库、题库和用户新增中文资料目录不属于阶段 0—1 的重写范围。

## 环境要求

- Windows 11 PowerShell 或 Linux/macOS shell。
- 推荐 Python 3.11 或 3.12。
- Docker Desktop 或 Docker Engine + Compose v2。
- Git 和 GitHub CLI（仅发布时需要）。

## Windows PowerShell 启动

如系统限制脚本执行，优先只对当前 PowerShell 进程放行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\dev.ps1
```

脚本会创建 `.venv`、安装依赖、从 `.env.example` 创建 `.env`、启动 PostgreSQL/Redis/MinIO、执行 Alembic migration 并启动 API。

## Docker Compose 启动

Windows 可直接使用自动适配脚本。它会在缺少 Docker Desktop 时通过
winget 安装、启动 Docker Engine、创建 `.env`、校验 Compose、构建镜像并等待
全部服务健康：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\docker_dev.ps1
```

停止服务但保留数据卷：

```powershell
.\scripts\docker_down.ps1
```

也可以手动执行：

```powershell
Copy-Item .env.example .env
docker compose config
docker compose up -d --build --wait
```

开发默认密码只用于本机，部署到共享环境前必须修改。

## 手动启动 API

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "apps/api[dev]"
Copy-Item .env.example .env
Set-Location apps/api
$env:DATABASE_URL="postgresql+asyncpg://xzd_user:xzd_password@localhost:5432/xzd"
$env:REDIS_URL="redis://localhost:6379/0"
$env:MINIO_ENDPOINT="localhost:9000"
..\..\.venv\Scripts\python.exe -m alembic upgrade head
Set-Location ../..
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --reload
```

## 测试与代码质量

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
```

或运行：

```powershell
.\scripts\test.ps1
```

CI 使用 Python 3.12、SQLite 与 Mock Provider，不读取真实星辰秘密。

## API

- 健康检查：`http://localhost:8000/health`
- v1 健康检查：`http://localhost:8000/api/v1/health`
- Swagger：`http://localhost:8000/docs`
- OpenAPI：`http://localhost:8000/openapi.json`

主要接口：

```text
POST /api/v1/sessions
GET  /api/v1/sessions/{session_id}
POST /api/v1/tasks
GET  /api/v1/tasks/{task_id}
GET  /api/v1/tasks/{task_id}/events
GET  /api/v1/tasks/{task_id}/stream
POST /api/v1/files
GET  /api/v1/artifacts/{artifact_id}
```

## Mock Provider

`.env` 默认配置：

```env
DEFAULT_AGENT_PROVIDER=mock
XINGCHEN_ENABLED=false
```

Mock 结果始终包含 `provider=mock` 和 `mock_result` 警告，不代表真实星辰输出，适用于本地开发、测试和演示。

## 星辰 Provider 配置

预留环境变量：

```env
DEFAULT_AGENT_PROVIDER=xingchen
XINGCHEN_ENABLED=true
XINGCHEN_BASE_URL=
XINGCHEN_API_KEY=
XINGCHEN_SOLVER_CT_WORKFLOW_ID=
XINGCHEN_TIMEOUT_SECONDS=120
```

当前 Adapter 不猜测正式请求路径和字段。即使配置变量，仍需补充官方 API 文档后实现请求与响应转换。密钥不得提交到 Git。

## 数据库迁移

```powershell
.\scripts\init_db.ps1
```

或：

```powershell
Set-Location apps/api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
```

## 安全说明

- `.env` 已被 `.gitignore` 忽略，只提交 `.env.example`。
- 不在代码和 Compose 文件中保存真实 API Key 或生产密码。
- 日志不输出完整 API Key、数据库密码或默认完整学生隐私数据。
- 上传文件只允许 png、jpg、jpeg、pdf、md、txt，不执行上传内容。
- 本地默认密码必须在共享部署前修改。

## 当前未实现

- 真实讯飞星辰协议和 SOLVER_CT 云端调用。
- 完整 LangGraph、多智能体编排和 RAGFlow。
- Celery/分布式 Worker。
- 完整学生端、教师端、科研端。
- Kubernetes。

## 后续阶段

1. 接入真实 `SOLVER_CT`。
2. 完成本地到星辰的端到端调用与回归测试。
3. 建立最小调试页面。
4. 开始 `LEARN_01` 课程知识问答。
