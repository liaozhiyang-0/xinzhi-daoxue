# Phase D6：Reflection Evaluation & Controlled Canary

## Evidence policy

The evaluator supports `synthetic_provider_free`, `offline_real_case`,
`real_provider_test`, `controlled_canary`, and `production`. A provider-free report is
never presented as real answer-quality improvement; its decision is at most
`CONDITIONAL_GO`.

## Metrics

`ReflectionEvaluationService` records:

- Critic precision, recall, false-positive rate, unsupported-critique rate, and
  Critic/verifier disagreement;
- revision attempted/success/no-change/improvement/degradation/new-error rates;
- verification pass before/after revision;
- added latency, Critic/revision token counts, and model-call proxies;
- checkpoint/resume, rollback, event order, and duplicate side effects.

The evaluator requires zero critical deterministic regressions and duplicate side effects,
unsupported critique rate at most 5%, degradation rate at most 2%, stable resume/event order,
rollback integrity, and at least one observed improvement. Provider-free evidence remains
`CONDITIONAL_GO`; real Provider or offline real-case evidence is required for `GO`.

## Case matrix

The tests cover:

| Capability | Cases |
| --- | --- |
| Academic Solver | numeric/symbol error, derivation gap, correct answer/no over-correction |
| Knowledge | supported evidence, insufficient evidence, citation mismatch candidate |
| Research | unsupported claim/conflicting evidence, Critic timeout/failure |
| Teaching | factual-risk review vs style difference |
| Runtime safety | revision failure, checkpoint/resume, event order, duplicate side effect count |

## Canary

`ReflectionControlledCanary` is policy-only and default OFF. Approval requires a real `GO`
report, explicit capability allowlist, rollback enabled, and automatic expansion disabled.
Rollback returns a non-active decision and does not mutate Runtime, checkpoint, task, or Agent
state.

## D6 conclusion

`D6 = PASS` for the provider-free evaluation/control structure. Current evidence is
`CONDITIONAL_GO`, not a claim of real Provider quality improvement; no production canary is
enabled.
