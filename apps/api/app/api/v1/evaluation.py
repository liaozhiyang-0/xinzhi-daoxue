from __future__ import annotations

import json
from collections import Counter
from statistics import mean

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import PROJECT_ROOT
from app.dependencies import get_current_principal
from app.evaluation.contracts import EvaluationReportSummary, SuiteReport
from app.evaluation.loader import EvaluationCaseLoader
from app.evaluation.reporting import build_report_summary
from app.observability.model_tracer import ModelCallRecord
from app.services.auth_service import Principal

router = APIRouter(prefix="/evaluation", tags=["evaluation"])
CASE_ROOT = PROJECT_ROOT / "evaluation" / "cases"
REPORT_PATH = PROJECT_ROOT / "evaluation" / "reports" / "latest.json"


def _require_enabled(request: Request, principal: Principal) -> None:
    if not request.app.state.settings.enable_evaluation_api:
        raise HTTPException(status_code=404, detail="evaluation API is disabled")
    if request.app.state.settings.auth_required and (
        not principal.authenticated or principal.role not in {"teacher", "admin"}
    ):
        raise HTTPException(status_code=403, detail="需要教师或管理员权限")


@router.get("/suites")
async def list_suites(
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> dict[str, object]:
    _require_enabled(request, principal)
    cases = EvaluationCaseLoader(CASE_ROOT).load_all()
    return {
        "case_count": len(cases),
        "by_course": dict(Counter(item.course for item in cases)),
        "by_task_family": dict(Counter(item.task_family for item in cases)),
        "case_ids": [item.case_id for item in cases],
        "execution_via_http": False,
    }


@router.get("/reports/latest")
async def latest_report(
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> dict[str, object]:
    _require_enabled(request, principal)
    if not REPORT_PATH.is_file():
        raise HTTPException(status_code=404, detail="evaluation report not found")
    value = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HTTPException(status_code=500, detail="invalid evaluation report")
    return value


@router.get("/reports/latest/summary", response_model=EvaluationReportSummary)
async def latest_report_summary(
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> EvaluationReportSummary:
    _require_enabled(request, principal)
    if not REPORT_PATH.is_file():
        raise HTTPException(status_code=404, detail="evaluation report not found")
    try:
        report = SuiteReport.model_validate_json(
            REPORT_PATH.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail="invalid evaluation report",
        ) from exc
    return build_report_summary(report)


@router.get("/observability/model-calls", response_model=dict[str, object])
async def model_call_observability(
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> dict[str, object]:
    _require_enabled(request, principal)
    records = [
        item
        for item in request.app.state.model_tracer.list()
        if isinstance(item, ModelCallRecord)
    ]
    elapsed = [item.elapsed_ms for item in records]
    return {
        "version": "v1",
        "retention": "bounded_process_memory",
        "raw_prompts_stored": False,
        "retained_record_count": len(records),
        "status_counts": dict(Counter(item.status for item in records)),
        "provider_counts": dict(Counter(item.provider for item in records)),
        "model_counts": dict(Counter(item.model for item in records)),
        "task_type_counts": dict(Counter(item.task_type for item in records)),
        "total_elapsed_ms": sum(elapsed),
        "average_elapsed_ms": round(mean(elapsed), 2) if elapsed else 0,
        "warnings": [
            "process_memory_only",
            "metadata_only_no_prompt_or_reasoning",
        ],
    }
