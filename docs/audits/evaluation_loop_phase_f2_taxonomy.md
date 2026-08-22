# Phase F2：Trace-level Scoring 与 Failure Taxonomy

## 统一失败阶段

`LoopFailureStage` 统一为：

```text
input / routing / planner / skill_selection / tool / rag /
model_generation / reflection / verification / governance / runtime /
infrastructure / fixture / unknown
```

旧 `EvaluationResult.failure_stage` 通过显式映射接入；无法证明时保留 `unknown`，不依靠猜测补齐阶段。

## FailureRecord

`FailureRecord` 记录 failure ID、evaluation/case、stage、owner component、error codes、severity、observed evidence、expected/actual behavior、reproducibility、confidence、上下游影响、版本上下文、trace/evaluation evidence refs 和聚合维度。

`FailureAttributor` 当前是 deterministic rules：显式 stage 优先，其次依据 error code/status 推断，并把推断信号与 confidence 写入记录。没有 evidence 时 owner 为 `unknown`，confidence 降低。

## 评分

现有 Scorer 的 `dimension_scores` 原样进入 `score_dimensions`，不改变现有权重或阈值。Academic、Knowledge、Research、Teaching 的领域维度继续由现有 case rubric/scorer 提供；system 维度由 actual metadata 和 failure stage 表示。未观测维度不补分，保持缺失/unknown 语义。

## F2 结论

“答案错误”现在可以定位到最早可观察的组件失败阶段；F2 完成。
