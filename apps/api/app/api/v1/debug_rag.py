from __future__ import annotations

import asyncio
import json
from statistics import mean
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import PROJECT_ROOT

router = APIRouter(prefix="/debug/rag", tags=["rag-debug"])
EVAL_CASES = (
    PROJECT_ROOT / "apps" / "api" / "tests" / "fixtures" / "rag_eval_cases.json"
)


class DebugRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)
    course_id: Literal["CT", "AE", "DE"] = "CT"
    intent: Literal[
        "general_qa",
        "explain_concept",
        "summarize_knowledge",
        "learning_advice",
        "solve_problem",
    ] = "explain_concept"
    response_depth: Literal["brief", "standard", "deep"] = "standard"
    conversation_summary: str = Field(default="", max_length=1000)
    previous_answer_summary: str = Field(default="", max_length=1000)
    use_rag: bool = True
    include_images: bool = False
    use_reranker: bool = False
    allow_cloud: bool = False
    request_id: str = Field(default="", max_length=128)


class CompareRequest(DebugRunRequest):
    comparison_mode: Literal["rag_vs_no_rag", "cloud_vs_local"] = "rag_vs_no_rag"


class EvalRequest(BaseModel):
    group: Literal["all", "CT", "AE", "DE", "boundary", "degradation"] = "all"
    allow_cloud: bool = False
    limit: int = Field(default=60, ge=1, le=60)


def _default_prewarm_models() -> list[Literal["text", "image", "reranker"]]:
    return ["text"]


class PrewarmRequest(BaseModel):
    models: list[Literal["text", "image", "reranker"]] = Field(
        default_factory=_default_prewarm_models
    )


def _ensure_enabled(request: Request, *, write: bool = True) -> None:
    settings = request.app.state.settings
    if not settings.rag_debug_enabled:
        raise HTTPException(status_code=404, detail="RAG Debug 未启用")
    if write and settings.app_env == "production":
        raise HTTPException(status_code=403, detail="生产环境禁用 RAG Debug 写操作")


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
    return ordered[index]


def _hit_matches_expectation(
    hit: dict[str, Any],
    expected_types: set[str],
    expected_keywords: list[str],
    expected_chapters: list[str],
) -> bool:
    searchable = " ".join(
        str(hit.get(field, "")) for field in ("title", "chapter", "content")
    ).casefold()
    return bool(
        (expected_types and hit.get("content_type") in expected_types)
        or any(keyword in searchable for keyword in expected_keywords)
        or any(chapter in searchable for chapter in expected_chapters)
    )


@router.get("/status", response_model=dict[str, Any])
async def status(request: Request) -> dict[str, Any]:
    _ensure_enabled(request, write=False)
    settings = request.app.state.settings
    health = request.app.state.rag_retrieval.health()
    learner = request.app.state.agent_registry.get("LEARN_01_KNOWLEDGE_QA_V1")
    provider_status = getattr(request.app.state.provider, "runtime_status", None)
    return {
        "api_status": "ready",
        "provider": request.app.state.provider.provider_name,
        "provider_available": bool(
            getattr(request.app.state.provider, "is_available", True)
        ),
        "learn_enabled": learner.enabled,
        "learn_publication_status": learner.publication_status,
        "learn_flow_configured": bool(
            request.app.state.agent_registry.resolve_flow_id(learner.agent_id, settings)
        ),
        "cpu_mode": settings.text_embedding_device == "cpu",
        "rag_enabled": settings.rag_enabled,
        "debug_write_enabled": settings.app_env != "production",
        "provider_runtime": provider_status() if provider_status else {},
        "agent_count": len(request.app.state.agent_registry.list_agents()),
        **health,
    }


@router.post("/run", response_model=dict[str, Any])
async def run_debug(payload: DebugRunRequest, request: Request) -> dict[str, Any]:
    _ensure_enabled(request)
    return await request.app.state.rag_debug.run(payload.model_dump())


@router.post("/prewarm", response_model=dict[str, Any])
async def prewarm(payload: PrewarmRequest, request: Request) -> dict[str, Any]:
    """Explicitly load selected local models without loading them at startup."""
    _ensure_enabled(request)
    service = request.app.state.rag_retrieval
    providers = {
        "text": service.text_provider,
        "image": service.image_provider,
        "reranker": service.reranker,
    }
    loaded: list[str] = []
    for model_name in dict.fromkeys(payload.models):
        await asyncio.to_thread(providers[model_name].load)
        loaded.append(model_name)
    return {
        "prewarmed": loaded,
        "health": request.app.state.rag_retrieval.health(),
    }


