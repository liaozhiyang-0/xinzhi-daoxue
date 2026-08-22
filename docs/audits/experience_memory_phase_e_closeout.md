# Phase E：Experience Memory Closeout

## Architecture and lifecycle

```text
Trace / Evaluation / Reflection / verified Run
                    │
                    ▼
          ExperienceCandidate writer
       (schema + privacy + redaction)
                    │ candidate
                    ▼
       replay / regression / conflict review
                    │
          validated → approved → active
                    │
                    ▼                         │ expiry/deprecate/forget
          ExperienceRecord (single store) ◄───┘
                    │ active only
                    ▼
        deterministic ExperienceRetriever
                    │ bounded ExperienceMatch
                    ▼
      Planner shadow / optional bounded prior
                    │
                    ▼
 Registry → SkillPolicy → ToolPolicy → Runtime
                    │
                    ▼
           current verification remains owner
```

Experience Memory does not execute tasks, create Runtime runs, own checkpoints, replace user Memory, alter Learning State, or automatically mutate Planner/Skill/Tool policy.

## Deliverables

- `ExperienceRecord` contract with type/lifecycle/scope/evidence/version/provenance/privacy/expiry/conflict fields.
- One additive `experience_records` migration; no Success/Failure/Strategy table split.
- Candidate → validate → approve → active governance service with rejection, deprecation, expiry and forget.
- Deterministic bounded Retriever and `ExperienceInfluence` contract.
- Planner shadow seam and controlled prior with default OFF, allowlist, minimum evidence and fail-safe baseline fallback.
- Regression tests for redaction, lifecycle, synthetic evidence rejection, user isolation and baseline fallback.

## Compatibility matrix

| Interface/owner | Phase E action |
| --- | --- |
| Task API / `AgentRequest` / `AgentResult` | unchanged |
| Runtime Plan / checkpoint / resume | unchanged; only source IDs may be referenced |
| RAG Interface / Tool Interface | unchanged; experience cannot add unregistered target |
| `MemoryService` / `MemoryModel` | unchanged and independent |
| Session / Working / Learning State | unchanged owners and semantics |
| Planner | baseline unchanged; explicit async shadow seam only |

## KEEP / MERGE / FREEZE / REMOVE

### KEEP

- `MemoryService` for explicit user long-term memory.
- Session context, Working State, Learning State, Task/AgentRun and Runtime checkpoint owners.
- TraceStore/ModelTracer as bounded audit sources.
- Evaluation, Planner, Skill and Reflection traces as candidate provenance.
- Registry, SkillPolicy, ToolPolicy, Runtime verification and existing public contracts.

### MERGE

- Success/Failure/Strategy into one `ExperienceRecord` with type projections.
- Candidate governance, privacy/redaction, evidence and promotion provenance into one lifecycle service.
- Retrieval output and Planner influence audit into one `ExperienceInfluence` contract.

### FREEZE

- Automatic self-learning and automatic policy mutation.
- Cross-user user-scoped retrieval.
- Provider-free/synthetic claims about real answer quality.
- New public Agent or Runtime rewrite in Phase E.

### REMOVE

- No existing production module is removed in Phase E.
- Forbidden design paths are removed by contract: three parallel memory tables, direct candidate activation, raw answer storage, silent conflict choice and baseline bypass.

## Verification status

Local verification before release:

- Experience tests: `4 passed`.
- Planner/migration/Runtime compatibility selection: `25 passed`.
- Full backend suite from repository root with CI-equivalent import path: `1925 passed, 15 skipped, 6 failed`.
- The six failures are pre-existing dirty-worktree baseline failures in commercial scenario coverage, offline embedding fixture, external source count, revoked-material text encoding, and demo scenario count; none touches Experience files or the new migration.
- Targeted Ruff: PASS; targeted Mypy: PASS; configuration validation: PASS; sensitive-file scan: PASS; `git diff --check`: PASS for the Phase E staged set.

Full-repository Ruff/Mypy remain blocked by unrelated pre-existing dirty-worktree errors (five UI test line lengths and three existing type errors). Real Provider quality remains unclaimed; the release status is `STRUCTURAL_GO / CONDITIONAL_GO`.

## Phase E acceptance

`Phase E completed. ExperienceRecord is the single governed experience contract. Candidate write, lifecycle promotion, deterministic retrieval, privacy isolation, forgetting, and Planner shadow/prior fail-safe are implemented. Existing Memory, Learning State, Runtime, Registry, SkillPolicy, ToolPolicy, verification, and public APIs remain owners of their original responsibilities. Phase F has NOT started.`
