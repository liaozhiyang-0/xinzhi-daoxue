# MasteryEvidence 与学习进度估计

`LearningOutcomeService` 将 Attempt、VerificationReport、FeedbackUptake、
提示层级和完整答案披露状态转换为 `MasteryEvidenceV1`，再更新现有唯一的
`LearnerKnowledgeStateModel`。

证据优先级保护以下边界：

- 延迟再测结果使用专用证据；
- 查看完整答案只产生零增量证据并安排再测；
- `manual_review` 增量为零；
- 正确修订可产生有限的 feedback 证据；
- 独立正确、H0/H1 后正确、H2 后正确使用递减增量；
- 已验证错误和未采用反馈使用配置化负增量；
- 失败、取消、跨用户或缺少稳定 skill ID 时不产生正向证据。

证据摘要保存在 Attempt 和 LearnerKnowledgeState 的 JSON 历史中，不新增
第二张 mastery 表。配置值未经统计校准，因此 API 和前端统一称为“学习进度
估计”，不得称为真实掌握概率、能力概率、考试成绩或正式能力评价。
