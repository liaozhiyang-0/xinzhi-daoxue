# Phase F2：Trace-level Scoring 与 Failure Taxonomy

## 目标
让“答案错了”变成可定位的组件失败。

## 统一失败阶段
```text
input
routing
planner
skill_selection
tool
rag
model_generation
reflection
verification
governance
runtime
infrastructure
fixture
unknown
```

## FailureRecord
至少包含：
```text
failure_id
evaluation_id
case_id
stage
owner_component
error_codes
severity
observed_evidence
expected_behavior
actual_behavior
reproducible
confidence
upstream_dependencies
downstream_effects
version_context
```

## 评分
Academic Solver：correctness、derivation completeness、numerical/unit correctness、tool agreement、answer usability。
Knowledge：factuality、evidence grounding、citation validity、completeness。
Research：source quality、evidence synthesis、unsupported claims、citation/provenance。
Teaching：factual correctness、pedagogical structure、requirement coverage。
系统维度：routing、plan validity、skill/tool selection、latency、cost、recovery、safety。

证据不足时必须使用 `unknown`，禁止硬猜。

## 本阶段不 commit
完成后继续 F3。
