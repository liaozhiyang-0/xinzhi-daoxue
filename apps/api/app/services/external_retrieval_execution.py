"""Provider-facing external retrieval orchestration.

This service owns query planning, provider fan-out, paper review, result
merging, bounded full-text enrichment, and cooperative timeout handling. The
Runtime services depend on this capability boundary rather than reimplementing
provider policy themselves.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from time import perf_counter

from app.agents.internal.contracts import AcademicSearchPlan
from app.contracts import (
    AgentRequest,
    ExternalRetrievalPolicy,
    ExternalRetrievalResult,
)
from app.core.config import Settings
from app.providers.retrieval.academic import (
    AcademicSearchService,
    merge_academic_results,
)
from app.services.academic_paper_review import AcademicPaperReviewService
from app.services.academic_search_planner import (
    AcademicSearchPlannerService,
    requested_minimum,
)
from app.services.external_research_answer import (
    filter_research_evidence,
    is_academic_search_follow_up,
    normalize_academic_search_query,
)
from app.services.external_retrieval import (
    ExternalContentFetcher,
    ExternalFetchError,
)

logger = logging.getLogger(__name__)
ExternalRetrievalCallable = Callable[..., Awaitable[ExternalRetrievalResult]]


def _retrieval_trace_id(request: AgentRequest) -> str:
    """Prefer the Runtime effect identity over the request-level trace."""

    options = request.options
    return str(
        options.get("external_retrieval_trace_id")
        or options.get("trace_id", "")
    )


class ExternalRetrievalExecutionService:
    """Execute bounded external retrieval under a declarative policy."""

    def __init__(
        self,
        *,
        settings: Settings,
        external_search: AcademicSearchService | None,
        external_fetcher: ExternalContentFetcher | None,
        external_paper_reviewer: AcademicPaperReviewService | None,
        external_search_planner: AcademicSearchPlannerService | None,
    ) -> None:
        self.settings = settings
        self.external_search = external_search
        self.external_fetcher = external_fetcher
        self.external_paper_reviewer = external_paper_reviewer
        self.external_search_planner = external_search_planner
        self._external_tasks: set[asyncio.Task[ExternalRetrievalResult]] = set()

    async def retrieve(
        self,
        request: AgentRequest,
        policy: ExternalRetrievalPolicy,
        *,
        allow_degraded_review: bool = False,
    ) -> ExternalRetrievalResult:
        query = self._external_query(request)
        retrieval_trace_id = _retrieval_trace_id(request)
        if self.external_search is None or not query:
            return ExternalRetrievalResult(
                query=query or "external retrieval",
                normalized_query=query or "external retrieval",
                source_scopes=list(policy.source_scopes),
                status="disabled",
                retrieval_trace_id=retrieval_trace_id,
            )
        started = perf_counter()
        result: ExternalRetrievalResult | None = None
        try:
            async with asyncio.timeout(
                min(
                    policy.timeout_seconds,
                    self.settings.external_retrieval_timeout_seconds,
                )
            ):
                planner_warning: str | None = None
                plan: AcademicSearchPlan | None = None
                if self.external_search_planner is not None:
                    plan, planner_warning = await self.external_search_planner.plan(
                        query,
                        request_id=str(request.options.get("request_id", "")),
                        research_intent=(
                            request.options.get("research_intent")
                            if isinstance(
                                request.options.get("research_intent"), dict
                            )
                            else None
                        ),
                    )
                explicit_minimum = requested_minimum(query)
                if plan is not None and explicit_minimum is not None:
                    plan = plan.model_copy(
                        update={
                            "minimum_results": max(
                                plan.minimum_results,
                                min(explicit_minimum, 20),
                            )
                        }
                    )
                display_limit = min(
                    policy.max_results, self.settings.external_retrieval_max_results
                )
                max_rounds = max(1, min(policy.max_iterations, 5))
                round_results: list[ExternalRetrievalResult] = []
                used_queries: set[str] = set()
                previous_retrieval = request.options.get("previous_external_retrieval")
                if isinstance(
                    previous_retrieval, dict
                ) and is_academic_search_follow_up(
                    self._knowledge_query(request),
                    previous_agent=str(request.options.get("previous_agent", "")),
                    previous_answer_summary=str(
                        request.options.get("previous_answer_summary", "")
                    ),
                    previous_query=str(
                        request.options.get("previous_external_query", "")
                    ),
                ):
                    try:
                        previous_result = ExternalRetrievalResult.model_validate(
                            previous_retrieval
                        )
                    except Exception:
                        previous_result = None
                    if previous_result is not None and previous_result.items:
                        round_results.append(
                            previous_result.model_copy(update={"search_round": 1})
                        )
                        used_queries.update(previous_result.search_queries)
                for search_round in range(1, max_rounds + 1):
                    query_variants = (
                        plan.search_queries
                        if plan is not None
                        else [normalize_academic_search_query(query)]
                    )
                    query_variants = [
                        value for value in query_variants if value not in used_queries
                    ] or query_variants
                    used_queries.update(query_variants)
                    prefer_high_citation = bool(
                        plan is not None
                        and plan.citation_preference in {"prefer_high", "required"}
                    )
                    freshness_days = (
                        None if prefer_high_citation else policy.freshness_days
                    )
                    search_many = getattr(self.external_search, "search_many", None)
                    if callable(search_many):
                        round_result = await search_many(
                            query,
                            query_variants=query_variants,
                            limit=display_limit,
                            provider_names=policy.providers,
                            source_scopes=policy.source_scopes,
                            freshness_days=freshness_days,
                            prefer_high_citation=prefer_high_citation,
                            retrieval_trace_id=retrieval_trace_id,
                        )
                    else:
                        round_result = await self.external_search.search(
                            query,
                            normalized_query=query_variants[0],
                            limit=display_limit,
                            provider_names=policy.providers,
                            source_scopes=policy.source_scopes,
                            freshness_days=freshness_days,
                            retrieval_trace_id=retrieval_trace_id,
                        )
                    if planner_warning and search_round == 1:
                        round_result.warnings = [
                            planner_warning,
                            *round_result.warnings,
                        ][:20]
                    if self.external_paper_reviewer is not None:
                        round_result = await self.external_paper_reviewer.review(
                            query,
                            round_result,
                            request_id=str(request.options.get("request_id", "")),
                            allow_non_academic=isinstance(
                                request.options.get("research_intent"), dict
                            ),
                            allow_degraded=allow_degraded_review,
                            required_concepts=(
                                plan.required_concepts if plan is not None else ()
                            ),
                            excluded_concepts=(
                                plan.excluded_concepts if plan is not None else ()
                            ),
                        )
                    round_result = round_result.model_copy(
                        update={"search_round": search_round}
                    )
                    round_results.append(round_result)
                    result = merge_academic_results(
                        round_results,
                        query=query,
                        limit=display_limit,
                        prefer_high_citation=prefer_high_citation,
                        search_round=search_round,
                        retrieval_trace_id=retrieval_trace_id,
                    )
                    if plan is None or result.approved_count >= plan.minimum_results:
                        break
                    if (
                        self.external_search_planner is None
                        or search_round >= max_rounds
                    ):
                        break
                    next_plan, refinement_warning = (
                        await self.external_search_planner.refine(
                            query,
                            plan,
                            result,
                            round_number=search_round,
                            request_id=str(request.options.get("request_id", "")),
                        )
                    )
                    if refinement_warning or next_plan is None:
                        result.warnings = [
                            *result.warnings,
                            refinement_warning or "search refinement unavailable",
                        ][:20]
                        break
                    next_queries = [
                        value
                        for value in next_plan.search_queries
                        if value not in used_queries
                    ]
                    if not next_queries:
                        result.warnings = [
                            *result.warnings,
                            "search refinement returned no new query variants",
                        ][:20]
                        break
                    plan = next_plan.model_copy(
                        update={
                            "search_queries": next_queries,
                            "minimum_results": plan.minimum_results,
                            "citation_preference": (
                                plan.citation_preference
                                if plan.citation_preference != "not_requested"
                                else next_plan.citation_preference
                            ),
                        }
                    )
                if result is None:
                    result = ExternalRetrievalResult(
                        query=query,
                        normalized_query=query,
                        source_scopes=list(policy.source_scopes),
                        status="failed",
                        retrieval_trace_id=retrieval_trace_id,
                    )
                filtered_items = filter_research_evidence(query, result.items)
                if len(filtered_items) != len(result.items):
                    result = result.model_copy(
                        update={
                            "items": filtered_items,
                            "approved_count": min(
                                result.approved_count, len(filtered_items)
                            ),
                            "warnings": [
                                *result.warnings,
                                "cross-topic evidence was removed before display",
                            ][:20],
                        }
                    )
                if (
                    plan is not None
                    and explicit_minimum is not None
                    and result.approved_count < plan.minimum_results
                ):
                    result.warnings = [
                        *result.warnings,
                        f"model-approved {result.approved_count} papers; "
                        f"requested at least {plan.minimum_results}",
                    ][:20]
                if (
                    policy.allow_full_text
                    and self.settings.external_retrieval_allow_full_text
                    and self.external_fetcher is not None
                ):
                    result = await self._fetch_external_items(result, policy)
        except TimeoutError:
            if result is not None:
                result = result.model_copy(
                    update={
                        "status": "partial",
                        "warnings": [
                            *result.warnings,
                            "external retrieval timed out; showing partial results",
                        ][:20],
                    }
                )
            else:
                result = ExternalRetrievalResult(
                    query=query,
                    normalized_query=" ".join(query.split()),
                    source_scopes=list(policy.source_scopes),
                    status="failed",
                    warnings=["external retrieval timed out"],
                )
        except Exception as exc:
            logger.warning(
                "external_retrieval_failed task_id=%s provider_error=%s",
                request.task_id,
                type(exc).__name__,
            )
            if result is None or not result.items:
                result = ExternalRetrievalResult(
                    query=query,
                    normalized_query=" ".join(query.split()),
                    source_scopes=list(policy.source_scopes),
                    status="failed",
                    warnings=["external retrieval failed"],
                )
            else:
                result = result.model_copy(
                    update={
                        "status": "partial",
                        "warnings": [
                            *result.warnings,
                            "external retrieval stopped after a partial result",
                        ][:20],
                    }
                )
        assert result is not None
        result.latency_ms = max(0, int((perf_counter() - started) * 1000))
        return result

    async def retrieve_with_deadline(
        self,
        request: AgentRequest,
        policy: ExternalRetrievalPolicy,
        *,
        allow_degraded_review: bool = False,
        retrieval: ExternalRetrievalCallable | None = None,
    ) -> ExternalRetrievalResult:
        """Bound one retrieval call and retain late tasks for shutdown.

        ``retrieval`` is an injectable hook used by the Runtime gateway and
        hard-deadline tests. Normal callers use this
        service's own ``retrieve`` implementation.
        """

        timeout_seconds = min(
            policy.timeout_seconds,
            self.settings.external_retrieval_timeout_seconds,
        )
        worker = retrieval or self.retrieve
        async def run_retrieval() -> ExternalRetrievalResult:
            return await worker(
                request,
                policy,
                allow_degraded_review=allow_degraded_review,
            )

        retrieval_task = asyncio.create_task(
            run_retrieval(),
            name=f"xzd-external-retrieval-{request.task_id}",
        )
        self._external_tasks.add(retrieval_task)
        retrieval_task.add_done_callback(self._discard_external_task)
        try:
            done, _ = await asyncio.wait(
                (retrieval_task,), timeout=max(0.01, timeout_seconds)
            )
        except asyncio.CancelledError:
            retrieval_task.cancel()
            raise
        if retrieval_task in done:
            return retrieval_task.result()

        retrieval_task.cancel()
        logger.warning(
            "external_retrieval_hard_deadline task_id=%s timeout_seconds=%s",
            request.task_id,
            timeout_seconds,
        )
        query = self._external_query(request) or "external retrieval"
        return ExternalRetrievalResult(
            query=query,
            normalized_query=" ".join(query.split()),
            source_scopes=list(policy.source_scopes),
            status="failed",
            warnings=["external retrieval timed out"],
            latency_ms=max(0, int(timeout_seconds * 1000)),
            retrieval_trace_id=_retrieval_trace_id(request),
        )

    def _discard_external_task(
        self, task: asyncio.Task[ExternalRetrievalResult]
    ) -> None:
        self._external_tasks.discard(task)
        if task.cancelled():
            return
        try:
            task.exception()
        except BaseException:
            # Consume late child errors after a hard-deadline response.
            return

    async def shutdown(self) -> None:
        """Cancel retrievals that outlived their user-facing deadline."""

        active = [task for task in self._external_tasks if not task.done()]
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)

    async def _fetch_external_items(
        self,
        result: ExternalRetrievalResult,
        policy: ExternalRetrievalPolicy,
    ) -> ExternalRetrievalResult:
        if self.external_fetcher is None or policy.max_fetches <= 0:
            return result
        selected = result.items[: policy.max_fetches]
        responses = await asyncio.gather(
            *(
                self.external_fetcher.fetch(
                    item,
                    max_chars=self.settings.external_retrieval_max_content_chars,
                )
                for item in selected
            ),
            return_exceptions=True,
        )
        enriched = []
        warnings = list(result.warnings)
        for item, response in zip(selected, responses, strict=True):
            if isinstance(response, ExternalFetchError):
                warnings.append(f"{item.evidence_id}: content unavailable")
                enriched.append(item)
            elif isinstance(response, BaseException):
                warnings.append(f"{item.evidence_id}: content unavailable")
                enriched.append(item)
            else:
                enriched.append(response)
        enriched.extend(result.items[len(selected) :])
        return result.model_copy(update={"items": enriched, "warnings": warnings})

    @staticmethod
    def _knowledge_query(request: AgentRequest) -> str:
        for key in ("text", "question", "problem", "query", "prompt"):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @classmethod
    def _external_query(cls, request: AgentRequest) -> str:
        current = cls._knowledge_query(request)
        previous_agent = str(request.options.get("previous_agent", ""))
        previous_query = (
            str(request.options.get("previous_external_query", ""))
            .split("\nFollow-up requirement:", 1)[0]
            .strip()
        )
        if previous_query and is_academic_search_follow_up(
            current,
            previous_agent=previous_agent,
            previous_answer_summary=str(
                request.options.get("previous_answer_summary", "")
            ),
            previous_query=previous_query,
        ):
            return f"{previous_query}\nFollow-up requirement: {current}"
        return current
