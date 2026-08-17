# Task Worker

`TaskWorker` is the process boundary for Redis-backed task execution. The API
publishes task IDs when `TASK_EXECUTOR_MODE=redis`; this process owns the
`TaskExecutor`/`RuntimeTaskEngine`, database lease claims, heartbeats, Runtime
checkpoints, and provider calls.

Run locally from the repository root:

```powershell
$env:PYTHONPATH = "apps/api"
.venv\Scripts\python.exe apps/worker/worker.py
```

Use exactly one API and one worker process. For the Compose profile, set
`TASK_EXECUTOR_MODE=redis` and start `api` plus the `queue-worker` profile.
The database lease and periodic recovery scan provide at-least-once recovery
when a worker exits after receiving a Redis message.

The Redis list transport tracks delivery attempts for each task ID. If a
dispatch raises, the worker requeues the ID up to
`TASK_QUEUE_DEAD_LETTER_MAX_ATTEMPTS` times. After the limit it moves the ID to
the `{queue_name}:dead-letter` list. A dispatch that returns ``False`` is treated
as an already-owned duplicate or shutdown signal and is acknowledged without
dead-lettering, because the database lease remains the authoritative recovery
source. This protects against poison dispatch messages without hiding live tasks.

Transport-level metrics are available through `TaskQueue.metrics()`:
`pending` (waiting Redis messages), `dead_letter`, and `attempts` (in-flight
delivery attempts). When `TASK_EXECUTOR_MODE=redis`, the API health endpoint
(`GET /health`) includes these metrics under the `task_queue` field. These are
useful for a liveness/health probe or a monitoring scraper, but task-level
latency and failure classification still come from the database-backed task and
runtime tables.
