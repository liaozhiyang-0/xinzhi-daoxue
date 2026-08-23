# T1：336-case 当前架构全量 Baseline

## Execution status

T1 executed every case currently available to the official loader: 84/84. The requested 336-case catalog is not present, so this is `Benchmark V1 / PARTIAL`, not a completed 336-case claim. No case, expected answer, scorer, Prompt, Agent, Planner, or Runtime was changed during T1.

Command:

```powershell
.venv\Scripts\python.exe scripts/run_phase_h_benchmark.py
```

Machine reports (ignored runtime artifacts):

- `evaluation/reports/phase_h/latest.json`
- `evaluation/reports/phase_h/summary.json`

The runner reused 38 matching provider-free cache entries and executed the remaining cases under the current evaluation fingerprint. Cached rows are explicitly marked by `result_loaded_from_cache` warnings; this is not a fresh uncached 84-case claim.

## Overall result

| Metric | Result |
| --- | ---: |
| Roadmap target | 336 |
| Available / executed | 84 / 84 |
| Missing | 252 |
| Passed | 62 |
| Failed | 16 |
| Error | 2 |
| Timeout | 4 |
| Pass rate | 0.738095 |
| Mean score | 86.394167 |
| Mean latency | 10,973.095 ms |
| Max latency | 240,004 ms |
| External Provider calls | 0 |
| Evidence level | `synthetic_provider_free` |

The command exits with code 1 because errors and timeouts are present. That is an expected failure signal, not a reason to omit the cases.

## Dimensions

### Course

| Course | Cases | Pass rate | Mean score | Mean latency |
| --- | ---: | ---: | ---: | ---: |
| AE | 11 | 0.818182 | 96.103636 | 3,727.909 ms |
| CT | 52 | 0.769231 | 85.439423 | 16,408.115 ms |
| DE | 12 | 0.416667 | 74.998333 | 1,198.750 ms |
| SS | 9 | 0.888889 | 95.237778 | 1,458.444 ms |

### Difficulty and input

| Dimension | Cases | Pass rate | Mean score | Observation |
| --- | ---: | ---: | ---: | --- |
| easy | 15 | 0.733333 | 90.475333 | long tail includes AE diode |
| medium | 56 | 0.785714 | 88.775357 | CT lesson/assessment timeouts dominate latency |
| hard | 6 | 0.166667 | 40.475000 | small but material quality weakness |
| boundary | 7 | 0.857143 | 97.958571 | one course-pack mismatch |
| text | 82 | 0.756098 | 87.107683 | dominant coverage |
| mixed | 2 | 0.000000 | 57.140000 | both visual commercial cases failed structural checks |

### Failure stage

| Stage | Cases | Representative pattern |
| --- | ---: | --- |
| tool_execution | 4 | DE tool-disabled negative/unsupported-tool cases |
| timeout | 4 | CT teaching and assessment / contest cases |
| routing | 4 | learning, research, governance, and TP3 route contracts |
| citation_validation | 2 | mixed visual commercial cases |
| generation | 3 | numeric/keyword mismatches in AE/CT/DE |
| course_pack_resolution | 1 | explicit boundary course conflict |
| verification | 2 | teaching-foundation contract mismatch |
| unknown / execution_error | 2 | data-analysis and research task creation 409 |

## Top observed patterns

1. `P01`: four DE academic cases reach `tool_execution` with `tool_disabled`; these include deliberate disabled-tool boundaries and must not be “fixed” by deleting or weakening the cases.
2. `P02`: two assignment-review cases time out at 180 seconds.
3. `P03`: two lesson-preparation cases time out at 180/240 seconds.
4. `P04`: two data-analysis/research cases return task-creation `409 Conflict` and are currently attributed as execution errors.
5. Mixed visual cases fail required visual extraction/acceptance/solution/review fields and citation checks; the current catalog has only two mixed cases.
6. DE is the weakest course by pass rate (0.416667); hard cases are the weakest difficulty slice (0.166667), but both samples are small.

## Governance checks

The generated summary records `scorer_modified=false`, `test_cases_deleted=false`, `agent_or_runtime_modified=false`, and `answers_retained=false`. T1 is therefore a measurement baseline only. T2 must attribute failures before any T4 change.
