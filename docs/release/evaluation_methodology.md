# Evaluation Methodology

Evidence is separated into four layers:

1. local contract/unit tests;
2. provider-free runtime and API tests;
3. synthetic evaluation cases and cached replay;
4. controlled real-provider evidence.

The first three layers are reproducible in this repository. Layer 4 is not claimed without a configured key, explicit case budget, token budget, estimated cost and timeout.

## Reproduction commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/run_phase_g_baseline.py --max-cases 40
.\.venv\Scripts\python.exe scripts/run_phase_h_benchmark.py
.\.venv\Scripts\python.exe scripts/run_phase_j_robustness.py --levels 1,5,10,20 --timeout-seconds 60
.\.venv\Scripts\python.exe scripts/validate_config.py
.\.venv\Scripts\python.exe scripts/check_sensitive_files.py
.\.venv\Scripts\python.exe scripts/check_repo_drift.py
```

The official case catalog currently contains 84 available cases; the roadmap target is 336. Reports preserve case IDs, catalog hashes, provenance and cache fingerprints. Synthetic results must not be described as real-provider quality.

## Scoring and governance

The existing Evaluation Framework is the sole scoring owner. Phase F proposals are candidates only; no result automatically changes Prompt, Skill, Planner policy, Tool policy, code or production configuration. Promotion requires review and a reproducible replay.
