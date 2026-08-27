# 当前系统基线（2026-08-26）

本文件是全功能审计要求的固定基线入口；完整内容见 [`docs/full_system_audit/01_current_system_baseline.md`](../full_system_audit/01_current_system_baseline.md)。

## 运行快照

- 分支：`feature/circuit-capability-v1`
- HEAD：`021d6e3834d19b00d0ced4ca94ba04db8aceaa8c`
- API：`uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000`
- `/health`：200；数据库、Redis、MinIO 可达。
- 已观察依赖：Postgres、Redis、MinIO、Qdrant 已运行；本审计未启动、重建或重启 Docker。
- 实际 `/workspace`：`apps/api/app/static/debug/workspace.html`；React/Vite 源树和构建产物已删除。
- RAG：ready；文本向量 27101，图像向量 3309；reranker 未加载。
- readiness：当前 API 暴露的 9 个场景均 `production_ready=false`。

## 工作区边界

审计开始前工作区已存在未提交修改；本审计没有修改业务源码、Prompt、Agent、Skill、Router、数据库 migration、公开配置或测试 fixture，没有提交/推送。审计新增报告位于 `docs/full_system_audit/`。

## 审计副作用

为验证真实链路创建了临时游客会话和任务，并上传了一份仓库既有 `组员反馈/组员一反馈/README.txt` 到本地文件服务；未上传密钥或学生隐私。