@router.post("/compare", response_model=dict[str, Any])
async def compare(payload: CompareRequest, request: Request) -> dict[str, Any]:
    _ensure_enabled(request)
    base = payload.model_dump(exclude={"comparison_mode"})
    if payload.comparison_mode == "rag_vs_no_rag":
        a = {**base, "use_rag": True}
        b = {**base, "use_rag": False}
    else:
        a = {**base, "allow_cloud": True}
        b = {**base, "allow_cloud": False}
    return {
        "mode": payload.comparison_mode,
        "a": await request.app.state.rag_debug.run(a),
        "b": await request.app.state.rag_debug.run(b),
        "manual_review_required": True,
    }


@router.get("/traces/{trace_id}", response_model=dict[str, Any])
async def trace(trace_id: str, request: Request) -> dict[str, Any]:
    _ensure_enabled(request, write=False)
    if not trace_id.startswith("debug_rag_") or len(trace_id) > 80:
        raise HTTPException(status_code=400, detail="trace_id 无效")
    item = request.app.state.rag_debug.store.get(trace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Trace 不存在或已过期")
    return item


@router.post("/eval", response_model=dict[str, Any])
async def evaluate(payload: EvalRequest, request: Request) -> dict[str, Any]:
    _ensure_enabled(request)
    try:
        raw_cases = await asyncio.to_thread(EVAL_CASES.read_text, encoding="utf-8")
        cases = json.loads(raw_cases)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="评测集不可用") from exc
    selected = [
        item
        for item in cases
        if payload.group == "all"
        or item.get("course_id") == payload.group
        or item.get("group") == payload.group
    ][: payload.limit]
    results: list[dict[str, Any]] = []
    for case in selected:
        if not case.get("question"):
            results.append(
                {
                    "case_id": case["case_id"],
                    "passed": True,
                    "manual_review_required": False,
                    "status": "rejected_empty_input",
                }
            )
            continue
        try:
            trace_result = await request.app.state.rag_debug.run(
                {
                    "question": case["question"],
                    "course_id": case.get("course_id", "CT"),
                    "intent": case.get("intent", "explain_concept"),
                    "use_rag": True,
                    "include_images": case.get("should_have_images", False),
                    "use_reranker": False,
                    "allow_cloud": payload.allow_cloud,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "case_id": case["case_id"],
                    "passed": case.get("expected_status") in {"rejected", "misrouted"},
                    "route_ok": False,
                    "top1_relevant": False,
                    "top3_relevant": False,
                    "cross_course": False,
                    "citation_legal": True,
                    "citation_used": False,
                    "cloud_success": False,
                    "local_fallback": False,
                    "latency_ms": 0,
                    "manual_review_required": False,
                    "status": f"rejected:{type(exc).__name__}",
                }
            )
            continue
        retrieval = trace_result["retrieval"]
        hits = retrieval.get("hits", [])
        cross_course = [
            hit for hit in hits if hit.get("course_id") != case.get("course_id")
        ]
        expected_types = set(case.get("expected_content_types", []))
        expected_keywords = [
            str(item).casefold() for item in case.get("expected_keywords", [])
        ]
        expected_chapters = [
            str(item).casefold() for item in case.get("expected_chapters", [])
        ]

        has_expectation = bool(expected_types or expected_keywords or expected_chapters)
        top3_relevant = bool(
            not has_expectation
            or any(
                _hit_matches_expectation(
                    hit,
                    expected_types,
                    expected_keywords,
                    expected_chapters,
                )
                for hit in hits[:3]
            )
        )
        top1_relevant = bool(
            not has_expectation
            or (
                hits
                and _hit_matches_expectation(
                    hits[0],
                    expected_types,
                    expected_keywords,
                    expected_chapters,
                )
            )
        )
        route_ok = trace_result["route"].get("agent_id") == case.get(
            "expected_route"
        ) or trace_result["route"].get("original_agent_id") == case.get(
            "expected_route"
        )
        citation_status = trace_result["citation_validation"].get("status")
        final_citations = trace_result["final"].get("citations", [])
        cloud_status = trace_result["cloud"].get("status")
        expects_misroute = case.get("expected_status") == "misrouted"
        misrouted_evaluated = bool(
            expects_misroute
            and payload.allow_cloud
            and cloud_status not in {None, "not_run", "cloud_failed"}
        )
        results.append(
            {
                "case_id": case["case_id"],
                "passed": route_ok and not cross_course and top3_relevant,
                "route_ok": route_ok,
                "course_ok": all(
                    hit.get("course_id") == case.get("course_id") for hit in hits
                ),
                "intent_ok": trace_result["route"].get("intent") == case.get("intent"),
                "top1_relevant": top1_relevant,
                "top3_relevant": top3_relevant,
                "cross_course": bool(cross_course),
                "citation_legal": citation_status in {"passed", "not_run"},
                "citation_used": bool(final_citations),
                "cloud_status": cloud_status,
                "cloud_success": cloud_status in {"success", "completed", "partial"},
                "misrouted_evaluated": misrouted_evaluated,
                "misrouted_ok": (
                    cloud_status == "misrouted" if misrouted_evaluated else None
                ),
                "local_fallback": bool(trace_result["final"].get("fallback_used")),
                "latency_ms": trace_result["final"]["total_latency_ms"],
                "retrieval_latency_ms": retrieval.get("latency_ms", 0),
                "cloud_latency_ms": trace_result["cloud"].get("latency_ms", 0),
                "manual_review_required": True,
                "trace_id": trace_result["trace_id"],
            }
        )
    total = len(results)
    latencies = [float(item.get("latency_ms", 0)) for item in results]
    retrieval_latencies = [
        float(item.get("retrieval_latency_ms", 0)) for item in results
    ]
    cloud_latencies = [
        float(item.get("cloud_latency_ms", 0))
        for item in results
        if item.get("cloud_latency_ms")
    ]
    misrouted_results = [item for item in results if item.get("misrouted_evaluated")]
    return {
        "group": payload.group,
        "total": total,
        "passed": sum(bool(item.get("passed")) for item in results),
        "failed": sum(not bool(item.get("passed")) for item in results),
        "manual_review_required": sum(
            bool(item.get("manual_review_required")) for item in results
        ),
        "route_accuracy": (
            sum(bool(item.get("route_ok", True)) for item in results) / total
            if total
            else 0
        ),
        "course_accuracy": (
            sum(bool(item.get("course_ok", True)) for item in results) / total
            if total
            else 0
        ),
        "intent_accuracy": (
            sum(bool(item.get("intent_ok", True)) for item in results) / total
            if total
            else 0
        ),
        "top1_relevance_rate": (
            sum(bool(item.get("top1_relevant", True)) for item in results) / total
            if total
            else 0
        ),
        "top3_recall_proxy": (
            sum(bool(item.get("top3_relevant", True)) for item in results) / total
            if total
            else 0
        ),
        "cross_course_evidence_rate": (
            sum(bool(item.get("cross_course")) for item in results) / total
            if total
            else 0
        ),
        "citation_legal_rate": (
            sum(bool(item.get("citation_legal", True)) for item in results) / total
            if total
            else 0
        ),
        "citation_usage_rate": (
            sum(bool(item.get("citation_used")) for item in results) / total
            if total
            else 0
        ),
        "cloud_success_rate": (
            sum(bool(item.get("cloud_success")) for item in results) / total
            if total
            else 0
        ),
        "local_fallback_rate": (
            sum(bool(item.get("local_fallback")) for item in results) / total
            if total
            else 0
        ),
        "misrouted_evaluated": len(misrouted_results),
        "misrouted_accuracy": (
            sum(bool(item.get("misrouted_ok")) for item in misrouted_results)
            / len(misrouted_results)
            if misrouted_results
            else None
        ),
        "average_latency_ms": mean(latencies) if latencies else 0,
        "p50_retrieval_latency_ms": _percentile(retrieval_latencies, 0.5),
        "p95_retrieval_latency_ms": _percentile(retrieval_latencies, 0.95),
        "p50_cloud_latency_ms": _percentile(cloud_latencies, 0.5),
        "p95_cloud_latency_ms": _percentile(cloud_latencies, 0.95),
        "p50_total_latency_ms": _percentile(latencies, 0.5),
        "p95_total_latency_ms": _percentile(latencies, 0.95),
        "results": results,
    }
