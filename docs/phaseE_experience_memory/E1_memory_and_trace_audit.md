# Phase E1：Memory / Trace / Evaluation 现状审计

## 目标
梳理所有现有“记忆/状态/轨迹”，避免 Experience Memory 成为新的事实源冲突。

## 至少审计
- Session context
- Working State
- Learning State
- MemoryService / active memories
- Task / AgentRun
- Runtime checkpoint
- TraceStore / ModelTracer
- EvaluationCase / EvaluationRunner / reports
- Planner trace
- Skill trace
- ReflectionTrace
- post-processing summary / research ingestion

## 输出分类
每个现有对象标记：
- SOURCE OF EXPERIENCE
- USER MEMORY ONLY
- EXECUTION STATE ONLY
- LEARNING STATE ONLY
- AUDIT ONLY
- NOT ELIGIBLE FOR EXPERIENCE

## 必须回答
1. 哪些 trace 能产生 Experience candidate？
2. 哪些字段包含用户隐私？
3. 哪些字段必须脱敏/摘要？
4. 哪些 evidence level 可以进入 validated？
5. 哪些来源永远不能自动 promotion？
6. 当前 MemoryService 是否应该保持完全独立？

## 原则
- MemoryService 保持用户显式长期记忆；
- Learning State 保持学生掌握度；
- Trace/Evaluation/Reflection 成为 Experience source；
- Experience Memory 不覆盖任何现有 owner。

## 本阶段不 commit
完成后继续 E2。
