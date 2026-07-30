# StudentAttempt 多版本记录

现有 `practice_attempts` 被增量升级为唯一 Attempt 实体。旧的变式题记录保留
`attempt_sequence = NULL`；正式提交使用 `StudentAttemptV2`：

- 第一次提交序号为 1，修订来源为空；
- 修订序号递增并指向前一 Attempt；
- 旧版本标记 `superseded`，不覆盖或删除；
- `(source_task_id, attempt_sequence)` 保证题内序号唯一；
- `(user_id, idempotency_key)` 防止重试重复创建；
- 用户、Session、来源 Task 和前一 Attempt 在关联前同时校验；
- 取消任务只能产生 `cancelled` Attempt，不能产生 verified Attempt。

只读 API 是：

```text
GET /api/v1/learning/attempts
GET /api/v1/learning/attempts/{attempt_id}
```

二者要求 `user_id`、支持分页并按用户过滤。公开合同不返回
`verification_report_json`、参考答案或内部答案键。
