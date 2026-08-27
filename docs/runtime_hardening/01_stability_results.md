# Repeatability and stability

The controlled subset contains 48 representative cases, each repeated three times (144 runs per mode). Exact output compares stable semantic, conclusion, route/status, tool, RAG, evidence, scenario, and multi-turn signatures; volatile timestamps, IDs, and raw answer text are excluded. The report also records fallback, retry, approval, and unexpected-degradation categories.

## `local_mock`

Before optimization: exact output 93.75%, route 100.00%, status 100.00%; unstable cases: COMMERCIAL_RUBRIC_001, TP2-12, STABILITY_RESEARCH_005.
After optimization: exact output 95.83%, route 95.83%, status 95.83%; unstable cases: TP2-11, STABILITY_MULTI_TURN_007.
After-run stability dimensions: semantic 95.83%, conclusion 95.83%, tool 95.83%, RAG 95.83%, evidence 100.00%, multi-turn context 100.00%.
- `after representative repeat`：144 次运行、48 个案例，通过率 56.94%；P50 1386.00 ms, P90 3015.00 ms, P95 3691.00 ms, max 45092.00 ms, mean 2056.83 ms；passed=82, failed=62。

## `local_deterministic`

Before optimization: exact output 93.75%, route 95.83%, status 95.83%; unstable cases: TP2-11, STABILITY_RESEARCH_005, STABILITY_MULTI_TURN_007.
After optimization: exact output 97.92%, route 97.92%, status 97.92%; unstable cases: TP2-11.
After-run stability dimensions: semantic 97.92%, conclusion 97.92%, tool 97.92%, RAG 97.92%, evidence 100.00%, multi-turn context 100.00%.
- `after representative repeat`：144 次运行、48 个案例，通过率 56.94%；P50 1290.00 ms, P90 2778.00 ms, P95 3503.00 ms, max 41247.00 ms, mean 1893.80 ms；passed=82, failed=62。

The remaining instability is concentrated in mixed fallback/research and multi-turn cases. This is a stability finding, not an accuracy claim: provider fallback and local background scheduling remain confounders.
