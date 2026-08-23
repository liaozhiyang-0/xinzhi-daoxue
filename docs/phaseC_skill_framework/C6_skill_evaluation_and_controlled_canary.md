# Phase C6：Skill Evaluation 与 Controlled Canary

## 目标
验证 Skill Framework 是否改善能力选择和可审计性，再决定是否允许小范围接管。

## 指标
valid selection、empty selection、invalid/unregistered、prerequisite rejection、policy rejection、binding success、handler mismatch、plan compatibility、runtime failure、latency、token/cost、task outcome quality（真实 Provider 时）、rollback integrity。

## Evidence level
严格区分：
synthetic_provider_free / offline_real_case / real_provider_test / controlled_canary / production。

## Case 覆盖
- Academic Solver / CT 多题型
- Knowledge QA
- Teaching
- Research
- general/fallback 无 skill
- invalid skill injection
- missing prerequisite
- unavailable tool/worker
- resume with checkpointed skill version

## Controlled Canary
只有 evaluation GO 才能启用；allowlist、default OFF、rollback、先低风险、不自动扩大。

## Git
commit: `test(agent): validate phase C skill framework canary`
push 当前 Phase C 分支。

## 结束条件
形成 GO/NO-GO 后停止，不自动执行后续清理。
