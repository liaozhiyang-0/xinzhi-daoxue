# Benchmark Results

## Phase G bounded baseline

Evidence: `evaluation/baselines/agentic_v1_real_baseline.json`.

| Metric | Value |
| --- | ---: |
| Cases | 40 |
| Passed | 25 |
| Pass rate | 0.625 |
| Mean score | 80.35675 |
| Latency p50 | 1,419 ms |
| Latency max | 180,005 ms |
| External calls | 0 |

Evidence level is `synthetic_provider_free`; real Provider was skipped because no key and explicit budget were in scope.

## Phase H available benchmark

Evidence: `evaluation/reports/phase_h/summary.json` and `docs/audits/phase_h_large_benchmark.md`.

| Metric | Value |
| --- | ---: |
| Available/executed | 84 / 84 |
| Passed | 60 |
| Failed | 18 |
| Errors | 2 |
| Timeouts | 4 |
| Pass rate | 0.714286 |
| Mean score | 85.713929 |
| Mean latency | 11,395.226 ms |
| Roadmap target | 336 |
| Missing cases | 252 |

All 84 cases are synthetic. Phase H coverage is therefore `partial`, not a 336-case completion claim.

## Phase I targeted replay

`AE_BJT_001` and `AE_MOS_001` moved from 71.43 / generation-step-missing to 100.0 after the minimal course-pack step contract fix. The replay was provider-free, with zero external calls; the full targeted regression matrix recorded 134 passed.

## Phase J robustness

The full matrix and bounded concurrency results are recorded in `../audits/phase_j_robustness.md`. The 1/5/10/20 provider-free probe completed 36/36 tasks with failure rate 0; at concurrency 20, p50 was 18.872 s and p95/p99 was 23.242 s. CPU and memory were not sampled because the environment did not contain `psutil`.

## Interpretation

These numbers establish reproducible failure and latency evidence, not production accuracy. Course, hard-case, image, grounding, research-evidence and teaching-quality metrics are incomplete until the missing dataset and approved real-provider campaign exist.
