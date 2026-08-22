# Failure-driven Optimization

The completed loop is:

```text
trace/evaluation
  -> failure taxonomy
  -> attributable pattern
  -> minimal proposal
  -> offline replay
  -> targeted regression
  -> governance decision
```

## Accepted optimization

Phase H pattern P02 found two AE bias cases failing because an existing `operating_region` verification rule was not represented in the generated solution-step contract. Phase I added that course-pack-level step composition, replayed both cases serially, and ran the regression matrix. No scorer threshold, answer fixture, Provider setting, API, Planner, Skill Registry or Runtime contract was changed.

## Explicitly not optimized

The three DE `disabled_tool` cases were declared negative fixtures and were not special-cased. Timeouts, routing failures and unknown failures were not hidden by increasing timeouts, deleting cases or changing scoring. This preserves the integrity of the failure loop.

## Promotion rule

Any future candidate must include the failure evidence, minimal diff, same-case replay, regression result, cost/safety review and human/policy approval before promotion.
