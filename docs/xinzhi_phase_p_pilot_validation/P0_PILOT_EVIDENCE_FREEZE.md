# P0：Pilot 0 证据冻结

## 目标
冻结组员真实测试数据，避免边修边污染证据。

## 每次任务至少记录
```text
pilot_user_id（匿名）
session_id
task_id
timestamp
scenario
course
input_mode
input_summary
attachment_count
planner_result
capability
skills
rag_used
tool_used
reflection_used
task_status
latency
review_score
user_feedback
failure_code
```

## 隐私
使用 `PILOT-U01` 等匿名编号。
不要记录学号、手机号、QQ、私人账号等无关敏感信息。

## 测试者建议
- 学生视角
- 教师/助教视角
- 技术组员
- 不熟悉项目的组员

## 输出
- `evaluation/pilot0/`
- `docs/pilot/pilot0_summary.md`
- `docs/pilot/pilot0_case_manifest.md`

P0 完成前不进行大规模优化。
