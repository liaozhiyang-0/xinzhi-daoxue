# 多 Agent 兼容性报告

## 兼容结论

正式 `POST /api/v1/tasks` 请求模型未改必需字段；新结果字段均有默认值。LEARN 的九个星辰输入字符串与 JSON/固定行双协议继续覆盖；SOLVER 的 `AGENT_USER_INPUT`、`USER_INPUT_image` 和 frozen 工作流未修改。Debug RAG 原端点保留，仅新增 Agent 状态与 dry-run。

配置兼容加载器接受旧注册项并合成 v1 AgentDefinition；新配置在启动时严格校验。Router 中原 SOLVER 名称特判替换为配置项 `route_when_unconfigured`；CHECK→SOLVER 提示词改为 `fallback.instruction_prefix`；TaskRunner 中 LEARN 名称/`learning_qa` fallback 判断替换为 retrieval/fallback 配置；Provider 内 LEARN 解析迁移到 Parser Registry。

## 已执行回归

- Ruff format/check 与 Mypy：通过；140 个文件格式一致，69 个源码文件无类型错误。
- 完整 Pytest：131 passed、12 skipped、8 warnings；跳过项包含默认关闭的10项真实星辰测试。
- 配置校验与敏感文件扫描：通过；`git diff --check` 无空白错误。
- Agent runtime 契约、Registry、Router、TaskRunner、Provider、RAG 回归均通过。
- 最终代码重启后60条 RAG 连续三次：60/60、60/60、60/60。
- 最终三次 Top1代理率93.33%，Top3代理召回96.67%，跨课程证据率0；此前三轮测得Top1为95%，因此该代理指标存在少量并列排序波动，但不影响60条通过结果。
- `CT_012` 与 `DE_013` 均 route/top1/top3通过且无跨课程证据。
- Debug `/agents/status` 与 LEARN dry-run 实测成功，未返回凭据或Flow值。
- 显式设置 `RUN_REAL_XINGCHEN_TESTS=1` 后，LEARN CT、AE、DE、misrouted、空上下文及无效 Flow 共6项真实云端回归全部通过（6 passed）。
- SOLVER_CT 新增4项真实文字题回归：串联电阻、戴维宁等效、RC暂态、交流阻抗全部通过（4 passed，245.56秒）。
- SOLVER_CT 正式任务API端到端通过：`queued→completed`，Provider 47,673ms，本地检索307ms，答案2158字符，无fallback；事件顺序从 `task.created` 到 `task.completed` 完整。
- 补充Flow后再次执行60条RAG：60/60，检索p50/p95为275/491ms，本地总p50/p95为283/503ms；`CT_012`、`DE_013`继续通过。

真实测试只在 `RUN_REAL_XINGCHEN_TESTS=1` 显式开启；未开启时不得把本地契约测试描述为真实云端成功。

## 剩余兼容风险

旧 registry 字段仍存在，暂不删除；建议 schema v2 稳定一个版本后发 deprecation warning，再在下一主版本移除。SOLVER四题总耗时245.56秒（平均约61.39秒），正式API样例Provider耗时47.67秒，明显高于LEARN，应继续与本地1秒目标分开监控。并发4的CPU热路径接近1秒，应避免提高本地模型并发上限。
