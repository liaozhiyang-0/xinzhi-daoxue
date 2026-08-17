# 统一可观测性

本文描述当前版本提供的统一可观测性出口。它把任务、模型、Trace 和任务队列指标聚合到同一份快照，并提供 Prometheus 文本格式，便于接入现有监控体系。

## 出口

| 路径 | 格式 | 用途 |
|---|---|---|
| `GET /api/v1/observability/summary` | JSON | 人工排查、调试、内部系统调用 |
| `GET /api/v1/observability/metrics` | Prometheus text | 可被 Prometheus 直接抓取 |
| `GET /metrics` | Prometheus text | 根路径别名，便于标准采集器配置 |
| `GET /health` | JSON | 健康检查；Redis 模式下额外包含 `task_queue` 指标 |

## 指标分组

### 任务指标

来自最近 200 条任务记录和数据库状态分组：

- `xzd_task_status_total{status="..."}`：按当前状态统计任务数；
- `xzd_task_recent_total`：最近采样任务数；
- `xzd_task_latency_ms_sum`：最近任务执行延迟总和；
- `xzd_task_latency_ms_p95`：最近任务执行延迟 p95；
- `xzd_task_queue_latency_ms_sum`：最近任务排队等待延迟总和。

### 模型指标

来自 `ModelTracer` 内存记录：

- `xzd_model_call_total`
- `xzd_model_error_total`
- `xzd_model_fallback_total`
- `xzd_model_latency_ms_sum`
- `xzd_model_prompt_tokens_total`
- `xzd_model_completion_tokens_total`
- `xzd_model_total_tokens_total`
- `xzd_model_provider_calls_total{provider="..."}`
- `xzd_model_calls_total{model="..."}`

### Trace 指标

来自 `TraceStore` 内存摘要：

- `xzd_trace_total`
- `xzd_trace_node_total`
- `xzd_trace_route_status_total{status="..."}`

### 队列指标

来自 `TaskQueue.metrics()`：

- `xzd_queue_pending`
- `xzd_queue_dead_letter`
- `xzd_queue_attempts`

## 当前边界

- `TraceStore` 和 `ModelTracer` 仍是有界内存存储，进程重启后会清零；
- 任务指标来自数据库查询，因此能跨重启保留；
- 当前是聚合快照，尚未写入 OpenTelemetry/ClickHouse 等外部后端；
- 后续可在 `app/observability/metrics.py` 中扩展 exporter，把同一份快照推送到 OTLP 或日志采集器。

## 接入 Prometheus 示例

```yaml
scrape_configs:
  - job_name: xinzhi-daoxue
    metrics_path: /metrics
    static_configs:
      - targets: ["127.0.0.1:8000"]
```
