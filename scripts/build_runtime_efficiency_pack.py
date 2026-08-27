# ruff: noqa: E501

"""Build the final runtime-efficiency evidence pack from sanitized reports.

The command deliberately consumes the existing runtime-hardening artifacts instead
of introducing another benchmark or runtime implementation.  It writes only the
publishable aggregate reports required by the runtime-efficiency handoff.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "docs" / "runtime_hardening"
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "runtime_efficiency"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def pct_delta(before: Any, after: Any) -> str:
    if before in (None, 0) or after is None:
        return "n/a"
    value = (float(after) - float(before)) / float(before) * 100
    return f"{value:+.2f}%"


def aggregate_fallbacks(payload: dict[str, Any]) -> dict[str, float | int]:
    records = payload.get("records", [])
    count = len(records)
    fallback = sum(
        int(record.get("fallback_count", 0) or 0)
        or int(bool(record.get("fallback_used")))
        for record in records
    )
    retries = sum(
        int(record.get("retry_count", 0) or 0)
        or int((record.get("metrics") or {}).get("retry_count", 0) or 0)
        for record in records
    )
    return {
        "case_runs": count,
        "fallback_count": fallback,
        "fallback_rate": fallback / count if count else 0.0,
        "retry_count": retries,
        "retry_rate": retries / count if count else 0.0,
    }


def stage_rows(aggregate: dict[str, Any]) -> str:
    rows = [
        "| 阶段 | P50 ms | P95 ms | 最大 ms | 样本数 |",
        "|---|---:|---:|---:|---:|",
    ]
    stages = aggregate.get("stage_latency_ms", {})
    for name, values in sorted(stages.items()):
        rows.append(
            f"| `{name}` | {fmt(values.get('p50_ms'))} | "
            f"{fmt(values.get('p95_ms'))} | {fmt(values.get('max_ms'))} | "
            f"{values.get('count', 0)} |"
        )
    return "\n".join(rows)


def real_provider_stats(report: dict[str, Any]) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    providers: dict[str, int] = {}
    models: dict[str, int] = {}
    task_types: dict[str, int] = {}
    model_elapsed: list[float] = []
    model_tokens = {"prompt": 0, "completion": 0, "total": 0}
    model_statuses: dict[str, int] = {}
    tool_ids: dict[str, int] = {}
    model_calls = 0
    tool_calls = 0
    for record in report.get("results", []):
        status = str(record.get("status", "unknown"))
        statuses[status] = statuses.get(status, 0) + 1
        for call in record.get("model_calls", []):
            model_calls += 1
            provider = str(call.get("provider", "unknown"))
            model = str(call.get("model", "unknown"))
            task_type = str(call.get("task_type", "unknown"))
            providers[provider] = providers.get(provider, 0) + 1
            models[model] = models.get(model, 0) + 1
            task_types[task_type] = task_types.get(task_type, 0) + 1
            call_status = str(call.get("status", "unknown"))
            model_statuses[call_status] = model_statuses.get(call_status, 0) + 1
            if call.get("elapsed_ms") is not None:
                model_elapsed.append(float(call["elapsed_ms"]))
            model_tokens["prompt"] += int(call.get("prompt_tokens", 0) or 0)
            model_tokens["completion"] += int(call.get("completion_tokens", 0) or 0)
            model_tokens["total"] += int(call.get("total_tokens", 0) or 0)
        for call in record.get("tool_calls", []):
            tool_calls += 1
            tool_id = str(call.get("tool_id", "unknown"))
            tool_ids[tool_id] = tool_ids.get(tool_id, 0) + 1

    def summarize(values: list[float]) -> dict[str, float | int]:
        if not values:
            return {"count": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}
        ordered = sorted(values)
        return {
            "count": len(values),
            "p50_ms": ordered[int((len(ordered) - 1) * 0.50)],
            "p95_ms": ordered[int((len(ordered) - 1) * 0.95)],
            "max_ms": max(ordered),
        }

    return {
        "mode": report.get("mode"),
        "suite": report.get("filters", {}).get("suite"),
        "case_count": len(report.get("results", [])),
        "status_counts": statuses,
        "provider_call_counts": providers,
        "model_call_counts": models,
        "task_type_counts": task_types,
        "model_status_counts": model_statuses,
        "model_calls_total": model_calls,
        "tool_calls_total": tool_calls,
        "tool_id_counts": tool_ids,
        "model_elapsed_ms": summarize(model_elapsed),
        "token_totals": model_tokens,
        "metadata_only": True,
        "raw_prompts_stored": bool(report.get("run_metadata", {}).get("raw_prompts_stored", False)),
        "raw_answers_stored": False,
        "source_run_id": report.get("run_metadata", {}).get("run_id"),
    }


def build_model_call_stats(
    after: dict[str, Any], real_report: dict[str, Any] | None
) -> dict[str, Any]:
    local: dict[str, Any] = {}
    for mode, payload in after.get("modes", {}).items():
        aggregate = payload.get("aggregate", {})
        local[mode] = {
            "case_runs": len(payload.get("records", [])),
            "model_calls_total": sum(
                int(record.get("model_call_count", 0) or 0)
                for record in payload.get("records", [])
            ),
            "tool_calls_total": sum(
                int(record.get("tool_call_count", 0) or 0)
                for record in payload.get("records", [])
            ),
            "rag_calls_total": sum(
                int(record.get("rag_call_count", 0) or 0)
                for record in payload.get("records", [])
            ),
            "stage_model": aggregate.get("stage_latency_ms", {}).get("model", {}),
            "metadata_only": True,
            "model_identity_retained": False,
        }
    return {
        "schema_version": "model_call_stats.v1",
        "retention": "bounded metadata only; no raw prompts or answers",
        "local_modes": local,
        "real_provider": real_provider_stats(real_report) if real_report else None,
    }


def build_markdown(source_dir: Path, output_dir: Path) -> None:
    baseline = load_json(source_dir / "runtime_baseline.json")
    after = load_json(source_dir / "runtime_after.json")
    stability = load_json(source_dir / "stability_results.json")
    slow = load_json(source_dir / "top_slow_cases.json")
    real = after.get("real_provider_verification")
    browser = after.get("browser_runtime_verification")

    baseline_modes = baseline.get("modes", {})
    after_modes = after.get("modes", {})
    baseline_rows = []
    for mode, payload in baseline_modes.items():
        aggregate = payload.get("aggregate", {})
        latency = aggregate.get("latency_ms", {})
        baseline_rows.append(
            f"| `{mode}` | {aggregate.get('run_count', 0)} | "
            f"{fmt(aggregate.get('pass_rate', 0) * 100)}% | "
            f"{fmt(latency.get('p50_ms'))} | {fmt(latency.get('p95_ms'))} | "
            f"{fmt(latency.get('max_ms'))} |"
        )
    baseline_table = "\n".join(baseline_rows)
    lines: dict[str, str] = {}
    lines["00_baseline.md"] = f"""# Runtime baseline

