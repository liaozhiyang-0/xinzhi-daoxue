# 本地开发指南

> 当前 `SOLVER_CT` 尚未发布外部 API。本地默认并仅验证 Mock Provider，
> 不要求填写任何星辰 API 字段。

## 1. 安装 Python

推荐安装 Python 3.11 或 3.12，并在安装器中启用 Python Launcher。PowerShell 验证：

```powershell
py -0p
py -3.12 --version
```

不要把项目依赖安装到系统 Python；脚本会使用仓库根目录 `.venv`。

## 2. 安装 Docker Desktop

Windows 11 推荐 Docker Desktop + WSL 2 后端。验证：

```powershell
docker --version
docker compose version
```

如果命令不存在，启动或安装 Docker Desktop 后重新打开 PowerShell。

## 3. PowerShell 执行策略

不要全局关闭安全策略。仅当前进程临时放行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

如需当前用户长期允许本地签名脚本，可在理解组织策略后使用：

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## 4. 创建环境配置

```powershell
Copy-Item .env.example .env
```

`.env` 不会提交到 Git。至少修改 PostgreSQL 和 MinIO 的开发密码；真实星辰 API Key 只能放在本地 `.env` 或安全秘密管理系统中。

Compose 容器使用 `DATABASE_URL`、`REDIS_URL`、`MINIO_ENDPOINT` 中的服务名；宿主机脚本使用对应的 `HOST_DATABASE_URL`、`HOST_REDIS_URL`、`HOST_MINIO_ENDPOINT`。不要把两组地址混用。

## 5. 一键启动

```powershell
.\scripts\dev.ps1
```

执行顺序：

1. 检查 Python 3.11/3.12 与 Docker。
2. 创建 `.venv`。
3. 安装 `apps/api` 及开发依赖。
4. 检查并创建 `.env`。
5. 启动 PostgreSQL、Redis、MinIO。
6. 执行 Alembic migration。
7. 启动 Uvicorn。

## 6. Docker Compose 启动完整服务

Windows 一键安装、启动和健康检查：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\docker_dev.ps1
```

该脚本会：

1. 从 PATH 或 Docker Desktop 默认安装目录定位 `docker.exe`。
2. 缺少 Docker Desktop 时使用 winget 安装。
3. 自动启动 Docker Desktop，并等待 Engine 就绪。
4. 从 `.env.example` 创建未跟踪的 `.env`。
5. 执行 `docker compose config --quiet`。
6. 构建并启动全部服务，等待四个容器健康。
7. 验证 API、PostgreSQL、Redis 和 MinIO 状态。

手动命令：

```powershell
docker compose config
docker compose up -d --build --wait
docker compose ps
```

服务地址：

| 服务 | 地址 |
| --- | --- |
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |
| MinIO API | http://localhost:9000 |
| MinIO Console | http://localhost:9001 |

停止服务但保留数据库和对象存储卷：

```powershell
.\scripts\docker_down.ps1
```

## 7. 数据库迁移

```powershell
.\scripts\init_db.ps1
```

创建新 migration：

```powershell
Set-Location apps/api
..\..\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe change"
..\..\.venv\Scripts\python.exe -m alembic upgrade head
```

## 8. 数据库重置

以下操作会删除本项目 Docker 命名卷中的开发数据。先确认当前目录是本仓库且无需保留数据：

```powershell
docker compose down
docker volume ls --filter "name=xzd"
```

需要重置时再手动执行：

```powershell
docker compose down -v
docker compose up -d postgres redis minio
.\scripts\init_db.ps1
```

## 9. 测试

```powershell
.\scripts\test.ps1
```

等价命令：

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
```

测试使用 SQLite 和 Mock Provider，不需要 PostgreSQL、Redis、MinIO 或星辰密钥。

## 10. 常见端口冲突

查看端口：

```powershell
Get-NetTCPConnection -LocalPort 5432,6379,8000,9000,9001 -ErrorAction SilentlyContinue
```

如果端口被占用，先停止冲突服务；需要改端口时修改 Compose 的主机端口映射和本地访问地址，不要随意修改容器内部默认端口。

## 11. 常见故障

### Docker 命令不存在

确认 Docker Desktop 已安装并运行，然后重新打开终端。

### PowerShell 拒绝执行脚本

只对当前进程运行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### PostgreSQL migration 连接失败

```powershell
docker compose ps
docker compose logs postgres
```

确认 `.env` 中 `DATABASE_URL` 的主机在 Docker 内使用 `postgres`，宿主机手动运行 API 时使用 `localhost`。

### MinIO 不可用

开发环境在 `LOCAL_STORAGE_FALLBACK=true` 时回退到 `LOCAL_STORAGE_PATH`。查看：

```powershell
docker compose logs minio
```

### 为什么始终显示 Mock

这是当前阶段的安全设计。`SOLVER_CT` 尚未发布外部 API，健康检查应显示：

```text
active_provider=mock
provider_mode=only_mock
xingchen_publication_status=not_published
```

不要填写星辰 API Key。工作流发布和真实接入属于后续独立阶段。

## 12. 调试页与完整检查

启动 API 后访问：

```text
http://localhost:8000/debug
```

页面支持创建会话、上传附件、提交非阻塞任务、读取 SSE、取消、重试和查看产物。它是本地开发工具，不是正式学生端。

提交前运行：

```powershell
.\scripts\check.ps1
```

该脚本依次执行配置检查、敏感文件扫描、Ruff、Mypy、Pytest、OpenAPI 导出、Docker Compose 配置检查和 `git diff --check`。
