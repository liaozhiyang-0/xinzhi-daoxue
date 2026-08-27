# 已删除与已归档内容

本文件记录本轮明确处理的结构，不代表删除了用户课程资料、真实题库、数据库或评测证据。

## 确定删除

| 范围 | 结果 | 依据 |
|---|---|---|
| `apps/web/` | 删除 40 个 React/Vite 源码、配置和脚本文件 | 无活动导入、无正式入口，Legacy 工作台已确定保留 |
| `apps/api/app/static/debug/react/` | 删除 62 个 React 构建/字体资产 | 仅由已删除 React 页面使用 |
| `apps/api/app/static/debug/ts/api/`、`demo/`、`hooks/`、`math/` 及孤立生成文件 | 删除 11 个文件 | 无 Legacy 导入；保留模块有直接依赖 |
| `/workspace-react` 路由、React mount 和 redirect | 删除 | `/workspace` 是唯一正式工作台 |
| `scripts/generate_openapi_types.py` | 删除 | React/TypeScript 生成链已不存在 |
| 根级 `.pytest_cache`、`.mypy_cache`、`.ruff_cache`、`.coverage` | 删除 | 可由工具安全再生成 |
| 旧 CT 专用配置和 `apps/api/app/agents/solver_ct/` | 删除 | 当前能力统一进入 `ACADEMIC_PROBLEM_SOLVER` |

## 归档而非删除

React 迁移、旧 CT 基线、阶段性架构迁移、旧界面截图和相关审计材料已移动到 `docs/history/`，由
`docs/history/README.md` 标记为历史证据，不参与活动运行链。

## 明确保留

- 课程原始资料、真实测试题、数据库 migration、现有 benchmark 案例和评测证据；
- `evaluation/cache`、`evaluation/reports` 等被忽略的本地产物，直到完成用途/所有者/再生方式确认；
- 数据分析契约、Planner、Local Analysis 和对应测试，用于冻结边界和未来独立解冻验收；
- `materials.js`、`task-transport.js`、`workspace-contracts.js`，它们是当前 Legacy 页面真实依赖。
