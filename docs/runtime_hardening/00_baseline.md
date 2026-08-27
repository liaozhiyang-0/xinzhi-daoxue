# Runtime stability baseline

## Scope

This evidence pack covers the publishable synthetic runtime catalog, not production accuracy or provider quality. The catalog has 150 cases with category distribution `boundary=24, general=16, knowledge=36, multi_turn=12, multimodal=16, research=10, solver=36` and course distribution `AE=22, COMM=12, CT=54, DE=24, DSP=13, SS=25`. The source is `evaluation/cases`; `RESEARCH_03` data-analysis cases remain excluded as required by the project rules. The manifest is `runtime_stability.v1` and the generated case file is `evaluation/runtime_stability/cases.json`.

The runner uses the existing `/sessions` → `POST /api/v1/tasks` → task runtime → persisted result/events chain. The local baseline exercises `local_mock` and `local_deterministic`; provider-unavailable paths are recorded as fallback evidence. A separate, explicitly authorized real-provider smoke was run against DashScope and is reported separately below.

## Baseline command

```powershell
.\.venv\Scripts\python.exe scripts\run_runtime_stability.py --mode both --limit 150 --repeat 1 --output docs\runtime_hardening\runtime_baseline.json
```

## Baseline results

- `local_mock`：150 次运行、150 个案例，通过率 79.33%；P50 1504.00 ms, P90 2464.00 ms, P95 3355.00 ms, max 28810.00 ms, mean 1843.39 ms；passed=119, failed=31。
- `local_deterministic`：150 次运行、150 个案例，通过率 79.33%；P50 1429.00 ms, P90 2013.00 ms, P95 2518.00 ms, max 34211.00 ms, mean 1705.73 ms；passed=119, failed=31。
- 受控真实 Provider：dashscope，48 个 CT 求解案例，通过率 100.00%，P50 7673.00 ms、P95 28968.00 ms、最大 65019.00 ms；模型调用 46 次（qwen3.6-flash=40, qwen3.7-plus=6），模型耗时 P50/P95 5914.00/10632.00 ms，tool 调用 43 次；passed=48, failed=0。

The result artifact explicitly reports `raw_prompts_stored=false` and `raw_answers_stored=false`; it retains only identifiers, timings, counters, and hashes.

## Browser smoke evidence

- 浏览器真实验证：1 个会话、4 轮；首轮首可见内容 11116 ms、首轮完成 11233 ms；追问完成耗时 8575, 7475, 7223 ms；上下文复用信号=True，浏览器错误 0 条。

The formal `/workspace` UI was exercised against the local server with the real submission flow. Ordinary, knowledge, circuit, AE, DE, SS, math, research, image-upload, and document-attachment paths were exercised. Completed responses were checked for enabled input, disabled stop control, terminal execution status, and absence of browser console errors. The attachment path reached the existing frozen data-analysis boundary and displayed that boundary explicitly; it did not expose raw server details.
