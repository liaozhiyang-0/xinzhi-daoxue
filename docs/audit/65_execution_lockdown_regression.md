# Execution Lockdown Regression

Date: 2026-08-25

## Commands and results

- Ruff on changed Python lockdown files: passed.
- `pytest apps/api/tests/test_execution_surface_lockdown.py`: 3 passed.
- Runtime boundary/adapter/subagent/planner/orchestration/trace group: 30 passed, 2 warnings.
- `pytest apps/api/tests/test_student_web.py` after updating its stale assertion: 3 passed, 2 warnings.
- `pytest apps/api/tests/test_config_validation.py`: 17 passed, 2 warnings.
- `node --check apps/api/app/static/debug/workspace.js`: passed.
- Earlier focused pre-lockdown regression recorded in the baseline report: 83 passed, 2 warnings.

## Browser result

One real task was submitted at `http://127.0.0.1:8000/workspace` after restart. It used `planner_active`, completed through Runtime, displayed the returned answer and two course materials, and had no console errors after reload.

## Known non-result

The broad frontend command initially found one stale test assertion for the removed `renderInline` call. The code and assertion were corrected, and the affected test then passed. The full requested browser matrix, Mypy, Docker validation and long-run soak were not claimed as passed.
