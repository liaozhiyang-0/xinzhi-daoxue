# Regression and verification results

## Completed checks

- Runtime timing, task-boundary, execution, knowledge-base/RAG, and SSE targeted tests: 66 passed, 8 skipped, 2 warnings.
- Evaluation case validation: 150 valid cases; all six course packs represented; no private-data violations.
- Ruff passed for the changed modules. Mypy could not complete because the installed NumPy stub uses a Python-3.12-only `type` statement while the project config targets Python 3.11; this is an environment/dependency compatibility blocker, not a claimed pass.
- 浏览器真实验证：1 个会话、4 轮；首轮首可见内容 11116 ms、首轮完成 11233 ms；追问完成耗时 8575, 7475, 7223 ms；上下文复用信号=True，浏览器错误 0 条。 Browser coverage included ordinary, knowledge, circuit, AE, DE, SS, math, research, image upload, document attachment, missing-parameter boundary, and multi-turn paths; completed paths had no observed console errors.
- Result artifacts contain no raw prompts or raw answers.

## Controlled real-provider verification

- 受控真实 Provider：dashscope，48 个 CT 求解案例，通过率 100.00%，P50 7673.00 ms、P95 28968.00 ms、最大 65019.00 ms；模型调用 46 次（qwen3.6-flash=40, qwen3.7-plus=6），模型耗时 P50/P95 5914.00/10632.00 ms，tool 调用 43 次；passed=48, failed=0。

The real-provider report is a separate `real_model` run with `--no-cache --confirm-paid`; it covers the first 48 CT solver cases only. It must not be read as a six-course production baseline. Raw prompts and answers were not retained.

## Full-suite check

The final full `pytest -q --no-cov` run completed with **2048 passed, 15 skipped, 6 failed** in 18m43s. The six failures are pre-existing contract drift outside this runtime-hardening change: one old API test still expects a different configured model count, one old API test still expects the frozen `RESEARCH_03_DATA_ANALYSIS_V1` capability, three tests still reference the deleted React source tree, and one revoked-material test expects a different revocation projection/answer encoding than the current unified runtime. The changed runtime timing, task execution, retrieval, and SSE paths are covered by the passing targeted suite above.

Full-repository Ruff passed. Mypy did not complete because the installed NumPy stub uses a Python-3.12-only `type` statement while the project config targets Python 3.11. Configuration validation, sensitive-file scan, repository-drift validation, and `git diff --check` passed in the final verification. Docker Compose configuration passed `docker compose config -q`; Docker execution itself was not performed.

## Scope note

The local modes intentionally expose `ProviderUnavailable`/`ProviderNotConfigured` fallback behavior. Provider-backed latency and quality are partially verified by the isolated CT slice above; six-course provider coverage, full-catalog provider coverage, and token-level TTFT remain unverified.
