# 教学闭环第二阶段架构

第二阶段在唯一任务链上增加有限诊断与分级辅导：

```text
POST /api/v1/tasks
→ TaskCreationService / TaskExecutor / TaskRunner
→ ACADEMIC_PROBLEM_SOLVER
→ SolutionPacketV1
→ TeachingExecutionPlanner
→ StudentVerification（check）
→ HintPolicy + NextCheckQuestion（guided/check）
→ AnswerDisclosure
→ TaskPresentation / SSE / History
```

`direct_answer`、`guided_learning`、`check_my_work` 正式可用；`review`
仍为 `foundation_only`。教学服务是既有求解结果的适配与过滤层，不创建第二个
TaskRunner、Session、Memory、路由器或 Solver。`SOLVER_CT_V1` 保持冻结。

`direct_answer` 不执行学生核对或提示策略，额外模型调用为 0。学习与检查模式在
后台保留完整 `SolutionPacketV1`，学生可见结果必须先经过后端披露过滤。
`POST /api/v1/learning/actions` 在同一源 Task 上处理继续提示、提交小步回答和切换
完整解答；切换时复用受保护标准解，不重复运行 Solver。

`TeachingStateV1` 只保存模式、标准解/核对报告引用、提示等级、待回答问题和披露
状态。它不保存 StudentAttempt 全文、教材全文、掌握度或未验证模型猜测。刷新由
会话消息、源 Task 和 WorkingState 恢复，不重新生成提示。

安全边界：

- `VerificationReportV1` 不是全题型首错系统；
- 只有确定性确认时才设置 `first_confirmed_error_step`；
- `manual_review` 表示超出有限规则范围，不表示学生答错；
- H0—H2 是受控模板提示，不是完整教学策略；
- 普通任务查询不返回内部答案键，跨用户查询返回不可见；
- 学生端不展示内部指标、Provider、Agent ID 或完整调试包。
