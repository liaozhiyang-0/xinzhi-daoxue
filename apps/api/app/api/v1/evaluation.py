from __future__ import annotations

import json
from collections import Counter

from fastapi import APIRouter, HTTPException, Request

from app.core.config import PROJECT_ROOT
from app.evaluation.loader import EvaluationCaseLoader

router = APIRouter(prefix="/evaluation", tags=["evaluation"])
CASE_ROOT = PROJECT_ROOT / "evaluation" / "cases"
REPORT_PATH = PROJECT_ROOT / "evaluation" / "reports" / "latest.json"


def _require_enabled(request: Request) -> None:
    if not request.app.state.settings.enable_evaluation_api:
        raise HTTPException(status_code=404, detail="evaluation API is disabled")


@router.get("/suites")
async def list_suites(request: Request) -> dict[str, object]:
    _require_enabled(request)
    cases = EvaluationCaseLoader(CASE_ROOT).load_all()
    return {
        "case_count": len(cases),
        "by_course": dict(Counter(item.course for item in cases)),
        "by_task_family": dict(Counter(item.task_family for item in cases)),
        "case_ids": [item.case_id for item in cases],
        "execution_via_http": False,
    }


@router.get("/reports/latest")
async def latest_report(request: Request) -> dict[str, object]:
    _require_enabled(request)
    if not REPORT_PATH.is_file():
        raise HTTPException(status_code=404, detail="evaluation report not found")
    value = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HTTPException(status_code=500, detail="invalid evaluation report")
    return value
