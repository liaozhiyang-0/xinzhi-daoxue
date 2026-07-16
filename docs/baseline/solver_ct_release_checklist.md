# 本地阶段 0—1.5 发布检查清单

## Git 与资料安全

- [x] 新分支直接基于 `origin/main`。
- [x] 未大规模迁移、删除或重命名课程资料。
- [x] `.local_inputs/`、`.local_outputs/` 与原始星辰 YAML 已忽略。
- [ ] BLOCKED：完整总体架构原文尚未提供。
- [ ] BLOCKED：原始星辰 YAML 尚未提供，无法生成真实脱敏清单。

## 本地工程

- [x] 星辰状态明确为 `not_published`。
- [x] `XingchenCloudProvider` 不执行 HTTP 请求。
- [x] Mock 结果显式标记。
- [x] 任务创建返回 HTTP 202 并由 TaskRunner 后台执行。
- [x] 事件使用递增 sequence。
- [x] SSE 支持 `Last-Event-ID` 与 `after`。
- [x] 已增加重试、取消、文件元数据和本地调试页面。
- [x] 已增加增量数据库 migration。

## 最终质量门

- [x] Ruff
- [x] Mypy
- [x] Pytest / Coverage
- [x] Migration upgrade / downgrade / upgrade
- [x] OpenAPI export
- [x] Config validation
- [x] Sensitive file scan
- [x] Docker Compose config
- [x] Docker runtime / Mock E2E
- [x] 架构、安全、可靠性三轮审查
- [ ] 新 Draft PR 与 CI

## 本轮真实结果

- Ruff：通过。
- Mypy：45 个应用源文件通过。
- Pytest：40 passed，覆盖率 86%，1 个上游 TestClient 弃用警告。
- SQLite migration：upgrade / downgrade / upgrade 通过。
- PostgreSQL migration：`20260717_0002` downgrade / upgrade 通过。
- Docker：PostgreSQL、Redis、MinIO、API 均 healthy。
- 非阻塞任务：POST 约 97 ms 返回 queued；Mock 后台完成。
- SSE：sequence 连续 1—7；`Last-Event-ID=2` 从 3 恢复。
- 文件：真实保存至 MinIO，SHA-256 与元数据入库。
- 调试页与 Swagger：HTTP 200。
- 取消、失败和重试：Docker 端到端验证通过。
- Docker 日志：保存在被忽略的 `.local_outputs/docker-compose.log`，验收后容器已关闭。
