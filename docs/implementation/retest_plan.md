# RetestPlan

`retest_plans` 保存延迟再测计划，唯一约束为
`(user_id, skill_id, source_task_id, interval_days)`。主要索引覆盖
`(user_id, status, due_at)`、`(skill_id, due_at)` 和来源 Task。

默认配置规则：

- 查看完整答案：1 天、7 天；
- H2 后正确：7 天；
- 独立正确：28 天；
- 延迟再测错误：1 天。

`GET /api/v1/learning/retests?status=due` 在用户打开 Workspace 时查询
`due_at <= now`。没有后台 scheduler、邮件、短信、推送或通知承诺。

用户点击“开始复习”才调用现有 `PracticeGenerationService`。CT/AE/DE 是
当前正式支持范围；可确定性生成时返回变式题，否则返回受控微测请求，由前端
通过普通 `/api/v1/tasks` 任务链提交。RetestPlan 本身不是执行链，也不是主动
通知系统。
