# Safety and Governance

## Runtime safety

- Task creation remains non-blocking.
- Checkpoints, state versions, leases, recovery and idempotency are auditable.
- Cancel, retry, approval and user-input waits are explicit terminal/suspended states.
- SSE event sequence and reconnect behavior are regression-tested.

## Evidence safety

- RAG degradation, empty evidence, revoked material and citation failures remain visible.
- Invalid Provider JSON is locally validated and redacted from error details.
- Tool errors cannot silently become fabricated tool results.
- Synthetic, cached and real-provider evidence are labeled separately.

## Data and release safety

- No real keys, student privacy or raw local Provider YAML are included.
- No database migration or public API change is part of K.
- `SOLVER_CT v1.0` is frozen and not modified.
- No automatic merge, force push, production/canary activation or release tag is performed.

## Rollback

The RC consists of a normal commit on `agentic/phase-k-release-candidate`. Reviewers can revert that commit or delete the candidate branch; no destructive operation is required.
