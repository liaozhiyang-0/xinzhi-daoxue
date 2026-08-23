# T0：测试环境与数据基线冻结

## Freeze result

T0 已完成，但基线状态为 `CONDITIONAL / PARTIAL`：仓库当前工作区存在 187 个已有未提交文件改动，且路线图要求的 336 个正式案例当前只加载到 84 个。T0 不修改原题、答案、评分器、Agent、Planner 或 Runtime。

机器可读冻结清单：

- `evaluation/baselines/current_system_manifest.json`
- `docs/testing/known_baseline_failures.yaml`

## Repository state

| Item | Value |
| --- | --- |
| Branch | `agentic/full-testing-campaign` |
| Base commit | `ba85c792af3e110c9fcab4b13bbff71f15401ac5` |
| Worktree | dirty; 187 pre-existing changed/untracked paths |
| T0 policy | preserve unrelated changes; do not treat them as T0 output |
| Frozen CT solver | `SOLVER_CT v1.0` / workflow `1.0.0` |

## Dataset freeze

The authoritative command was:

```powershell
.venv\Scripts\python.exe scripts/run_evaluation.py --validate-only
```

It returned `valid: true`, no registry errors, no attachment errors, and no API requests. The current loader sees 84 official cases, not 336:

| Dimension | Current count |
| --- | ---: |
| Target | 336 |
| Loaded official | 84 |
| Missing | 252 |
| AE / CT / DE / SS | 11 / 52 / 12 / 9 |
| easy / medium / boundary / hard | 15 / 56 / 7 / 6 |
| text / mixed | 82 / 2 |
| attachments | 0 |
| provenance | synthetic |

All loaded cases have required execution identity fields (`case_id`, `course`, `task_family`, `difficulty`, `input_type`, `expected_agent`, `message`). Optional metadata remains incomplete: 28 cases lack `problem_type`, 73 lack `source`, and all 84 lack `reference_answer`. These are recorded as data-quality gaps; T0 does not fill them by guessing.

## Version freeze

Planner, Skill, Prompt, Tool, Reflection, and Experience do not expose independent release identifiers in the current repository, so they are frozen as `repository_current` with evidence paths in the manifest. Evaluation schemas are frozen as `evaluation_record.v1` and the three case-catalog/source/attachment hashing contracts. RAG reports its configured `rag_schema_v2`, `semantic_v2`, and `clean_v1` identifiers. No semantic version is invented.

T0 tests use offline `mock` execution. Real Provider evaluation is `SKIPPED_WITH_REASON`; no paid request is permitted without an explicit budget and bounded call/token/cost/time limits.

## T0 decision

`T0 PASS WITH CONDITIONS`.

The environment and hashes are reproducible, but T1 cannot honestly claim a 336-case result until the missing 252 authorized cases are supplied. T1 will run all 84 available cases without early stopping and will report coverage as partial.
