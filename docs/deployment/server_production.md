# 服务器部署

服务器使用 Docker Compose 的生产覆盖文件，不使用 Windows 本地启动器，也不把本地教材、向量索引、测试数据或 `.env` 打进镜像。

## 1. 准备主机

安装 Docker Engine 和 Compose v2，并准备只读课程资料目录：

```text
/srv/xinzhi-daoxue/knowledge/CT
/srv/xinzhi-daoxue/knowledge/AE
/srv/xinzhi-daoxue/knowledge/DE
/srv/xinzhi-daoxue/knowledge/SS
/srv/xinzhi-daoxue/knowledge/DSP
/srv/xinzhi-daoxue/knowledge/COMM
```

复制服务器环境模板并填写真实密码、DashScope Key 和主机路径：

```bash
cp .env.server.example .env
chmod 600 .env
```

`AUTH_REQUIRED=true`、`ALLOW_MOCK_FALLBACK=false`、`IFLYTEK_SPARK_ENABLED=false` 和 `TASK_EXECUTOR_MODE=redis` 必须保持不变。有效案例的模型路由由 `config/model_routes.yaml` 控制，首选为 Qwen；Spark 不作为首选模型。

## 2. 配置与启动

先只检查 Compose 渲染结果：

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml --profile server config --quiet
```

启动一个 API 和一个 Worker：

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml --profile server up -d --build --wait
```

检查服务：

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml --profile server ps
curl --fail http://127.0.0.1:8000/health
```

API 只绑定到 `SERVER_BIND_ADDRESS`，默认是 `127.0.0.1`。生产环境应由 Nginx、Caddy 或云负载均衡器负责 TLS、域名和外部访问控制；PostgreSQL、Redis、MinIO、Qdrant 不发布宿主机端口。

## 3. 更新与停止

更新代码后重新构建 API 和 Worker，不删除数据卷：

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml --profile server up -d --build --wait
docker compose -f docker-compose.yml -f docker-compose.server.yml --profile server logs --tail=100 api queue-worker
```

停止服务但保留数据：

```bash
docker compose -f docker-compose.yml -f docker-compose.server.yml --profile server down
```

不要在没有备份和明确审批的情况下使用 `down -v`。

## 4. 发布门禁

- `docker compose ... config --quiet` 通过。
- API、Worker、PostgreSQL、Redis、MinIO、Qdrant 均为 healthy/running。
- `/health` 返回 HTTP 200，且数据库、Redis、MinIO 状态为 `ok`。
- API 只有一个服务实例，Worker 只有一个服务实例。
- `TASK_EXECUTOR_MODE=redis`，未以本地内存队列运行。
- `AUTH_REQUIRED=true`，Debug API 和 Mock 均关闭。
- DashScope/Qwen Key 已通过服务器 Secret 管理注入，未进入 Git、镜像层或日志。
- 部署前完成数据库备份和 Alembic 增量迁移审查。
