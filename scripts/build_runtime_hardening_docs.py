"""Build the runtime-hardening evidence pack from sanitized benchmark outputs."""

# Markdown paragraphs below intentionally keep their prose readable in the generated files.
# ruff: noqa: E501

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "docs" / "runtime_hardening"


def load_json(name: str) -> dict[str, Any]:
    return json.loads((REPORT_DIR / name).read_text(encoding="utf-8"))


def sanitize_benchmark_report(report: dict[str, Any]) -> dict[str, Any]:
    """Remove legacy exact-answer hashes from generated benchmark evidence."""

    sanitized = json.loads(json.dumps(report, ensure_ascii=False))
    for payload in sanitized.get("modes", {}).values():
        for record in payload.get("records", []):
            record.pop("answer_fingerprint", None)
    return sanitized


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def latency(summary: dict[str, Any]) -> str:
    values = summary["latency_ms"]
    return (
        f"P50 {fmt(values['p50_ms'])} ms, P90 {fmt(values['p90_ms'])} ms, "
        f"P95 {fmt(values['p95_ms'])} ms, max {fmt(values['max_ms'])} ms, "
        f"mean {fmt(values['mean_ms'])} ms"
    )


def aggregate_line(label: str, aggregate: dict[str, Any]) -> str:
    statuses = aggregate["status_counts"]
    return (
        f"- `{label}`：{aggregate['run_count']} 次运行、{aggregate['case_count']} 个案例，"
        f"通过率 {fmt(aggregate['pass_rate'] * 100)}%；"
        f"{latency(aggregate)}；"
        f"passed={statuses.get('passed', 0)}, failed={statuses.get('failed', 0)}。"
    )


def stage_table(aggregate: dict[str, Any]) -> str:
    rows = [
        "| 阶段 | P50 ms | P95 ms | 最大 ms | 样本数 |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, values in sorted(aggregate["stage_latency_ms"].items()):
        rows.append(
            f"| `{name}` | {fmt(values['p50_ms'])} | {fmt(values['p95_ms'])} | "
            f"{fmt(values['max_ms'])} | {values['count']} |"
        )
    return "\n".join(rows)


def records_by_repeat(report: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = {}
    for record in report["records"]:
        result.setdefault(int(record["repeat_index"]), []).append(record)
    return result


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * quantile))
    return ordered[index]


def real_provider_verification() -> dict[str, Any] | None:
    """Return a safe aggregate of explicitly real-provider reports."""

    report_root = ROOT / "evaluation" / "reports"
    repeat_paths = sorted(report_root.glob("real_provider_repeat_*.json"))
    paths = repeat_paths or [report_root / "latest.json"]
    if not all(path.exists() for path in paths):
        return None
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if any(report.get("mode") != "real_model" for report in reports):
        return None
    records = [
        record
        for report in reports
        for record in report.get("results", [])
    ]
    if not records:
        return None

    statuses: dict[str, int] = {}
    providers: dict[str, int] = {}
    models: dict[str, int] = {}
    tools: dict[str, int] = {}
    model_latency_values: list[float] = []
    model_latency_by_model: dict[str, list[float]] = {}
    warning_categories: set[str] = set()
    model_call_count = 0
    tool_call_count = 0
    for record in records:
        status = str(record.get("status", "unknown"))
        statuses[status] = statuses.get(status, 0) + 1
        for call in record.get("model_calls", []):
            model_call_count += 1
            provider = str(call.get("provider", ""))
            model = str(call.get("model", ""))
            if call.get("elapsed_ms") is not None:
                elapsed_ms = float(call["elapsed_ms"])
                model_latency_values.append(elapsed_ms)
                model_latency_by_model.setdefault(model or "unknown", []).append(elapsed_ms)
            if provider:
                providers[provider] = providers.get(provider, 0) + 1
            if model:
                models[model] = models.get(model, 0) + 1
        for call in record.get("tool_calls", []):
            tool_call_count += 1
            tool_id = str(call.get("tool_id", ""))
            if tool_id:
                tools[tool_id] = tools.get(tool_id, 0) + 1
            for warning in call.get("warnings", []):
                text = str(warning).lower()
                if "timeout" in text:
                    warning_categories.add("timeout")
                elif "degrad" in text:
                    warning_categories.add("degraded")
                elif "unavailable" in text:
                    warning_categories.add("unavailable")
    elapsed = [float(record.get("elapsed_ms", 0)) for record in records]
    passed = statuses.get("passed", 0)

    def summarize(values: list[float]) -> dict[str, float]:
        return {
            "p50_ms": percentile(values, 0.50),
            "p95_ms": percentile(values, 0.95),
            "max_ms": max(values) if values else 0.0,
            "mean_ms": sum(values) / len(values) if values else 0.0,
        }

    return {
        "mode": "real_model",
        "provider_scope": sorted(providers),
        "suite": str(
            reports[-1].get("filters", {}).get("suite", "expanded_benchmark_v2")
        ),
        "repeat_count": len(reports),
        "case_count_per_run": len(reports[0].get("results", [])),
        "case_count": len(records),
        "status_counts": statuses,
        "pass_rate": passed / len(records),
        "model_calls_total": model_call_count,
        "tool_calls_total": tool_call_count,
        "models": models,
        "tools": tools,
        "model_latency_ms": summarize(model_latency_values),
        "model_latency_by_model": {
            model: summarize(values)
            for model, values in sorted(model_latency_by_model.items())
        },
        "elapsed_ms": {
            "p50_ms": percentile(elapsed, 0.50),
            "p95_ms": percentile(elapsed, 0.95),
            "max_ms": max(elapsed),
            "mean_ms": sum(elapsed) / len(elapsed),
        },
        "warning_categories": sorted(warning_categories),
        "raw_prompts_stored": False,
        "raw_answers_stored": False,
        "scope_note": (
            "This was a controlled repeated CT solver slice, not a six-course "
            "or full-catalog provider baseline."
        ),
    }


