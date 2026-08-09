from __future__ import annotations

from app.contracts import AgentRequest, AgentResult
from app.core.config import Settings
from app.models import SessionModel


class SessionContextService:
    """Project durable session state into routing and execution context.

    This is the short-term continuity layer: it keeps the active task family,
    topic, prior agent and evidence pointers separate from long-term memories
    and from the rolling transcript summary.
    """

    CONTEXT_SCHEMA_VERSION = 2

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def apply(self, session: SessionModel, request: AgentRequest) -> AgentRequest:
        stored = dict(session.context_data or {})
        continuity = stored.get("continuity", {})
        if not isinstance(continuity, dict):
            continuity = {}
        previous_course = str(stored.get("active_course", "")).upper()
        requested_course = request.course_id.upper()
        effective_course = (
            previous_course
            if requested_course in {"", "AUTO", "UNKNOWN"} and previous_course
            else requested_course
        )
        switched = bool(
            previous_course and previous_course != effective_course
        )
        options = dict(request.options)
        options.update(
            {
                "active_course": effective_course,
                "previous_course": previous_course,
                "previous_intent": str(stored.get("previous_intent", "")),
                "previous_agent": str(stored.get("previous_agent", "")),
                "previous_task_id": str(
                    stored.get("previous_task_id", continuity.get("last_task_id", ""))
                ),
                "previous_task_family": str(
                    stored.get(
                        "previous_task_family",
                        continuity.get("last_task_family", ""),
                    )
                ),
                "previous_answer_summary": (
                    "" if switched else str(stored.get("previous_answer_summary", ""))
                ),
                "previous_business_summary": (
                    "" if switched else str(stored.get("previous_business_summary", ""))
                ),
                "conversation_summary": (
                    ""
                    if switched
                    else str(
                        options.get(
                            "conversation_summary",
                            stored.get("conversation_summary", ""),
                        )
                    )
                ),
                "last_evidence_ids": (
                    [] if switched else list(stored.get("last_evidence_ids", []))[:10]
                ),
                "previous_evidence_ids": (
                    []
                    if switched
                    else list(stored.get("previous_evidence_ids", []))[:10]
                ),
                "previous_external_query": (
                    "" if switched else str(stored.get("previous_external_query", ""))
                ),
                "previous_external_retrieval": (
                    dict(stored.get("previous_external_retrieval", {}))
                    if not switched
                    and isinstance(stored.get("previous_external_retrieval", {}), dict)
                    else {}
                ),
                "continuity_state": {
                    "schema_version": self.CONTEXT_SCHEMA_VERSION,
                    "active_topic": str(
                        continuity.get(
                            "active_topic", stored.get("previous_external_query", "")
                        )
                    ),
                    "last_agent_id": str(
                        continuity.get(
                            "last_agent_id", stored.get("previous_agent", "")
                        )
                    ),
                    "last_intent": str(
                        continuity.get("last_intent", stored.get("previous_intent", ""))
                    ),
                    "last_task_family": str(
                        continuity.get("last_task_family", "")
                    ),
                    "evidence_ids": list(
                        stored.get(
                            "last_evidence_ids", continuity.get("evidence_ids", [])
                        )
                    )[:10],
                },
                "course_context_reset": switched,
            }
        )
        return request.model_copy(update={"options": options})

    def update(
        self,
        session: SessionModel,
        request: AgentRequest,
        result: AgentResult,
    ) -> None:
        old = dict(session.context_data or {})
        old_course = str(old.get("active_course", "")).upper()
        switched = bool(old_course and old_course != request.course_id.upper())
        question = self._question(request)
        answer_summary = " ".join(result.answer.split())[
            : self.settings.student_previous_answer_chars
        ]
        memory_intent = self._routing_value(request, "intent") or request.intent.value
        memory_task_family = (
            self._routing_value(request, "task_family")
            or str(request.options.get("task_family", ""))
            or request.intent.value
        )
        previous_summary = "" if switched else str(old.get("conversation_summary", ""))
        turn = f"问：{question[:240]} 答：{answer_summary}"
        conversation = " ".join(part for part in (previous_summary, turn) if part)[
            -self.settings.student_conversation_summary_chars :
        ]
        evidence_ids = [
            str(item.get("evidence_id", ""))
            for item in result.structured_result.get("knowledge", {}).get("hits", [])
            if isinstance(item, dict) and item.get("evidence_id")
        ][:10]
        business_summary = " ".join(
            str(value)
            for value in result.business_data.values()
            if isinstance(value, (str, int, float))
        )[: self.settings.student_previous_answer_chars]
        external_payload = result.structured_result.get("external_retrieval")
        previous_external_query = ""
        previous_external_retrieval: dict[str, object] = {}
        if isinstance(external_payload, dict):
            previous_external_query = str(external_payload.get("query", ""))
            previous_external_retrieval = dict(external_payload)
            raw_items = external_payload.get("items", [])
            if isinstance(raw_items, list):
                compact_items: list[dict[str, object]] = []
                for item in raw_items[:8]:
                    if not isinstance(item, dict):
                        continue
                    compact = dict(item)
                    excerpt = compact.get("content_excerpt")
                    if isinstance(excerpt, str):
                        compact["content_excerpt"] = excerpt[:3000]
                    compact_items.append(compact)
                previous_external_retrieval["items"] = compact_items
        session.context_data = {
            "context_schema_version": self.CONTEXT_SCHEMA_VERSION,
            "active_course": request.course_id.upper(),
            "previous_course": old_course,
            "previous_task_id": request.task_id,
            "previous_task_family": memory_task_family,
            "previous_intent": memory_intent,
            "previous_agent": result.agent_id,
            "previous_answer_summary": answer_summary,
            "previous_business_summary": business_summary,
            "conversation_summary": conversation,
            "last_evidence_ids": evidence_ids,
            "previous_evidence_ids": evidence_ids,
            "previous_external_query": previous_external_query,
            "previous_external_retrieval": previous_external_retrieval,
            "continuity": {
                "schema_version": self.CONTEXT_SCHEMA_VERSION,
                "last_task_id": request.task_id,
                "last_agent_id": result.agent_id,
                "last_intent": memory_intent,
                "last_task_family": memory_task_family,
                "active_topic": previous_external_query or question,
                "evidence_ids": evidence_ids,
            },
        }
        session.course_id = request.course_id.upper()

    @staticmethod
    def _question(request: AgentRequest) -> str:
        for key in ("text", "question", "problem", "query", "prompt"):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                return " ".join(value.split())
        return ""

    @staticmethod
    def _routing_value(request: AgentRequest, key: str) -> str:
        routing = request.options.get("_routing", {})
        if not isinstance(routing, dict):
            return ""
        recognition = routing.get("intent_recognition", {})
        if isinstance(recognition, dict):
            value = recognition.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        value = routing.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else ""
