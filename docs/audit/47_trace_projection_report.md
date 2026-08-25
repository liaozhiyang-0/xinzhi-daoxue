# H1 Trace Projection 验收报告

## 范围

H1 只增加现有 TraceStore 与 ModelTracer 的只读投影，并通过原有
`GET /api/v1/debug/traces/{trace_id}` 返回 `projection`。没有修改 TaskEvent、
Checkpoint、Runtime 调度或 Provider 调用链。

投影包含 ingress、planning、retrieval、model、tool、verification、presentation
七类 span，提供统一的时间、状态、Provider、Tool 和脱敏摘要字段。敏感键和疑似
Token 不进入投影摘要。

## 自动验证

| 检查 | 结果 |
|---|---:|
| H1 target tests（trace projection、observability、orchestration） | 7 passed |
| 六场景路由/受控 Planner smoke | 21 passed |
| 老工作台学生端与统一页面回归 | 35 passed |
| Ruff（H1 文件） | passed |
| compileall（H1 Python 文件） | passed |
| Mypy | 未通过环境检查：项目配置为 Python 3.11，当前虚拟环境为 Python 3.13，NumPy stub 使用了 3.12+ `type` 语法 |

## 浏览器验证

在当前运行的老工作台 `/workspace` 完成了文字题加载/提交路径和图片材料路径检查。
图片上传返回 `201 Created`，使用版本化附件契约后任务创建返回 `202 Accepted`，页面进入
“正在理解你的需求”执行状态，不再出现 422 参数校验错误。

对照日志显示，旧缓存脚本的请求顺序为 `POST /api/v1/files 201` →
`POST /api/v1/tasks 422`；更新后的请求顺序为 `POST /api/v1/files 201` →
`POST /api/v1/tasks 202`。老工作台入口和附件模块已增加版本查询参数，避免继续命中旧
浏览器模块缓存。

当前 `.env` 使用真实本地模型执行路径，模型任务可能长时间处于执行中；本报告只验收
H1 的页面加载、附件提交和接口边界，不把模型最终答案耗时描述为 H1 通过条件。

## 结论

H1 代码验收通过。需要注意的剩余环境风险是：真实本地模型调用期间，单进程 local
executor 可能使 `/health` 变慢；这属于既有 Runtime 执行隔离问题，不是 TraceProjection
引入的问题，也未在 H1 中扩大修复范围。
