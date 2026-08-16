# 芯智导学团队快速使用指南

## 1. 首次准备

Windows 11 需要：

- Git；
- Python 3.11、3.12 或 3.13；
- Docker Desktop（使用 Linux containers）；
- 建议至少 16 GB 内存；本地图片模型和 Reranker 默认不会因打开页面而加载。

克隆仓库后启动 Docker Desktop，并等待状态显示为 Running：

```powershell
git clone https://github.com/liaozhiyang-0/xinzhi-daoxue.git
Set-Location xinzhi-daoxue
.\xzd.cmd doctor
.\xzd.cmd start
```

首次运行会安装 Python 依赖并拉取四个基础服务镜像，耗时取决于网络。后续启动不会重复安装未变化的依赖。

数据库和服务数据使用固定 Docker 卷：

```text
xinzhi-daoxue_xzd_postgres_data
xinzhi-daoxue_xzd_redis_data
xinzhi-daoxue_xzd_minio_data
xinzhi-daoxue_xzd_qdrant_data
```

这些名称不依赖仓库所在目录。重启 Docker、更新代码或重新创建容器都会复用同一套数据；`xzd.cmd stop` 不删除数据卷。不要使用 `docker compose down -v`，除非明确要永久清空本地数据。

## 2. 打开页面

启动器显示“服务已就绪”后访问：

| 页面 | 地址 | 用途 |
|---|---|---|
| 统一首页 | `http://localhost:8000/` | 所有功能入口 |
| 学生端 | `http://localhost:8000/student` | 三课程问答、CT 文字/图片解题 |
| RAG 调试 | `http://localhost:8000/debug/rag` | 检索链和引用调试 |
| Agent 管理 | `http://localhost:8000/debug/agents` | 配置、契约和 Dry Run |
| 系统状态 | `http://localhost:8000/system` | 轻量健康状态 |
| 演示中心 | `http://localhost:8000/demo?presentation=1` | 会议演示 |

## 3. 本机私有配置

首次 `start` 会从 `.env.example` 创建 `.env`。`.env` 已被 `.gitignore` 排除，每位组员在自己的机器维护，不通过 Git、聊天或截图分享真实值。

业务任务统一走本地 Runtime。`.env` 只需配置本地基础设施和可选模型 API；不再填写外部工作流或平台凭据。

未配置模型时仍可启动页面，能力状态会显示本地 Runtime 的就绪度；Mock 仅在开发配置显式开启时可用，并会标记“开发模拟”。

## 4. 本地课程资料与索引

仓库不包含原始教材和向量索引。获得授权资料后，将三门课程分别放到仓库根目录：

```text
电路理论/  -> CT
模电/      -> AE
数电/      -> DE
```

先保持 `start` 正在运行，再开一个 PowerShell 窗口构建索引：

```powershell
.\xzd.cmd index -Course CT -TextOnly
.\xzd.cmd index -Course AE -TextOnly
.\xzd.cmd index -Course DE -TextOnly
```

需要图片检索时去掉 `-TextOnly`。模型首次下载和图片索引会更慢，并占用更多内存。生成的 `knowledge_indexes/` 与 Qdrant 数据不会上传 GitHub。

## 5. 日常命令

```powershell
.\xzd.cmd start                    # 标准启动
.\xzd.cmd start -Reload            # 开发热重载
.\xzd.cmd status                   # 服务状态
.\xzd.cmd doctor                   # 环境与配置安全检查
.\xzd.cmd preflight                # 不调用云端的演示检查
.\xzd.cmd preflight -WithCloud     # 明确允许一次真实云端检查
.\xzd.cmd stop                     # 停止基础容器，保留数据卷
```

旧命令 `scripts/dev.ps1`、`scripts/start_demo.ps1` 和 `scripts/stop.ps1` 仍可使用，但内部都转接到同一个启动器。

Linux/macOS 可使用：

```bash
chmod +x xzd.sh
./xzd.sh start
```

## 6. 常见错误

### `socket.gaierror: [Errno 11001]`

旧启动方式在宿主机使用了 Docker 内部主机名 `postgres`。统一启动器会自动将数据库、Redis、MinIO 和 Qdrant 切换到 `localhost`。请勿在宿主机手工运行旧的裸 `uvicorn` 命令。

### Docker Desktop 尚未运行

启动 Docker Desktop，等待引擎就绪后重新运行：

```powershell
.\xzd.cmd doctor
.\xzd.cmd start
```

### 提示容器名称已被旧项目占用

统一启动器不会自动删除旧容器。先停止旧容器并改名，确认新版本运行正常后再决定是否清理：

```powershell
docker stop xzd-api xzd-postgres xzd-redis xzd-minio
docker rename xzd-api xzd-api-legacy
docker rename xzd-postgres xzd-postgres-legacy
docker rename xzd-redis xzd-redis-legacy
docker rename xzd-minio xzd-minio-legacy
.\xzd.cmd start
```

改名和停止不会删除旧数据卷。

### 端口已占用

先确认是否已有一套服务：

```powershell
.\xzd.cmd status
```

API 可改用其他端口：

```powershell
.\xzd.cmd start -Port 8010
```

### 页面能打开但知识库为空

这是本机尚未放置授权教材或尚未构建索引。按“本地课程资料与索引”操作，并在系统状态页确认索引版本。

## 7. 提交代码前

禁止提交 `.env`、教材、索引、上传文件和模型缓存。提交前执行：

```powershell
.\scripts\check.ps1
git status --short
```

敏感文件检查只输出是否通过，不输出凭据值。
