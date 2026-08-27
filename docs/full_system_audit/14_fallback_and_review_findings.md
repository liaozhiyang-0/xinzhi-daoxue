# Fallback、人工复核与发布边界

## 当前边界

配置和 readiness 已明确很多 Agent 处于 local/configured_unavailable，知识治理为 fallback_only，多数场景 production_ready=false；learning runtime 还缺 paired evidence 和 canary evidence；feedback loop disabled。系统内部对“demo 可用”和“生产可用”已有区分，但用户入口没有始终把这一区分说清楚。

## 失败时的 fallback

在简单问答任务中，运行完成后结果验证失败，系统返回失败而没有提供一个“低置信度但可用的最小回答”或清晰的补充信息问题；另一方面，RAG 无匹配仍返回候选。当前 fallback 的触发条件更像“组件不可用”，没有覆盖“结果不足、证据不适用、格式不满足”。

## 人工复核

课程证据和场景契约要求人工复核，这是正确的安全边界。但页面将“有资料支持”“尚无独立质量判定”“需要人工复核”放在同一层，未明确告诉用户：哪些内容可以直接学习、哪些仅是候选、哪些必须打开原文或由教师确认。

## 发布结论

在 P0 多轮失信、P1 入口分叉/路由错配/低相关检索/取消延迟未解决前，不建议对外发布。可以保留本地受控 demo，但应显著显示 local/demo/manual-review 状态，并限制未发布 Agent 的自然语言触达。