本目录的基线是现有 Runtime 链路上的本地可重复基准，不代表生产准确率，也不把 mock/deterministic 结果冒充真实模型结果。案例目录为 `{baseline.get('case_count', 'n/a')}` 个，原始问答未写入报告：`raw_prompts_stored={baseline.get('raw_prompts_stored')}`、`raw_answers_stored={baseline.get('raw_answers_stored')}`。

运行命令：

```powershell
.\\.venv\\Scripts\\python.exe scripts\\run_runtime_stability.py --mode both --limit 150 --repeat 1 --output docs\\runtime_hardening\\runtime_baseline.json
```

| 模式 | 案例运行数 | 通过率 | P50 ms | P95 ms | 最大 ms |
|---|---:|---:|---:|---:|---:|
{baseline_table}

该基线只用于和 `runtime_after.json` 做同口径比较。真实 Provider、浏览器和工作区六案例矩阵均单独列出，不混入本地延迟数字。
"""

    lines["01_runtime_diagnostics.md"] = """# Runtime diagnostics contract

统一诊断载荷为 `runtime_timing.v1`，挂在任务结构化结果中，使用现有 Runtime，不新增 Runtime、LangGraph 或第二套编排器。每个 trace 包含：

- `events`：请求接收、阶段开始/结束、模型调用、工具节点和完成事件；保存时间、耗时、状态和有限元数据。
- `stages`：`request_preparation`、`routing`、`runtime_execute`、`planner`、`context_build`、`rag`、`model`、`tool`、`reflection`、`quality_gate`、`result_validation`、`task_commit` 等阶段的耗时与 `outcome`。
- `counters`：模型、工具、RAG、重试、fallback 和质量门计数。
- `context_usage`：上下文字符/消息/文档数量与哈希；不保存原始 prompt、answer 或 token 内容。
- `fingerprints`：有限数量的上下文、结构化结果和事件指纹，用来比较重复运行，不用来还原用户内容。

