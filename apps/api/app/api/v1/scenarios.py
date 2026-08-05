from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.contracts.scenarios import (
    ScenarioDefinition,
    ScenarioEvidenceReviewRequest,
    ScenarioEvidenceReviewResponse,
    ScenarioPreflightResponse,
)
from app.services.scenario_catalog import ScenarioCatalogError
from app.services.scenario_preflight import ScenarioPreflightService

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _preflight_for_scenario(
    scenario: ScenarioDefinition, request: Request
) -> ScenarioPreflightResponse:
    try:
        definition = request.app.state.agent_registry.get(scenario.agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    mock_available = bool(
        definition.development.mock_enabled
        and request.app.state.development_mock_provider.profile_exists(
            definition.development.mock_profile
        )
        and request.app.state.development_mock_provider.is_allowed(
            definition.agent_id
        )
    )
    return ScenarioPreflightService().check(
        scenario,
        registry=request.app.state.agent_registry,
        settings=request.app.state.settings,
        mock_available=mock_available,
    )


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


@router.get(
    "/readiness",
    response_model=list[ScenarioPreflightResponse],
)
async def list_scenario_readiness(request: Request) -> list[ScenarioPreflightResponse]:
    try:
        scenarios = request.app.state.scenario_catalog.list()
        return [_preflight_for_scenario(scenario, request) for scenario in scenarios]
    except ScenarioCatalogError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{scenario_id}", response_model=ScenarioDefinition)
async def get_scenario(scenario_id: str, request: Request) -> ScenarioDefinition:
    try:
        return request.app.state.scenario_catalog.get(scenario_id)
    except ScenarioCatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/{scenario_id}/preflight",
    response_model=ScenarioPreflightResponse,
)
async def preflight_scenario(
    scenario_id: str, request: Request
) -> ScenarioPreflightResponse:
    try:
        scenario = request.app.state.scenario_catalog.get(scenario_id)
    except ScenarioCatalogError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _preflight_for_scenario(scenario, request)


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
