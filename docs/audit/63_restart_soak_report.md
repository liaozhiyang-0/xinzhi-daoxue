# Restart / Soak Report

Date: 2026-08-25

## Observed restart

One complete stop/start cycle was executed after the execution-surface changes. The service returned HTTP health `ready`; PostgreSQL, Redis, MinIO and the configured local provider were healthy. The second start emitted:

`PRODUCTION_EXECUTION_FINGERPRINT fingerprint=dc773192222132ba32624b5d66315873e216656c24d2da62e5bf7de3ed145b4c build_id=c0e68cf847aa4ccdc38299822932646210f6ee6e-dirty runtime_generation=runtime-v3 planner_version=planner-v1`

RAG model warmup completed successfully. Warmup was approximately 81.9 seconds on this machine; this is startup cost, not a legacy-chain retry.

## Browser confirmation after restart

The live `/workspace` task completed through `planner_active` and the current Runtime, returned a knowledge answer with two course materials, and showed no browser console error after the minimal `renderInline` compatibility fix.

## Matrix status

| Scenario | Status |
|---|---|
| One complete stop/start/submit cycle | passed |
| Ten cold-start rounds | not run |
| Long-running multi-modal soak | not run |
| Hot code change with retained Redis/DB state | partially exercised by this restart; not a full matrix |
| Browser 20/10/10/5/10 matrix | not run |
