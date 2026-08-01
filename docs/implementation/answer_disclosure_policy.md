# AnswerDisclosurePolicy V1

后端 `AnswerDisclosureService` 在 TaskPresentation 前强制执行披露：

| 模式 | 策略 | 最终答案 | 完整标准解 |
|---|---|---:|---:|
| `direct_answer` | `full` | 显示 | 显示 |
| `guided_learning` | `next_step_only` | 隐藏 | 隐藏 |
| `check_my_work` | `withhold_final` | 隐藏 | 隐藏 |

过滤同时作用于回答正文、`answer_text`、`math_content`、`solution_packet`、
`final_answer`、中间结果、工具产物和普通消息数据。完整答案只保存在任务内部
`_teaching_internal`，普通任务 API 永不返回该键；没有当前用户标识的查询还会
移除学生核对报告。

用户主动执行 `switch_to_direct_answer` 后，服务从内部包恢复已有完整答案，并把
`solution_packet_reused=true`、`full_solution_disclosed=true` 写入状态和指标，
不再次运行 Solver。
