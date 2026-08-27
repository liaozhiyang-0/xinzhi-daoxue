# M7：Cross-stack Parity 与 Regression

日期：2026-08-23

## 已验证边界

| 边界 | 结果 | 证据 |
| --- | --- | --- |
| React type boundary | PASS | `npm run typecheck` |
| React production bundle | PASS | `npm run build` |
| Legacy/React static smoke | PASS | `npm run smoke` |
| `/workspace` 默认 React | PASS | `test_react_workspace_route.py` |
| `/workspace-legacy` 回滚入口 | PASS | `test_react_workspace_route.py` |
| Task/runtime adapter compatibility | PASS | `test_modernization_boundaries.py` |
| Runtime adapters/subagents/skill binding | PASS | 17 targeted pytest cases |
| OpenAPI | unchanged by Phase M semantics | M0 frozen hash retained |

## 精简回归集

本阶段采用最小阻断集，覆盖新入口、兼容 facade、Runtime adapter、subagent、skill binding 和前端构建；不重复执行已经在 T5 通过的全量 benchmark。

Phase M 未修改 Task API、Task lifecycle、SSE event protocol、checkpoint/resume、Planner、Skill、Reflection、Experience、Evaluation、RAG 或 Tool 接口。

## 已知基线

M0 的 focused regression 中有一个在架构变更前已存在的本地失败：撤回资料历史回答断言未显示“课程资料已撤回”，但任务公开撤回状态断言通过。该行为不属于 Phase M 变更，未在本阶段扩大范围修复；GitHub CI 是最终门禁。
