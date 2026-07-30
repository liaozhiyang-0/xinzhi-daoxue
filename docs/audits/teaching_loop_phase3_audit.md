# 教学闭环第三阶段实施前审计

审计日期：2026-07-26

审计范围包括 `LearningInteractionModel`、`PracticeAttemptModel`、
`LearnerKnowledgeStateModel`、`WrongAnswerRecordModel`、
`ConversationMessageModel`、`SessionWorkingState`、`LearningLoopService`、
`StudentAnswerReviewService`、`PracticeGenerationService`、`TeachingStateV1`
和 `config/learning_mastery.yaml`。本审计只描述实施前状态。

## 结论

第三阶段选择增量扩展现有 `PracticeAttemptModel`，不新增职责重复的
`StudentAttemptModel` 表。`practice_attempts` 已保存来源任务、用户、课程、
题目、参考答案、学生答案、复核结果和状态，语义上已经是现有唯一的学生练习
尝试实体。新增版本、会话、教学状态和验证字段后，可以同时兼容旧的“已生成但
未提交”变式题记录和新的正式提交记录。

数据库只需扩展 `practice_attempts` 并新增 `retest_plans`，使用一份增量
Alembic migration。`LearnerKnowledgeStateModel` 继续作为唯一掌握状态事实
来源；反馈采用结果和掌握证据保存在 Attempt 的结构化 JSON 中。

## 八项审计问题

1. **`PracticeAttemptModel` 能否安全扩展**

   可以。它已经具备 `source_task_id`、`user_id`、`course_id`、
   `student_answer`、`review_result`、`status` 和时间字段。新增可空的
   `session_id`、`task_id`、`attempt_sequence`、`revision_of_attempt_id`、
   结构化步骤、教学模式、提示、披露、验证、反馈采用、掌握证据和幂等字段，
   不会改变旧记录含义。旧变式题记录的序号保持为空，新提交才参与版本唯一约束。

2. **`LearningInteractionModel` 当前保存什么**

   它保存来源任务、用户、动作、用户级幂等键、动作 payload、完整动作响应和
   创建时间。第一阶段动作保存学生答案、错题、提示、变式题和关联知识请求；
   第二阶段动作保存 `request_more_hint`、`submit_check_response`、
   `switch_to_direct_answer` 的教学结果，其中可包含提示层级、验证摘要、披露
   状态和下一步检查。它没有稳定的 Attempt 修订关系。

3. **是否已有 Attempt 序号、修订关系或耗时字段**

   `PracticeAttemptModel` 没有 Attempt 序号、修订外键、更新时间或提交耗时。
   `ConversationMessageModel` 有独立的消息序号、消息修订关系和时间戳，但消息
   版本不能替代 Attempt 版本。`LearningInteractionModel` 只有创建时间。

4. **当前 mastery 更新入口**

   唯一持久化入口是 `LearningLoopService._update_points`，它更新
   `LearnerKnowledgeStateModel` 的分数、置信度、计数和最后证据摘要。
   `StudentAnswerReviewService` 会计算复核结果和建议 delta，但持久化仍由
   `LearningLoopService` 根据配置执行。`WrongAnswerRecordModel` 只保存更新
   前后快照，不是 mastery 事实来源。

5. **哪些动作会直接修改 mastery**

   `check_answer`、`add_wrong_answer`、`mark_mastered` 和 `get_hint` 会直接
   调用 `_update_points`。`generate_variant`、`related_knowledge` 以及第二
   阶段的提示、理解检查和切换直接答案动作不会直接更新 mastery。第三阶段需要
   将新 Attempt 结果统一交给 `LearningOutcomeService`，避免在 TaskRunner 中
   出现 delta 规则。

6. **是否可以只增加一张 Attempt 表和一张 RetestPlan 表**

   无需新增 Attempt 表。扩展现有 `practice_attempts`，再新增
   `retest_plans` 即可，因此最终仍只有一个 Attempt 实体和一个新增表。反馈
   采用和掌握证据使用 JSON 字段，不需要第三张事件表。

7. **是否存在重复的反馈采用实现**

   不存在。现有 `StudentAnswerReviewService` 比较一次学生答案与参考答案，
   `StudentVerificationService` 对单次 Attempt 做有限验证；二者都不比较前后
   Attempt，也没有 `FeedbackUptake` 状态。因此新增本地规则服务不会重复已有
   职责。

8. **当前用户隔离如何完成**

   学习动作先用 `source_task_id` 读取任务并核对 `task.user_id`；动作幂等约束
   是 `(user_id, idempotency_key)`；掌握状态查询按 `user_id` 过滤；各学习表
   都保存 `user_id`。当前 API 的身份仍由调用方显式提交 `user_id`，尚无正式
   RBAC。第三阶段所有 Attempt、修订和 Retest 查询必须同时带用户过滤，并在
   关联前再次核对任务、会话和前一 Attempt 的所有权。

## 其他边界

- `SessionWorkingState` 和 `TeachingStateV1` 是短期会话状态，不是长期学习
  记录；只能保存 Attempt ID、序号和待复习 ID。
- `ConversationMessageModel` 可以关联正式提交的消息，但不保存内部答案键或
  完整验证报告。
- `PracticeGenerationService` 目前仅能确定性生成有限的 CT 电路变式，不能
  静默生成未来再测题。
- `config/learning_mastery.yaml` 实施前是版本 1 的统一 delta 配置，没有按
  提示层级、完整答案披露、反馈采用或延迟再测区分，也没有显式上下限与
  “未经统计校准”声明。
- 现有实现没有后台 scheduler、主动通知或 FeedbackUptake 模型调用。
