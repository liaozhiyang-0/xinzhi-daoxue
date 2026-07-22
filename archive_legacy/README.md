# 历史隔离区

本目录保存已退出活动架构、但仍有审计价值的历史材料。这里的内容：

- 不参与应用导入、Agent 注册、测试发现或 Docker 构建；
- 不作为当前 API、环境变量或工作流能力的依据；
- 只允许用于历史追溯，不在此目录开发新功能。

当前运行事实以 `apps/api/app/`、`agent_configs/registry.yaml` 和 `docs/` 下的现行文档为准。

## 已隔离内容

- `docs/`：阶段 0—2.2 的历史架构、评审快照与旧工作流计划；
- `apps/api/app/services/task_service.py`：无人引用的旧 `TaskService` 导入门面。活动代码直接使用 `TaskQueryService`。

隔离代码保留原相对路径是为了方便审计，不表示它仍是可导入包；本目录不会加入 `PYTHONPATH`。
