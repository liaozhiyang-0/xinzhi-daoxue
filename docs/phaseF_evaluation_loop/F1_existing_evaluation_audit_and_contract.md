# Phase F1：现有 Evaluation 审计与统一 Contract

## 目标
复用现有评测基础设施，禁止创建第二套 Evaluation Framework。

## 至少审计
- EvaluationCase / EvaluationRunner / EvaluationScorer / SuiteReport
- circuit theory / 336-case evaluation
- planner shadow evaluation
- skill evaluation
- reflection evaluation
- experience evaluation
- model-evaluation workflow
- benchmark scripts
- Task/Runtime trace
- failure/error code
- cost/latency metrics

## 输出分类
AUTHORITATIVE / REUSE / ADAPT / MERGE / FREEZE / REMOVE LATER

## 统一 EvaluationRecord
至少包含：
```text
evaluation_id
suite_id
case_id
evidence_level
task_family
course
capability
expected_outcome
actual_outcome
score_dimensions
overall_score
failure_stage
failure_codes
task_id
run_id
trace_ids
planner_version
plan_version
skill_versions
tool_versions
model/provider version
reflection_version
experience_ids
latency
tokens
cost
reproducible
baseline_id
candidate_id
```

旧报告通过 adapter 接入，不一次性重写全部 runner。

## 本阶段不 commit
完成后继续 F2。
