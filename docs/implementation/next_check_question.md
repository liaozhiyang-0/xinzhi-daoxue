# NextCheckQuestion V1

第二阶段每轮只生成一个理解检查问题。生成优先使用已确认错误对应的错因/技能，
否则把 `SolutionPacketV1` 的下一步骤转换为问题。公开合同包含问题 ID、文本、
目标 skill、目标 step、回答类型和来源。

`answer_key_internal` 不返回学生端，也不进入普通 ConversationMessage 文本；它只
随受保护任务内部数据保存。提交回答使用既有
`POST /api/v1/learning/actions` 的 `submit_check_response`，在有限规则范围内更新
同一个 Verification/Hint/Question 状态，不生成整套测验、不更新 mastery，也不
安排延迟再测。
