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
