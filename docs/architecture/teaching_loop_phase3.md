# 教学闭环第三阶段架构

第三阶段在现有任务链和第二阶段有限诊断之上增加本地学习记录，不创建第二个
TaskRunner、教学 Session 或 mastery 系统。

```text
POST /api/v1/tasks
→ TaskRunner
→ SolutionPacketV1
→ StudentVerificationService
→ PracticeAttemptModel（StudentAttemptV2）
→ FeedbackUptakeService
→ LearningOutcomeService
→ LearnerKnowledgeStateModel
→ RetestPlanModel
```

初次 `check_my_work` 的显式 StudentAttempt 由 TaskRunner 交给
`LearningOutcomeService`；TaskRunner 不包含 mastery delta 规则。后续
`submit_attempt_revision`、`start_retest`、`complete_retest` 和
`dismiss_retest` 继续走 `POST /api/v1/learning/actions`。

Attempt 全文只存在 `practice_attempts`。TeachingState 只保留当前/前一
Attempt ID、序号、最近反馈采用状态、最近证据类型和待复习计划 ID；
LearnerKnowledgeState 只保留分数、计数和结构化证据摘要；Memory 不接收
Attempt 全文。

所有第三阶段计算均在本地完成：Attempt diff 使用规范化文本和步骤 ID，
反馈采用复用有限 VerificationReport，mastery 使用版本化 YAML 配置，
RetestPlan 使用数据库时间查询。没有新增模型调用、scheduler、队列或主动通知。

`FeedbackUptake` 不等于真实理解，`MasteryEvidence` 是启发式证据，
`LearnerKnowledgeState` 不是考试成绩，完整答案披露不等于掌握，
`manual_review` 不产生 mastery 增量。