本轮最小实现补齐了失败状态和尾部阶段：`timed_stage` 在异常时记录 `outcome=failed` 后继续抛出；模型调用使用其状态；工具节点同时记录 `tool` 与 `tool_execution`；结果校验和任务提交分别可观测。SSE 仍由稳定性脚本记录首事件、首个可用内容和终态，且明确标注为可用内容事件，不冒充 token-level TTFT。

相关实现：`apps/api/app/observability/runtime_timing.py`、`apps/api/app/services/task_runtime_execution.py`、`apps/api/app/services/task_completion.py`、`scripts/run_runtime_stability.py`。
"""

    stability_lines = [
        "# Stability results",
        "",
        "150-case 双模式基准用于覆盖面；代表性重复集为 48 个案例 × 3 轮 × 2 个本地模式，用于判断路由、状态、语义结论、工具/RAG 激活和多轮上下文是否稳定。波动的时间戳、task id 和原始答案不参与精确稳定性比较。",
        "",
    ]
    for mode, payload in stability.get("modes", {}).items():
        current = after_modes.get(mode, {}).get("representative_repeat", {}).get("stability", {})
        before = payload.get("stability", {})
        stability_lines.extend(
            [
                f"## `{mode}`",
                "",
                f"重复集：{before.get('repetition_count', 'n/a')} 次 case-run；任务成功率 {fmt(payload.get('aggregate', {}).get('pass_rate', 0) * 100)}%；精确稳定性 {fmt(before.get('exact_output_stability', 0) * 100)}%；路由稳定性 {fmt(before.get('route_stability', 0) * 100)}%；状态稳定性 {fmt(before.get('status_stability', 0) * 100)}%。",
                f"最新诊断口径：精确稳定性 {fmt(current.get('exact_output_stability', 0) * 100)}%；路由稳定性 {fmt(current.get('route_stability', 0) * 100)}%；状态稳定性 {fmt(current.get('status_stability', 0) * 100)}%；未稳定案例：{', '.join(current.get('unstable_case_ids', [])) or '无'}。",
                "",
            ]
        )
    lines["02_stability_results.md"] = "\n".join(stability_lines)

    latency_lines = [
        "# Latency analysis",
        "",
        "以下阶段数据来自最新 `runtime_after.json` 的本地报告。P50/P95 是 case-run 统计；真实 Provider 延迟另见 `05_ab_results.md`。",
        "",
    ]
    for mode, payload in after_modes.items():
        aggregate = payload.get("aggregate", {})
        latency = aggregate.get("latency_ms", {})
        latency_lines.extend(
            [
                f"## `{mode}`",
                "",
                f"总耗时 P50/P95/最大：{fmt(latency.get('p50_ms'))}/{fmt(latency.get('p95_ms'))}/{fmt(latency.get('max_ms'))} ms。",
                "",
                stage_rows(aggregate),
                "",
            ]
        )
    latency_lines.extend(
        [
            "## Top slow cases",
            "",
            "详单见 `top_slow_cases.json`；slow case 按总耗时排序并保留阶段、计数、fallback 与终态原因，不保留原始问答。",
            "",
            f"来源：`{slow.get('source', 'docs/runtime_hardening/top_slow_cases.json')}`。",
        ]
    )
    lines["03_latency_analysis.md"] = "\n".join(latency_lines)

    lines["04_changes_applied.md"] = """# Changes applied

