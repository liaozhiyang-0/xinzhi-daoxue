from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.contracts.scenarios import (
    ScenarioDefinition,
    ScenarioEvidenceReviewRequest,
    ScenarioEvidenceReviewResponse,
)
from app.services.scenario_catalog import ScenarioCatalogError

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioDefinition])
async def list_scenarios(
    request: Request,
    course: str | None = Query(default=None, max_length=32),
    role: str | None = Query(default=None, max_length=32),
) -> list[ScenarioDefinition]:
    try:
        return request.app.state.scenario_catalog.list(course=course, role=role)
    except ScenarioCatalogError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{scenario_id}", response_model=ScenarioDefinition)
async def get_scenario(scenario_id: str, request: Request) -> ScenarioDefinition:
    try:
        return request.app.state.scenario_catalog.get(scenario_id)
    except ScenarioCatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{scenario_id}/evidence-review",
    response_model=ScenarioEvidenceReviewResponse,
)
async def review_scenario_evidence(
    scenario_id: str,
    payload: ScenarioEvidenceReviewRequest,
    request: Request,
) -> ScenarioEvidenceReviewResponse:
    try:
        scenario = request.app.state.scenario_catalog.get(scenario_id)
    except ScenarioCatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return request.app.state.scenario_evidence_review.review(scenario, payload)
