# M5：React Workspace Feature Migration

日期：2026-08-23

## 完成范围

React Workspace 已形成按职责拆分的最小 feature 结构：

- `features/sessions/SessionList`：会话列表、创建和选择；
- `features/chat/MessageList`、`Composer`：消息展示、文本提交、附件选择、取消；
- `components/MarkdownRenderer`、`TaskStatus`：结果和任务状态展示；
- `api/attachments.ts`：上传仍走既有 `/api/v1/files`；
- `api/sessions.ts`、`api/tasks.ts`：业务组件不直接拼接 HTTP 请求。

React 只负责 UI 状态和 API 调用，不复制后端 Task、Planner、Skill、Runtime、RAG 或 Tool 逻辑。CSS 沿用工作台的轻量布局，不引入视觉重设计。

## 控制能力

React 已接入既有 `cancel`、`retry`、`pause`、`resume` 和 `runtime-controls` API。控制按钮根据服务端返回的 `available` 状态显示；没有创建第二套任务控制协议。

## 边界

Markdown 初版采用安全纯文本渲染边界，避免在架构迁移阶段引入新的 HTML/LaTeX 依赖。既有 API 的结构化结果和附件字段保持可扩展；详细 citation/artifact 视觉呈现仍由后续产品迭代补齐，不影响 Task/SSE 主链。

## 健康检查

当前 React feature 文件均远低于 M5 的 400–500 行组件、300 行 hook 和 1000–1200 行 feature review 阈值。
