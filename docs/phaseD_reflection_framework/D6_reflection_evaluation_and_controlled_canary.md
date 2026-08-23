# Phase D6：Reflection Evaluation 与 Controlled Canary

## 目标
证明 Reflection 不只是多一次模型调用，而是真正提高结果质量且成本可控。

## Evidence Levels
严格区分：
`synthetic_provider_free` / `offline_real_case` / `real_provider_test` / `controlled_canary` / `production`。

不得仅凭 synthetic tests 宣称 Reflection 提升真实答案质量。

## 指标

### Critic
issue detection precision/recall（有标注时）、false positive、unsupported critique、evidence grounding、critic/verifier disagreement。

### Revision
attempted rate、success rate、improvement rate、no-change、degradation、new-error introduction、verification pass before/after。

### 成本
added latency、model calls、token/cost、timeout/error、fallback。

### 稳定性
checkpoint/resume、rollback、SSE/event order、terminal consistency、no duplicate side effects。

## Case 覆盖
- CT 数值/符号错误
- CT 推导遗漏
- CT 正确答案（防过度修正）
- Knowledge 有证据/不足/citation mismatch
- Research unsupported claim/conflicting evidence
- Teaching factual error vs style difference
- Tool result conflict
- Critic timeout/failure
- Revision failure
- resume after critic/revision checkpoint

## 真实质量要求
资源允许时，至少用一小组真实 Provider 或历史真实失败案例验证。
若无法运行真实 Provider，只能给结构性 `CONDITIONAL_GO/NO-GO`，不得宣称真实质量提升。

## GO 条件
- critical deterministic regression = 0
- duplicate side effect = 0
- unsupported critique 在可接受范围
- revision degradation 有明确上限
- 有实际 improvement evidence
- latency/cost 在预算内
- rollback/resume 完整

具体阈值由 Codex 根据现有 benchmark 规模提出并记录，不得为了 GO 临时降低。

## Canary
仅在 GO 时：default OFF、allowlist、低风险优先、rollback、automatic expansion=false。

## 提交
本阶段不 commit，完成后继续 D7。
