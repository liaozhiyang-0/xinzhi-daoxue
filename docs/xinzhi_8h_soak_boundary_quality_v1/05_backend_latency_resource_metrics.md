# 05 后端耗时与资源专项

每类能力统计：count / success / failure / p50 / p90 / p95 / p99 / max。

尽量按 Trace 拆：
ingress、planning、RAG、vision、model、tool、verification、circuit、artifact、presentation。

分类型：
general、text solver、single image、multi image、RAG、research、lesson prep、assignment、learning path、governance、circuit OFF/ON/AUTO。

每15~30分钟记录：
API RSS、CPU、DB connections、Redis memory、Qdrant、MinIO、running tasks、queued tasks、lease count。

重点看趋势：
- RSS 是否单调增长
- DB connection 是否泄漏
- running task 是否累积
- lease 是否残留
- latency 是否随运行时间上升

Circuit 必须比较 baseline vs OFF vs ON vs AUTO；OFF 基本不能增加耗时。

输出：
`docs/audit/71_backend_latency_resource_report.md`
