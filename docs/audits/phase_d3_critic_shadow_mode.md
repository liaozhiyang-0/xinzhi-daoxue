# Phase D3：Critic Shadow Mode

## Shadow path

```text
Draft AgentResult ─────────→ existing Result Pipeline → Publish
        │                              │
        └→ ReflectionPolicy → Internal Critic → ReflectionTrace only
```

When enabled for an allowlisted capability, the Critic receives only the goal,
canonical workflow identity, draft fields, existing evidence references, tool
observations, and deterministic verification output. It cannot call a Tool,
write a checkpoint, publish a result, or mutate the original draft.

Critic failures are caught and recorded as `critic_failed`; the pre-existing
validation result remains usable. Any Critic evidence reference not present in
the existing evidence/tool packet is converted to `needs_review`, disables
revision, and increments `unsupported_critique_count`.

The trace records:

- `pass/revise/fail/needs_review`;
- issue types, severity, summary, grounded refs, and unsupported claims;
- Critic latency/tokens and worker failure;
- deterministic-vs-Critic disagreement;
- final shadow status.

## Initial scenario coverage

The policy and tests cover Academic Solver, Knowledge, and Research. Teaching is
supported by the same capability mapping and is only triggered when its existing
manual-review signal is present. The first implementation is provider-agnostic in
tests; real Provider evidence remains separately classified.

## D3 conclusion

`D3 = PASS` structurally. Shadow mode is observable and non-mutating. No revision
is enabled by default; D4 can only run when its explicit revision switch is on.