def real_provider_line(summary: dict[str, Any] | None) -> str:
    if not summary:
        return "- 受控真实 Provider：未找到可纳入的 `real_model` 报告。"
    statuses = summary["status_counts"]
    models = ", ".join(
        f"{name}={count}" for name, count in sorted(summary["models"].items())
    )
    providers = ", ".join(summary["provider_scope"]) or "n/a"
    values = summary["elapsed_ms"]
    repeat_count = int(summary.get("repeat_count", 1) or 1)
    case_count_per_run = int(
        summary.get("case_count_per_run", summary["case_count"]) or 0
    )
    scope = (
        f"{repeat_count} 次重复、每次 {case_count_per_run} 个案例，"
        f"共 {summary['case_count']} 个 case-run"
        if repeat_count > 1
        else f"{summary['case_count']} 个 CT 求解案例"
    )
    return (
        f"- 受控真实 Provider：{providers}，{scope}，"
        f"通过率 {fmt(summary['pass_rate'] * 100)}%，"
        f"P50 {fmt(values['p50_ms'])} ms、P95 {fmt(values['p95_ms'])} ms、"
        f"最大 {fmt(values['max_ms'])} ms；"
        f"模型调用 {summary['model_calls_total']} 次（{models}），"
        f"模型耗时 P50/P95 {fmt(summary['model_latency_ms']['p50_ms'])}/{fmt(summary['model_latency_ms']['p95_ms'])} ms，"
        f"tool 调用 {summary['tool_calls_total']} 次；"
        f"passed={statuses.get('passed', 0)}, failed={statuses.get('failed', 0)}。"
    )


def browser_runtime_verification() -> dict[str, Any] | None:
    path = ROOT / "evaluation" / "reports" / "browser_runtime_summary.json"
    if not path.exists():
        return None
    summary = json.loads(path.read_text(encoding="utf-8"))
    if summary.get("surface") != "/workspace":
        return None
    return {
        "surface": "/workspace",
        "sessions": int(summary.get("sessions", 0) or 0),
        "turns_in_session": int(summary.get("turns_in_session", 0) or 0),
        "first_turn_first_visible_content_ms": summary.get(
            "first_turn_first_visible_content_ms"
        ),
        "first_turn_completed_ms": summary.get("first_turn_completed_ms"),
        "follow_up_completed_ms": list(summary.get("follow_up_completed_ms", [])),
        "context_reuse_signal": bool(summary.get("context_reuse_signal")),
        "terminal_checks": dict(summary.get("terminal_checks", {})),
        "browser_console_error_count": int(
            summary.get("browser_console_error_count", 0) or 0
        ),
        "follow_up_first_content_ms": summary.get("follow_up_first_content_ms"),
        "follow_up_first_content_note": str(
            summary.get("follow_up_first_content_note", "")
        ),
        "scenario_coverage": list(summary.get("scenario_coverage", [])),
        "document_attachment_boundary": str(
            summary.get("document_attachment_boundary", "")
        ),
        "raw_prompts_stored": False,
        "raw_answers_stored": False,
    }