本轮只做了与稳定性、可观测性和浏览器验收直接相关的小改动：

1. Runtime diagnostics 补齐阶段失败状态、结果校验、任务提交和工具执行阶段。
2. 稳定性脚本保留 SSE 投影、上下文哈希、计数器和 fallback/retry 分层，避免把原始问答写入证据。
3. Playwright smoke 适配当前 Legacy Workspace 的六能力按钮和自然语言输入，不再操作已经隐藏的旧课程选择器；图片测试支持外部指定 fixture。
4. 生成本目录的机器可读证据和 markdown 交接文档。

已知验证：runtime timing 相关测试与 Ruff/Mypy 目标文件检查通过；浏览器 acceptance 在本地 FastAPI 测试服务上通过，包含输入恢复、停止按钮终态、SSE、附件边界、移动/暗色视图和多轮路径。完整历史回归曾得到 `2048 passed, 15 skipped, 6 failed`；6 个失败属于已有契约/删除 React 旧路径/模型清单等问题，不能在本报告中伪称为全绿。
"""

    ab_lines = [
        "# A/B results",
        "",
        "A=基线，B=加入现有 RAG 有界缓存与本轮诊断补齐后的运行结果。两者均为本地 mock/deterministic 口径；不把本地耗时外推为生产性能。",
        "",
        "| 模式 | 指标 | A 基线 | B 最新 | 变化 |",
        "|---|---|---:|---:|---:|",
    ]
    for mode in baseline_modes:
        before = baseline_modes[mode].get("aggregate", {}).get("latency_ms", {})
        current = after_modes.get(mode, {}).get("aggregate", {}).get("latency_ms", {})
        before_fb = aggregate_fallbacks(baseline_modes[mode])
        current_fb = aggregate_fallbacks(after_modes.get(mode, {}))
        for label, key in (("P50 ms", "p50_ms"), ("P95 ms", "p95_ms"), ("最大 ms", "max_ms"), ("平均 ms", "mean_ms")):
            ab_lines.append(
                f"| `{mode}` | {label} | {fmt(before.get(key))} | {fmt(current.get(key))} | {pct_delta(before.get(key), current.get(key))} |"
            )
        ab_lines.append(
            f"| `{mode}` | fallback 次数/率 | {before_fb['fallback_count']} / {before_fb['fallback_rate'] * 100:.2f}% | {current_fb['fallback_count']} / {current_fb['fallback_rate'] * 100:.2f}% | {pct_delta(before_fb['fallback_rate'], current_fb['fallback_rate'])} |"
        )
    ab_lines.extend(
        [
            "",
            "解释：P50 改善不能掩盖 P95 或最大值回归；长尾主要看 `rag_retrieval`、`runtime_execute`、`result_commit/task_commit` 和未配置模型导致的降级路径。fallback 率必须与失败分类一起解读，不把预期的 provider-unavailable 降级写成成功模型调用。",
            "",
        ]
    )
    if real:
        ab_lines.extend(
            [
                "## Real Provider evidence",
                "",
                f"受控真实报告：provider={', '.join(real.get('provider_scope', [])) or 'n/a'}，{real.get('case_count', 0)} 个 case-run，状态={real.get('status_counts', {})}，模型调用 {real.get('model_calls_total', 0)} 次。模型耗时 P50/P95={fmt(real.get('model_latency_ms', {}).get('p50_ms'))}/{fmt(real.get('model_latency_ms', {}).get('p95_ms'))} ms；总 case 耗时 P50/P95={fmt(real.get('elapsed_ms', {}).get('p50_ms'))}/{fmt(real.get('elapsed_ms', {}).get('p95_ms'))} ms。该报告是单独的 CT 求解切片，不是六课程生产基线。",
                "",
            ]
        )
    if browser:
        ab_lines.extend(
            [
                "## Browser evidence",
                "",
                f"`/workspace` 浏览器会话 {browser.get('sessions', 0)} 个、{browser.get('turns_in_session', 0)} 轮；首轮完成 {fmt(browser.get('first_turn_completed_ms'))} ms；console errors={browser.get('browser_console_error_count', 0)}；终态检查={browser.get('terminal_checks', {})}。",
            ]
        )
    lines["05_ab_results.md"] = "\n".join(ab_lines)

    lines["06_remaining_bottlenecks.md"] = """# Remaining bottlenecks

