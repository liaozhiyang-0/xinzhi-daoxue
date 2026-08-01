# 教学闭环基础能力第一阶段

第一阶段在既有 `POST /api/v1/tasks`、TaskRunner、`ACADEMIC_PROBLEM_SOLVER`、
RAG、会话消息和 SSE 链路上增加教学元数据，不建立第二套任务或求解系统。
`SOLVER_CT_V1` 仍是冻结的云端基线与回退，本阶段没有修改它。

## 执行位置

1. `TaskCreationService` 规范化 `options.teaching_mode` 和
   `options.student_attempt`，旧请求默认 `direct_answer`。
2. TaskRunner 完成既有路由、求解、检索和质量门后，
   `TeachingFoundationService` 只读适配已有结果。
3. `SolutionPacketAdapter`、`EvidencePacketAdapter` 和 `SkillRegistry` 生成
   教学结构；`check_my_work` 复用现有答案检查器。
4. 同一任务结果、助手消息和会话短期 `TeachingStateV1` 保存结构化输出，
   不修改长期 Memory 或 mastery。

第一阶段新增服务不得调用模型、Provider、Solver 或检索器。因此显式
`direct_answer` 与未传教学参数的旧请求具有相同的模型调用次数和原始答案链路。

## 可用范围

- 正式技能配置和错因模板只覆盖 CT、AE、DE。
- Workspace 当前开放“直接解答”和“检查我的解答”。
- `guided_learning`、`review` 已有后端合同，但返回 `foundation_only` 与清晰提示；
  第一阶段不声称已实现完整逐级提示、苏格拉底对话或复习编排。
- 未知课程、未知题型、缺少结构化步骤或缺少检索证据时返回 `partial` 或
  `unavailable`，不得猜测映射或来源。

## 数据与安全边界

`student_attempt` 属于当前任务和短期会话状态，可进入任务 options 与会话消息，
但不自动写入长期 Memory、错题本或 mastery。证据包只保留既有检索命中的有界
摘录，不复制原始教材，不记录凭据、完整 prompt 或学生隐私。所有教学调试字段
仍经过既有调试接口的脱敏规则。

## 可观测性

`RunMetrics` 新增解题包、证据包、技能映射、错因查找耗时，以及
`student_attempt_present`、`teaching_mode`。这些指标衡量适配层开销，不代表
学科答案质量或教学效果。
