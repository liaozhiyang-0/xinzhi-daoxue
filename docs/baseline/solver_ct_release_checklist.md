# 阶段 0—1 发布检查清单

## 阶段 0

- [x] 建立 SOLVER_CT v1.0 基线文档。
- [x] 记录当前性能观测。
- [x] 建立节点清单模板。
- [x] 建立已知问题清单。
- [x] 建立电路理论 benchmark manifest。
- [ ] TODO：导出星辰工作流节点、提示词和配置。
- [ ] TODO：补充第一批冻结测试案例与标准答案。

## 阶段 1

- [x] 建立 FastAPI API 壳层。
- [x] 建立统一 Agent 协议。
- [x] 建立 Mock 与 Xingchen Provider 隔离层。
- [x] 建立 SQLAlchemy 模型与首个 Alembic migration。
- [x] 建立会话、任务、事件、文件和产物 API。
- [x] 建立 SSE 事件流。
- [x] 建立 Docker Compose、本地脚本和 CI。
- [x] 建立自动化测试。
- [ ] TODO：补充星辰正式接口信息并完成真实联调。

## 发布前

- [x] `ruff check .`
- [x] `pytest`
- [x] `docker compose config`
- [x] 本地 health check
- [x] Mock 端到端任务
- [x] 确认 `.env` 未跟踪。
- [x] 确认无真实 API Key、生产数据库密码或私密数据。
- [x] 创建 Draft Pull Request，不自动合并。

> 已在 Windows 11 + Docker Desktop 4.82.0 + WSL 2 环境完成真实容器验收：PostgreSQL、Redis、MinIO、API 均为 healthy，PostgreSQL Alembic migration、MinIO 文件上传和 Mock 端到端任务均通过。
