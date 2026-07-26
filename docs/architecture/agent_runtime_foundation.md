# Agent Runtime Foundation v1

## 范围与边界

本版本在唯一任务链上增加消息历史、多轮上下文、预算压缩和受控长期记忆：

```text
POST /api/v1/tasks
→ TaskCreationService（user message + task）
→ TaskExecutor
→ TaskRunner（ConversationContextBundle + 现有 RAG）
→ Agent / Model / SOLVER_CT_V1
→ TaskPresentation
→ assistant message + WorkingState + Summary + metrics
```

`POST /api/v1/chat` 仍是适配器。实现没有新增 TaskRunner、模型入口、队列、
顶层 Agent 或学习掌握度数据库，也没有修改冻结的 `SOLVER_CT_V1`。云端工作流
默认授权仍为 `XINGCHEN_WORKFLOWS_DEFAULT_ENABLED=false`。

## 数据职责

| 概念 | 事实来源 | 用途 |
|---|---|---|
| 任务历史 | `tasks`、`task_events`、`agent_runs` | 执行、重试、SSE、调试 |
| 消息历史 | `conversation_messages` | 用户可见多轮对话与稳定 sequence |
| 会话上下文 | `ConversationContextBundle` | 当前任务临时组装，不保存完整 Prompt |
| WorkingState | `session_working_states` | 当前目标、纠正、待办和高置信状态 |
| 会话摘要 | `session_summaries` | 有覆盖范围、来源 ID、checksum 的版本化压缩 |
| Context Cache | Redis 或进程内 TTL | 缓存脱敏的上下文结构，不缓存答案 |
| Prompt Cache | Provider 能力 | v1 未启用；不能与 Context Cache 混称 |
| 长期记忆 | `memories` | 用户明确保存的稳定偏好，默认不自动提取 |
| 学习状态 | `learner_knowledge_states` 等 | 课程掌握事实，不复制到通用 Memory |
| RAG 知识 | 只读知识库与检索索引 | 当前任务证据，不写入长期记忆 |

## 上下文优先级与防污染

安全规则和当前明确输入始终优先于历史、记忆和 RAG。组装只读取同一用户、
同一会话；课程切换会排除旧课程消息，用户纠正被标记并优先保留。路由只获得
最近少量消息和结构化状态，完整历史不会进入本地确定性路由。星辰仅复用已有
安全文本映射，不添加未知 Flow 字段。

## Token 预算与压缩

配置集中在 `Settings` 和 `.env.example`。无 Provider 本地 tokenizer 时使用
`conservative_chars_div_2`，其结果是估算值。裁剪先移除重复和低相关旧消息，
再移除低优先记忆，并始终保留当前轮。达到消息或预算阈值时生成确定性摘要；
每个新版本保留覆盖范围、消息 ID、checksum 和结构化状态。摘要失败降级为未
压缩，不阻断回答。

## 安全与可观测性

学生消息 API 只返回 `user_visible` 消息。记忆 CRUD 和新会话管理 API 都按
`user_id` 隔离；当前部署尚未提供独立认证服务，因此生产环境必须由可信身份层
注入并校验该标识。消息和记忆写入会脱敏常见密钥、Bearer、电话、身份证和本机
绝对路径。`AgentRunModel.metrics_data` 只保存计数、估算 token、命中状态和延迟，
不保存完整上下文或记忆内容。

## 单实例边界

TaskExecutor 仍是进程内执行器。Redis Context Cache 不承担任务接管；Redis
不可用时退化为有界进程内 TTL。多实例任务租约、定时压缩、语义答案缓存和跨用户
共享记忆均不在本版本范围。
