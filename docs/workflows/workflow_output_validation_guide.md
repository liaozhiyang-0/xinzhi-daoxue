# 工作流输出校验与展示指南

`WorkflowOutputParserRegistry` 先把 JSON、固定行协议或允许的纯文本变成统一结构；`AgentResultValidatorRegistry` 再按 Agent 业务边界校验。HTTP 200、`task.completed` 或非空 token usage 都不等于回答可用。

| Agent | 关键校验 | Renderer 主要区域 |
|---|---|---|
| LEARN | status/course/intent、非空回答、引用必须属于本轮证据、复杂求解标记 misrouted | 正文、关键点、来源、图片、学习建议 |
| SOLVER_CT | 非空回答/final answer、单位或方向风险、图片识别失败、方法参考边界 | 摘要、方程、步骤、最终答案、假设、风险 |
| TEACH_01 | 目标、流程、活动、评价、课时和虚构教材来源 | 教学目标、先修、时间轴、例题、活动、评价、作业、备注 |
| TEACH_02 | 建议分范围、rubric 总和、无 rubric 不给正式成绩、不判作弊 | 建议分、评分点、正确项、错误、反馈、人工复核横幅 |
| RESEARCH_02 | 不新增 DOI/引用/实验，不把计划写成已完成，unsupported claims 结构 | 提纲、修改稿、说明、引用检查、无依据声明 |
| RESEARCH_03 | 无真实结果强制 plan，不生成 p 值/AUC/样本量/显著性，方法与变量边界 | 数据质量、方法、步骤、指标、解释、限制、复现要求；plan 横幅 |
| ROUTER_01 | 只接受可用目标 JSON，拒绝自身/Mock/未配置目标 | 仅 Debug 路由信息，不展示业务回答 |

统一校验输出包括 `validation_status`、`validation_issues`、`corrected_fields`、`response_usable` 和 `result_status`。结果状态为 accepted、accepted_with_warnings、fallback、misrouted、insufficient 或 failed。

降级遵循 AgentDefinition：LEARN 使用本地检索回答；备课使用明确标记的模板；批改进入人工复核且不产生正式成绩；科研任务返回边界清晰的复核或计划。不会把所有失败都降级到 LEARN。

空 `choices[0].delta.content` 必须抛出 `XingchenResponseParseError`。当前真实检查中 TEACH_01/02 正是此状态，Presentation 必须显示 fallback，不得显示“云端成功”。