- 真实 Provider 覆盖仍是受控 CT 求解切片，不能代表六课程或全量任务；需要有授权的重复真实 Provider run 才能形成生产级 P50/P95。
- RAG 冷启动和检索长尾仍会主导 P95/最大值；当前缓存是有界、行为保持的优化，不等于解决了索引、嵌入或 SQLite 并发瓶颈。
- 未配置的模型别名会产生可观测的 fallback/失败日志；后续应在配置校验阶段尽早暴露，而不是等任务运行阶段触发。
- 当前 TTFT 是首个可用 SSE 内容事件，不是 token-level 首 token 时间；需要流式 Provider 级别埋点才可进一步拆分。
- 完整回归仍有既有失败项；这些失败已被分层记录，不能通过修改证据生成器掩盖。
"""

    lines["07_final_architecture.md"] = """# Final architecture

```text
Legacy Workspace (/workspace)
        |
sessions + POST /api/v1/tasks
        |
request preparation -> routing -> existing Runtime executor
        |
planner/capability -> context/RAG -> model/tool nodes
        |
reflection -> quality gate -> result validation -> task/session commit
        |
SSE projection + persisted structured result + RuntimeDiagnostics
```

诊断是横切能力，不是第二条执行链。Provider 选择仍复用既有 ModelService、Provider registry、环境变量和 HTTP 调用链；外部检索的备用 Provider 仍由既有 retrieval factory/execution 链按 tier 运行。Legacy Workspace 保持入口，未恢复已删除的 React 旧入口。仓库中没有为本任务新增第二个 Runtime、第二套 LangGraph、第二个 Planner 或第二套 Provider/Session/RAG runtime。

证据边界：local mock/deterministic 用于可重复回归，real_model 用于受控真实调用，Playwright 用于真实浏览器交互；三者在报告中分开，不互换结论。
"""

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in lines.items():
        (output_dir / name).write_text(content.rstrip() + "\n", encoding="utf-8")


def build_pack(source_dir: Path, output_dir: Path) -> None:
    baseline = load_json(source_dir / "runtime_baseline.json")
    after = load_json(source_dir / "runtime_after.json")
    stability = load_json(source_dir / "stability_results.json")
    slow = load_json(source_dir / "top_slow_cases.json")
    real_report_path = ROOT / "evaluation" / "reports" / "latest.json"
    real_report = load_json(real_report_path) if real_report_path.exists() else None

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "runtime_baseline.json", baseline)
    write_json(output_dir / "runtime_after.json", after)
    write_json(output_dir / "stability.json", stability)
    write_json(output_dir / "top_slow_cases.json", slow)
    write_json(
        output_dir / "model_call_stats.json", build_model_call_stats(after, real_report)
    )
    build_markdown(source_dir, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    build_pack(args.source_dir.resolve(), args.output_dir.resolve())
    print(f"wrote runtime efficiency pack to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
