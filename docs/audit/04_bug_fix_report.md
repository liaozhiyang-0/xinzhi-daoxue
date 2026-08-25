# 芯智导学问题修复报告

## 1. 修复原则

只修改已证实的共享根因，不引入 React/Vite，不改数据库 migration，不重写 Runtime；前端继续使用当前静态工作台和既有 KaTeX 资源。

## 2. 代码变更

| 文件 | 变更 |
|---|---|
| `apps/api/app/services/agent_runtime.py` | 图片检索仅由显式 `include_images=true` 或真实图片输入触发；显式 `false` 继续覆盖默认策略 |
| `apps/api/app/core/config.py`、`.env.example` | 图片模型预热改为默认关闭，文本模型仍按既有延迟/预热配置工作 |
| `apps/api/app/bootstrap/runtime_task_engine.py` | Knowledge QA Runtime 复用已注册 `AgentRegistry` |
| `apps/api/app/services/knowledge_qa_runtime.py` | 根据 Agent 定义生成节点超时；校验节点取 Agent 超时与 30 秒的较小值 |
| `apps/api/app/runtime/executor.py` | 超时错误映射为稳定错误码 `runtime_node_timeout` |
| `apps/api/app/static/debug/ui-core.js` | 增加行内富文本/公式渲染入口；过滤孤立 `\\]`、`\\)`、`$$`，避免资料卡片出现残留闭合符 |
| `apps/api/app/static/debug/workspace.js` | 资料摘要恢复统一 LaTeX 渲染；资料标题支持行内公式 |
| `apps/api/app/static/debug/workspace-v2.css` | 移除资料摘要 7.2em 截断和论文摘要 5 行截断，保留面板滚动 |
| `apps/api/app/static/debug/workspace.html` | 更新静态资源版本号，避免浏览器继续使用旧脚本/CSS |
| `apps/api/tests/*` | 添加图片路由、Agent 超时、终态收敛、默认配置和前端契约回归测试 |

## 3. 重启证据

通过项目自带 `scripts/xzd_supervisor.ps1` 完成安全停止和启动，未使用强制清理或改动数据卷。

- `/api/v1/health`：HTTP 200；database、Redis、MinIO 均为 `ok`。
- `/workspace`、`/student`：HTTP 200。
- 重启后知识服务先短暂显示文本模型未加载，约 20 秒后恢复 `rag_status=ready`。
- 最终文本模型加载成功，图片模型保持 `image_model_loaded=false`，符合“普通文本不预热图片模型”的目标。
- 文本向量数 27101，图片向量数 3309，Qdrant 连接正常。

## 4. 浏览器验收结果

在重启后的 `/workspace` 实际页面中验证：

- 历史会话列表可打开；带图片的电路题历史消息显示“题目原图 1”。
- 科研检索历史任务显示 6 张外部论文资料卡片，标题、作者、日期、摘要和标识均在右侧卡片内呈现。
- 公式资料卡片中 KaTeX 节点正常，孤立 `\\]` 不再出现，公式失败回退数量为 0。
- 资料标题中的 `\\(RC\\)` 已编译为公式，不再直接显示原始分隔符。
