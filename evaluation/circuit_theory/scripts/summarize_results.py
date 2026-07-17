from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = ROOT / "results" / "mock_benchmark.json"
    if not source.exists():
        print("NOT RUN: run_mock_benchmark.py first")
        return 2
    report = json.loads(source.read_text(encoding="utf-8"))
    results = report.get("results", [])
    completed = sum(item.get("status") == "completed" for item in results)
    summary = [
        "# Mock Benchmark Summary",
        "",
        "> 工程链路验证，不代表真实电路解题正确率。",
        "",
        f"- Provider: `{report.get('provider')}`",
        f"- Cases: {len(results)}",
        f"- Completed: {completed}",
        "- Correctness: NOT EVALUATED",
        "- Real Xingchen benchmark: DEFERRED",
    ]
    output = ROOT / "results" / "mock_benchmark_summary.md"
    output.write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(f"Summary: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
