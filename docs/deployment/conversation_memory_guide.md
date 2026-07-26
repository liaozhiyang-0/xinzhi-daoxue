# 会话与长期记忆部署指南

## 配置

复制 `.env.example` 后按 Provider 上下文窗口设置：

```env
CONTEXT_MAX_INPUT_TOKENS=16000
CONTEXT_RESERVED_OUTPUT_TOKENS=4096
CONTEXT_COMPACTION_TRIGGER_RATIO=0.70
CONTEXT_RECENT_MESSAGE_LIMIT=12
CONTEXT_RELEVANT_OLDER_LIMIT=6
CONTEXT_MEMORY_LIMIT=8
CONTEXT_SUMMARY_TARGET_TOKENS=1200
CONTEXT_SUMMARY_MESSAGE_TRIGGER=24
CONTEXT_CACHE_TTL_SECONDS=300
CONTEXT_CACHE_MAX_ENTRIES=256
CONTEXT_CONFIG_VERSION=conversation-v1
```

这些 token 是保守估算值。修改选择或裁剪规则时递增
`CONTEXT_CONFIG_VERSION`，使旧 Context Cache 自动失效。Redis 是首选缓存；
连接失败会自动使用进程内有界 TTL，主任务不应因此失败。

## 数据库升级

```powershell
Set-Location apps\api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
```

新增 migration `20260723_0006_agent_runtime_foundation.py`。它只追加表、字段、
索引与约束，不修改旧 migration。升级前按现有数据库运维流程备份 PostgreSQL；
SQLite 的升级—降级—升级由专项测试覆盖。

## 产品默认值

- `memory_enabled=true`：允许用户显式“记住”、手动添加和召回；
- `auto_memory_enabled=false`：不会从普通聊天自动写入长期记忆；
- `context_compaction_enabled=true`：仅在阈值触发时做确定性压缩；
- 星辰工作流授权策略不因历史或记忆而改变。

Workspace 的记忆面板可关闭召回、查看来源、添加和软删除记忆。删除后记忆立即
退出 active 召回；恢复 API 可撤销软删除。关闭记忆不会删除已有记录。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_agent_runtime_foundation.py apps/api/tests/test_migrations.py -q
.\.venv\Scripts\python.exe -m ruff check apps/api/app apps/api/tests
.\.venv\Scripts\python.exe -m mypy apps/api/app
.\.venv\Scripts\python.exe scripts\export_openapi.py
```

在 `/workspace` 验证刷新后消息恢复、会话搜索/归档/恢复和记忆 CRUD；在
`/debug/execution/{task_id}` 验证上下文估算、预算、缓存后端和延迟瀑布。
测试数据必须是虚构数据，不执行真实付费调用。

## 运维限制

当前用户隔离依赖请求中的 `user_id`；公网部署前必须接入可信认证层，禁止接受
客户端任意声明身份。Context Cache 不是答案缓存，也不是 Provider Prompt Cache。
本版本不会主动联系学生、不会跨用户共享记忆，也不会把教材/RAG 内容写入记忆。
