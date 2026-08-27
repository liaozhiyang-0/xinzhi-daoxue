# 10 Restart / Failure / Recovery 专项

8h 测试中至少：
5 cold restart
5 API restart

重启时禁止清 DB / Redis / MinIO / Qdrant。

有条件时模拟：
provider timeout
RAG unavailable
MinIO temporary failure
Redis reconnect
renderer error
artifact write failure
SSE disconnect
client refresh
expired lease
cancel race

每次恢复后检查：
production fingerprint
runtime generation
legacy counters
registry hash

legacy invocation 必须持续为 0。

技术故障不能造成：
无限 loading
空回答
旧回答覆盖新回答
重复答案
Circuit failure 拖垮 Solver

输出：
`docs/audit/76_restart_failure_recovery_report.md`
