# M8：Legacy Cleanup 与 Code Health

日期：2026-08-23

## 前端

- React 已成为 `/workspace` 默认入口；
- `/workspace-legacy` 仅保留兼容重定向；
- `workspace.js`、`workspace.html`、`student.js`、`student.html` 已删除；
- `/workspace-react` 保留为构建和回归检查入口；
- React API boundary、SSE hook 和 feature 目录均已建立。

## 后端

- `TaskQueryService` 和 `TaskProgressReporter` 的实现 owner 已收敛到 `application/tasks`；
- `runtime_adapters` 的 provider/tool composition 已收敛到 `infrastructure`；
- 旧 import path 只保留薄 re-export facade，并由 boundary tests 锁定；
- Runtime package 不再 eager import concrete provider/tool adapter；
- `RuntimeTaskEngine` 仍是唯一任务执行引擎。

高风险大型模块（Academic Solver、内部 Agent dispatch、LearningLoop、RAG、Research 等）没有盲目搬迁。它们仍保持单一实现和 M1 move matrix 中的 owner 约束，避免在 dirty worktree 中制造第二套执行路径。

## 大文件与 services

当前 services 目录仍包含历史兼容和高风险业务模块；本阶段以 owner clear、import direction、thin facade、no duplicate implementation 为健康指标，不以 LOC 机械压缩为目标。已识别的 >2000 行文件保留原状并在后续 owner-by-owner refactor 时处理：`agents/router.py`、`services/academic_solver_service.py`。

## 清理结论

Phase M 清理了已迁移学生工作区的旧源码和静态适配器；兼容路由、管理/调试页面、migration、baseline 和业务数据均保留。
