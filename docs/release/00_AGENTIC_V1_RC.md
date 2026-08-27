# 芯智导学 Agentic v1.0 Release Candidate

## Release identity

| 项目 | 值 |
| --- | --- |
| Candidate | `agentic-v1.0-rc1`（文档候选，不自动创建 tag） |
| Branch | `agentic/phase-k-release-candidate` |
| Base evidence | Phase F → G → H → I → J |
| Provider policy | 本 RC 验收不执行无预算的真实付费 Provider |
| Retired baseline | `SOLVER_CT v1.0` 仅作历史证据；当前电路题能力由 `ACADEMIC_PROBLEM_SOLVER` 承接 |
| Release posture | **CONDITIONAL GO / not production release** |

## Version freeze ledger

| Component | Frozen identifier in evidence | Status |
| --- | --- | --- |
| Planner | `repository_current` | conditional; no independent release ID |
| Skill Registry | `repository_current` | conditional; no independent release ID |
| Prompt | `repository_current` | conditional; no independent release ID |
| RAG index | `repository_current` | conditional; index fingerprint is evidence-bound |
| Tool registry | `repository_current` | conditional; no independent release ID |
| Reflection | `repository_current` | conditional; no independent release ID |
| Experience | `repository_current` | structural/conditional evidence only |
| Evaluation | `phase_g_baseline.v1` + `phase_j_concurrency.v1` | reproducible evidence schemas |
| Retired CT Solver | `SOLVER_CT v1.0` / workflow `1.0.0` | historical evidence only; not an active route |

The `repository_current` rows are intentionally not upgraded to invented semantic versions. They are release blockers for a production promotion, not hidden assumptions.

本阶段只冻结、验证、打包和文档化，不新增 Agent 控制层，不修改 public API、数据库 migration、Planner、Skill、Reflection、Memory、RAG 或 Tool 的业务实现。

## Acceptance gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Critical regression | PASS for targeted/CI gate；full available benchmark remains PARTIAL | Phase I regression、Phase J matrix、CI run |
| Public API compatibility | PASS | backend CI OpenAPI/TS contract checks |
| Database migration | PASS / unchanged | K does not add or alter migration |
| CI status | PASS | Phase J run `32595412903` |
| Secrets | PASS | sensitive-file scan |
| Repository layout | PASS | repo drift check |
| Commercial scenario coverage | CONDITIONAL | local validator sees pre-existing dirty `config/scenarios.yaml` entries without matching cases; not staged by K |
| Reproducible benchmark | CONDITIONAL | 84 available of 336 target; all available cases synthetic |
| Rollback | PASS | revert the single K commit; no merge/tag/production action |
| Real Provider evidence | CONDITIONAL | no key + explicit budget in scope |

## Final artifact index

- `architecture_overview.md`
- `evaluation_methodology.md`
- `benchmark_results.md`
- `failure_driven_optimization.md`
- `safety_governance.md`
- `demo_cases.md`
- `known_limitations.md`
- `../audits/phase_j_robustness.md`

## Release decision

This is suitable as a reproducible local/demo Release Candidate and review package. It is not evidence for production quality, real-model accuracy, or an unrestricted deployment. Promotion requires the missing 252 official cases, expanded benchmark coverage, real-provider budget approval, long-duration soak evidence, and explicit version identifiers for currently `repository_current` components.