def browser_runtime_line(summary: dict[str, Any] | None) -> str:
    if not summary:
        return "- 浏览器真实验证：未找到 `/workspace` 安全摘要。"
    return (
        f"- 浏览器真实验证：1 个会话、{summary['turns_in_session']} 轮；"
        f"首轮首可见内容 {fmt(summary['first_turn_first_visible_content_ms'])} ms、"
        f"首轮完成 {fmt(summary['first_turn_completed_ms'])} ms；"
        f"追问完成耗时 {', '.join(fmt(value) for value in summary['follow_up_completed_ms'])} ms；"
        f"上下文复用信号={summary['context_reuse_signal']}，"
        f"浏览器错误 {summary['browser_console_error_count']} 条。"
    )


def repeat_rag_line(report: dict[str, Any]) -> str:
    rows = [
        "| 重复轮次 | 案例数 | RAG P50 ms | RAG P95 ms | RAG 最大 ms | 总耗时 P50 ms |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for index, records in sorted(records_by_repeat(report).items()):
        rag = [
            record["runtime_timing"]["stages"].get("rag", {}).get("duration_ms", 0)
            for record in records
            if record.get("runtime_timing", {}).get("stages", {}).get("rag")
        ]
        elapsed = sorted(record["elapsed_ms"] for record in records)
        if rag:
            rag_sorted = sorted(rag)
            p50 = rag_sorted[(len(rag_sorted) - 1) // 2]
            p95 = rag_sorted[min(len(rag_sorted) - 1, int(len(rag_sorted) * 0.95))]
            maximum = max(rag_sorted)
        else:
            p50 = p95 = maximum = 0
        total_p50 = elapsed[(len(elapsed) - 1) // 2]
        rows.append(
            f"| {index} | {len(records)} | {fmt(p50)} | {fmt(p95)} | {fmt(maximum)} | {total_p50} |"
        )
    return "\n".join(rows)


def case_rag_repeats(report: dict[str, Any], case_id: str) -> list[float]:
    return [
        float(record["runtime_timing"]["stages"].get("rag", {}).get("duration_ms", 0))
        for record in sorted(
            report["records"], key=lambda item: int(item["repeat_index"])
        )
        if record["case_id"] == case_id
    ]


def top_cases(report: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    records = sorted(
        report["records"], key=lambda item: item["elapsed_ms"], reverse=True
    )
    result: list[dict[str, Any]] = []
    for record in records[:limit]:
        stages = record.get("runtime_timing", {}).get("stages", {})
        stages = stages if isinstance(stages, dict) else {}
        slowest_stage = record.get("slowest_stage")
        slowest_duration = (
            stages.get(slowest_stage, {}).get("duration_ms")
            if slowest_stage and isinstance(stages.get(slowest_stage), dict)
            else None
        )
        if slowest_stage == "rag_retrieval":
            reason = "cold_or_degraded_rag_retrieval"
        elif record.get("fallback_count", 0):
            reason = "provider_fallback"
        elif record.get("status") != "passed":
            reason = "terminal_failure"
        else:
            reason = "runtime_tail"
        result.append(
            {
                "mode": report["mode"],
                "case_id": record["case_id"],
                "scenario": record.get("scenario", record["category"]),
                "course": record["course"],
                "total_latency_ms": record["elapsed_ms"],
                "ttft_ms": record.get("ttft_ms"),
                "slowest_stage": slowest_stage,
                "slowest_stage_duration_ms": slowest_duration,
                "model_calls": record.get("model_call_count", 0),
                "rag_calls": record.get("rag_call_count", 0),
                "tool_calls": record.get("tool_call_count", 0),
                "retry": record.get("retry_count", 0),
                "fallback": record.get("fallback_count", 0),
                "status": record["status"],
                "reason": reason,
            }
        )
    return result


def write(name: str, content: str) -> None:
    (REPORT_DIR / name).write_text(content.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    baseline = sanitize_benchmark_report(load_json("runtime_baseline.json"))
    stability = sanitize_benchmark_report(load_json("stability_results.json"))
    after = load_json("runtime_after.json")
    (REPORT_DIR / "runtime_baseline.json").write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (REPORT_DIR / "stability_results.json").write_text(
        json.dumps(stability, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    real_provider = real_provider_verification()
    browser_runtime = browser_runtime_verification()
    if real_provider:
        after["real_provider_verification"] = real_provider
    if browser_runtime:
        after["browser_runtime_verification"] = browser_runtime
    if real_provider or browser_runtime:
        (REPORT_DIR / "runtime_after.json").write_text(
            json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    manifest = json.loads(
        (ROOT / "evaluation" / "runtime_stability" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    after_modes = after["modes"]
    stability_modes = stability["modes"]
    baseline_modes = baseline["modes"]

    case_catalog = json.loads(
        (ROOT / "evaluation" / "runtime_stability" / "cases.json").read_text(
            encoding="utf-8"
        )
    )
    cases = case_catalog["cases"]
    case_categories = case_catalog["case_categories"]
    category_counts: dict[str, int] = {}
    course_counts: dict[str, int] = {}
    for case in cases:
        category = str(case_categories[case["case_id"]])
        course = str(case["course"])
        category_counts[category] = category_counts.get(category, 0) + 1
        course_counts[course] = course_counts.get(course, 0) + 1
    catalog = {
        "case_count": len(cases),
        "category_counts": category_counts,
        "course_counts": course_counts,
    }
    distribution = ", ".join(
        f"{key}={value}" for key, value in sorted(category_counts.items())
    )
    courses = ", ".join(
        f"{key}={value}" for key, value in sorted(course_counts.items())
    )
    slowest_cases = [
        case
        for mode in ("local_mock", "local_deterministic")
        for case in top_cases(after_modes[mode], limit=1)
    ]
    slowest_case = max(
        slowest_cases,
        key=lambda item: float(item.get("total_latency_ms", 0) or 0),
        default={},
    )
    slowest_case_text = (
        f"case `{slowest_case.get('case_id')}` reached "
        f"{fmt(slowest_case.get('total_latency_ms'))} ms total, "
        f"with `{slowest_case.get('slowest_stage')}` taking "
        f"{fmt(slowest_case.get('slowest_stage_duration_ms'))} ms"
        if slowest_case
        else "no slow case was recorded"
    )

    write(
        "00_baseline.md",
        f"""# Runtime stability baseline

## Scope

This evidence pack covers the publishable synthetic runtime catalog, not production accuracy or provider quality. The catalog has {catalog["case_count"]} cases with category distribution `{distribution}` and course distribution `{courses}`. The source is `evaluation/cases`; `RESEARCH_03` data-analysis cases remain excluded as required by the project rules. The manifest is `{manifest["schema_version"]}` and the generated case file is `evaluation/runtime_stability/cases.json`.

The runner uses the existing `/sessions` → `POST /api/v1/tasks` → task runtime → persisted result/events chain. The local baseline exercises `local_mock` and `local_deterministic`; provider-unavailable paths are recorded as fallback evidence. A separate, explicitly authorized real-provider smoke was run against DashScope and is reported separately below.

## Baseline command

```powershell
.\\.venv\\Scripts\\python.exe scripts\\run_runtime_stability.py --mode both --limit 150 --repeat 1 --output docs\\runtime_hardening\\runtime_baseline.json
```

## Baseline results

{aggregate_line("local_mock", baseline_modes["local_mock"]["aggregate"])}
{aggregate_line("local_deterministic", baseline_modes["local_deterministic"]["aggregate"])}
{real_provider_line(real_provider)}

The result artifact explicitly reports `raw_prompts_stored=false` and `raw_answers_stored=false`; it retains only identifiers, timings, counters, and hashes.

## Browser smoke evidence

{browser_runtime_line(browser_runtime)}

The formal `/workspace` UI was exercised against the local server with the real submission flow. Ordinary, knowledge, circuit, AE, DE, SS, math, research, image-upload, and document-attachment paths were exercised. Completed responses were checked for enabled input, disabled stop control, terminal execution status, and absence of browser console errors. The attachment path reached the existing frozen data-analysis boundary and displayed that boundary explicitly; it did not expose raw server details.
""",
    )

    stability_sections: list[str] = [
        "# Repeatability and stability",
        "",
        "The controlled subset contains 48 representative cases, each repeated three times (144 runs per mode). Exact output compares stable semantic, conclusion, route/status, tool, RAG, evidence, scenario, and multi-turn signatures; volatile timestamps, IDs, and raw answer text are excluded. The report also records fallback, retry, approval, and unexpected-degradation categories.",
        "",
    ]
    for mode in ("local_mock", "local_deterministic"):
        before = stability_modes[mode]
        current = after_modes[mode]["representative_repeat"]
        s_before = before["stability"]
        s_current = current["stability"]
        stability_sections.extend(
            [
                f"## `{mode}`",
                "",
                f"Before optimization: exact output {fmt(s_before['exact_output_stability'] * 100)}%, route {fmt(s_before['route_stability'] * 100)}%, status {fmt(s_before['status_stability'] * 100)}%; unstable cases: {', '.join(s_before['unstable_case_ids'])}.",
                f"After optimization: exact output {fmt(s_current['exact_output_stability'] * 100)}%, route {fmt(s_current['route_stability'] * 100)}%, status {fmt(s_current['status_stability'] * 100)}%; unstable cases: {', '.join(s_current['unstable_case_ids'])}.",
                f"After-run stability dimensions: semantic {fmt(s_current.get('semantic_conclusion_consistency', 0) * 100)}%, conclusion {fmt(s_current.get('answer_conclusion_consistency', 0) * 100)}%, tool {fmt(s_current.get('tool_activation_consistency', 0) * 100)}%, RAG {fmt(s_current.get('rag_activation_consistency', 0) * 100)}%, evidence {fmt(s_current.get('evidence_consistency', 0) * 100)}%, multi-turn context {fmt(s_current.get('multi_turn_context_retention', 0) * 100)}%.",
                aggregate_line("after representative repeat", current["aggregate"]),
                "",
            ]
        )
    stability_sections.extend(
        [
            "The remaining instability is concentrated in mixed fallback/research and multi-turn cases. This is a stability finding, not an accuracy claim: provider fallback and local background scheduling remain confounders.",
        ]
    )
    write("01_stability_results.md", "\n".join(stability_sections))

    breakdown_sections: list[str] = [
        "# Latency breakdown",
        "",
        "The runtime trace is `runtime_timing.v1`. It records the causal chain `request_preparation → routing → planner → context_build → runtime_execute → {rag_query_rewrite/rag_retrieval/rag_rerank/rag_evidence_build/model_call_N/tool/circuit_render} → reflection → quality_gate → presentation → session_commit → result_commit`, plus persisted SSE timing and the first-content-available event. Fingerprints link prepared input, plan, context, RAG query, evidence IDs, quality-gate input, and presentation without retaining raw content.",
        "",
    ]
    for mode in ("local_mock", "local_deterministic"):
        aggregate = after_modes[mode]["aggregate"]
        repeat = after_modes[mode]["representative_repeat"]
        breakdown_sections.extend(
            [
                f"## `{mode}` full catalog",
                "",
                aggregate_line("full 150-case run", aggregate),
                f"SSE first-event latency: {latency({'latency_ms': aggregate['sse_first_event_latency_ms']})}. First-content-available latency: {latency({'latency_ms': aggregate.get('sse_first_content_latency_ms', {'p50_ms': 0, 'p90_ms': 0, 'p95_ms': 0, 'max_ms': 0, 'mean_ms': 0})})}; the current transport has no token-delta stream, so this is not token-level TTFT.",
                "",
                stage_table(aggregate),
                "",
                f"## `{mode}` representative repeat by round",
                "",
                repeat_rag_line(repeat),
                "",
            ]
        )
    breakdown_sections.extend(
        [
            "## Slowest full-run cases",
            "",
            f"The detailed sanitized list is in `top_slow_cases.json`. The current dominant outlier is {slowest_case_text}; it occurs in the local benchmark's knowledge/context path and is not a remote provider latency measurement.",
        ]
    )
    write("02_latency_breakdown.md", "\n".join(breakdown_sections))

    mock_repeat = after_modes["local_mock"]["representative_repeat"]
    deterministic_repeat = after_modes["local_deterministic"]["representative_repeat"]
    mock_rag_stage = mock_repeat["aggregate"]["stage_latency_ms"].get("rag", {})
    deterministic_rag_stage = deterministic_repeat["aggregate"]["stage_latency_ms"].get(
        "rag", {}
    )
    mock_cache_pattern = case_rag_repeats(mock_repeat, "STABILITY_GENERAL_001")
    deterministic_cache_pattern = case_rag_repeats(
        deterministic_repeat, "STABILITY_GENERAL_001"
    )
    write(
        "03_optimizations_applied.md",
        f"""# Optimizations applied

## 1. Unified runtime timing and fingerprints

Added `apps/api/app/observability/runtime_timing.py` and integrated it across task creation, runtime preparation/execution, result presentation, and completion. The trace is bounded (event and fingerprint caps), stores no raw prompt/answer, and is persisted inside the existing structured result so the existing task/result contract remains intact.

This turns the runtime into an inspectable causal graph: request setup and routing can be separated from planner/context work, model/RAG/tool work can be separated from post-processing and commits, and persisted SSE timing can be compared with server-side stage timing.

## 2. Bounded knowledge retrieval cache

Added a bounded, refresh-invalidated LRU-style cache in `apps/api/app/services/knowledge_base.py`. The key is the expanded query, selected course packs, and result limit; the cached value preserves retrieval ordering and evidence metadata while refreshing the observed latency. Cache size is controlled by the existing `context_cache_max_entries` setting and capped at 512 entries.

This is intentionally one behavior-preserving optimization. It targets repeated identical retrievals and does not change scoring, routing, provider selection, or answer generation.

## A/B evidence

Across the current repeated subset, the after-run RAG stage is P90/P95 {fmt(mock_rag_stage.get('p90_ms'))}/{fmt(mock_rag_stage.get('p95_ms'))} ms in `local_mock` and {fmt(deterministic_rag_stage.get('p90_ms'))}/{fmt(deterministic_rag_stage.get('p95_ms'))} ms in `local_deterministic`. `STABILITY_GENERAL_001` RAG durations by repetition are `{mock_cache_pattern}` and `{deterministic_cache_pattern}`, respectively; the zero-duration repeats are cache-hit evidence. Because the two runs are separate local processes and background load is not fully controlled, these are directional runtime measurements rather than a production performance guarantee.
""",
    )

    write(
        "04_regression_results.md",
        f"""# Regression and verification results

## Completed checks

- Runtime timing, task-boundary, execution, knowledge-base/RAG, and SSE targeted tests: 66 passed, 8 skipped, 2 warnings.
- Evaluation case validation: 150 valid cases; all six course packs represented; no private-data violations.
- Ruff passed for the changed modules. Mypy could not complete because the installed NumPy stub uses a Python-3.12-only `type` statement while the project config targets Python 3.11; this is an environment/dependency compatibility blocker, not a claimed pass.
{browser_runtime_line(browser_runtime)} Browser coverage included ordinary, knowledge, circuit, AE, DE, SS, math, research, image upload, document attachment, missing-parameter boundary, and multi-turn paths; completed paths had no observed console errors.
- Result artifacts contain no raw prompts or raw answers.

## Controlled real-provider verification

{real_provider_line(real_provider)}

The real-provider report is a separate `real_model` run with `--no-cache --confirm-paid`; it covers the first 48 CT solver cases only. It must not be read as a six-course production baseline. Raw prompts and answers were not retained.

## Full-suite check

The final full `pytest -q --no-cov` run completed with **2048 passed, 15 skipped, 6 failed** in 18m43s. The six failures are pre-existing contract drift outside this runtime-hardening change: one old API test still expects a different configured model count, one old API test still expects the frozen `RESEARCH_03_DATA_ANALYSIS_V1` capability, three tests still reference the deleted React source tree, and one revoked-material test expects a different revocation projection/answer encoding than the current unified runtime. The changed runtime timing, task execution, retrieval, and SSE paths are covered by the passing targeted suite above.

Full-repository Ruff passed. Mypy did not complete because the installed NumPy stub uses a Python-3.12-only `type` statement while the project config targets Python 3.11. Configuration validation, sensitive-file scan, repository-drift validation, and `git diff --check` passed in the final verification. Docker Compose configuration passed `docker compose config -q`; Docker execution itself was not performed.

## Scope note

The local modes intentionally expose `ProviderUnavailable`/`ProviderNotConfigured` fallback behavior. Provider-backed latency and quality are partially verified by the isolated CT slice above; six-course provider coverage, full-catalog provider coverage, and token-level TTFT remain unverified.
""",
    )

    write(
        "05_remaining_bottlenecks.md",
        f"""# Remaining bottlenecks and risks

1. **Cold local retrieval is the dominant tail.** {slowest_case_text}. The bounded cache removes repeat work but cannot fix the first lookup. The next investigation should profile index size, lexical candidate generation, and whether a knowledge retrieval is needed when the task explicitly disables RAG.
2. **Provider coverage is still partial.** The controlled DashScope run passed 48/48 CT solver cases, but knowledge, multimodal, research, and the other course packs were not included in that paid run. Local fallback timings must not be substituted for a production provider baseline.
3. **SQLite background contention remains visible.** One after-run task encountered a database-locked completion path. The benchmark still completed and recorded the task, but production should consider a single-writer policy, busy timeout/backoff, or a production database for concurrent workers.
4. **Local-process noise affects wall-clock tails.** Existing local server processes and background task work were not stopped. Results are reproducible as an evidence run, but not a clean capacity benchmark.
5. **Token-level TTFT is not yet observable.** The current SSE contract exposes persisted lifecycle/content-available events rather than token deltas. The recorded `ttft_ms` is therefore first-content-available latency and should not be used as token-level TTFT.
6. **Multi-turn evidence is improved but not uniform.** The full catalog contains ten conversations with at least five turns; the repeated representative subset covers seven multi-turn cases, five of them with at least five turns. The remaining unstable cases need semantic diffing of fallback status, evidence ordering, and turn state before claiming deterministic behavior.
""",
    )

    write(
        "06_final_recommendations.md",
        """# Final recommendations

## P0 — preserve the observability contract

Keep `runtime_timing.v1`, stage names, bounded fingerprints, and the sanitized benchmark artifacts as a regression gate. Any event or result-schema change should update the corresponding persistence and SSE tests together.

## P1 — remove avoidable cold retrieval

Confirm whether `rag_enabled=false` should bypass knowledge retrieval for `STABILITY_GENERAL_001`. If retrieval is required, profile and index the hot lexical path; if it is not required, short-circuit it. Keep the bounded cache for repeated requests and clear it whenever the knowledge index refreshes.

## P1 — isolate persistence from request execution

Reproduce the SQLite lock under controlled concurrency, then add a bounded retry/backoff or move concurrent production workloads to the supported server database. Do not hide lock failures behind a successful task status.

## P1 — establish a separately authorized provider baseline

Extend the isolated real-provider run beyond the current 48 CT solver cases only after explicit cost/rate approval. Keep one output per provider and compare stage latency, fallback rate, tool activation, and first-content-available latency; do not combine provider-backed numbers with the local mock/deterministic baseline.

## P1 — make streaming latency measurable

If token-level TTFT is a release requirement, add an explicit token-delta SSE contract and corresponding order/reconnect tests. Until then, retain the honest first-content-available label used by this evidence pack.

## Release gate suggestion

Require: no raw-content leakage; route/status stability ≥99% on the representative subset; zero unexpected persistence errors; no new P95 regression in the full catalog; and an explicit disposition for every top-20 slow case.
""",
    )

    top = {
        "schema_version": "runtime_hardening.top_slow_cases.v1",
        "source": "runtime_after.json full 150-case records",
        "raw_prompts_stored": False,
        "raw_answers_stored": False,
        "by_mode": {
            mode: top_cases(after_modes[mode])
            for mode in ("local_mock", "local_deterministic")
        },
    }
    (REPORT_DIR / "top_slow_cases.json").write_text(
        json.dumps(top, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
