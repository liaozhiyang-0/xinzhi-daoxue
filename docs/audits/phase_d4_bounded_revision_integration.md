# Phase D4：Bounded Revision Integration

## Revision gate

Revision is attempted only when all conditions hold:

1. `ReflectionPolicy` returns `critique`;
2. Critic returns `revise`;
3. Critic explicitly sets `revision_allowed=true`;
4. the configured revision canary is enabled;
5. `max_revision_count == 1`;
6. a re-verification callback is available.

Otherwise the result remains a shadow observation and the original answer is unchanged.

## Safety boundary

`ReflectionService._apply_revision` only accepts answer/business/structured fields outside
the immutable set. Citation IDs, evidence packets, knowledge hits, tool observations,
verification reports, quality gates, validation, and retrieval trace IDs cannot be replaced
by the model proposal. Evidence refs in the proposal must already exist in the original
packet.

After a changed draft, `RuntimeResultPipeline.reverify()` reuses the existing solver quality
gate, scenario contract, and Agent result validator. A failed re-verification is returned as
`revision_failed_closed`; the caller cannot commit it as a usable answer. Tool side effects
are not re-run by Reflection.

## Trace

The trace records original Critic output, revision proposal, revision count, change summary,
latency/tokens, and `revision_verified`, `revision_no_change`, or
`revision_failed_closed`.

## D4 conclusion

`D4 = PASS`. The implementation has a hard one-revision ceiling and a mandatory existing
verification callback; it does not create a second Runtime or checkpoint path.
