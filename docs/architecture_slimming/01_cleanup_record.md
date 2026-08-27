# 架构收缩记录

审计/修改日期：2026-08-26。本文只记录本轮实际检查和修改，不把历史评测结果当作当前运行结果。

## 当前事实

- 学生入口是 FastAPI 托管的 `apps/api/app/static/debug/workspace.html`，由
  `workspace.js`、`workspace-v2.css`、`ui-core.js` 和模块化静态 JavaScript 驱动。
- `/student`、`/workspace`、`/workspace-legacy` 返回同一 Legacy 工作区；没有第二个 React 页面入口。
- `/api/v1/tasks` 是正式任务入口；`/api/v1/chat` 只负责 Session/附件适配，然后调用同一个
  `TaskCreationService`、`task_executor` 和任务 SSE 链。
- 电路理论统一进入 `ACADEMIC_PROBLEM_SOLVER`，由 CT CoursePack、Capability、Skill 和确定性 Tool
  承担；旧 `SOLVER_CT` 配置、代码和活动注册项已删除。
- 数据分析能力仍保留契约、单元测试和冻结状态说明，但 `data_analysis_enabled=false` 时不注入
  `ResearchAnalysisRuntimeService`，新任务在 HTTP 边界返回 409。

## 本轮完成的收缩

1. 删除 `apps/web/` React/Vite 源树、Node 包管理和前端专属脚本。
2. 删除 `apps/api/app/static/debug/react/` 构建产物，以及未被 Legacy 导入的静态 TS 输出。
3. 保留 `apps/api/app/static/debug/ts/materials.js`、`task-transport.js`、
   `workspace-contracts.js`，因为 `workspace.js` 和 Legacy 测试仍直接导入它们。
4. 删除 React 专属路由、资产挂载、测试和 OpenAPI TypeScript 生成脚本；CI 只保留后端检查。
5. 将 React/Vite 迁移文档、旧 CT 基线和迁移审计移动到 `docs/history/`，不删除审计证据。
6. 删除明确可再生的根级 Pytest、Mypy、Ruff 缓存和覆盖率文件；不删除题库、课程原文、评测存储、
   `tmp` 或本地输出证据。

## 未做的删除

`evaluation/cache`、`evaluation/reports`、`真实测试题`、课程资料、数据库和 `apps/api/app/services`
中的研究分析代码均没有整体删除。它们仍被测试、图片调试接口、历史报告或配置引用；继续删除前必须
先完成独立的迁移和数据归档决策。

## 关联索引

目录级逐文件清单见 `docs/repository_file_catalog.md`；运行时调用关系见
`docs/architecture_slimming/03_runtime_graph.md`；尚未合并的服务候选见
`docs/architecture_slimming/02_remaining_complexity.md`。
