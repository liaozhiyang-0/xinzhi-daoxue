from __future__ import annotations

from app.contracts import AgentRequest, AgentResult
from app.core.config import Settings
from app.models import SessionModel


class SessionContextService:
    """Small rule-based context; never calls a model or stores full history."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def apply(self, session: SessionModel, request: AgentRequest) -> AgentRequest:
        stored = dict(session.context_data or {})
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
        session.context_data = {
            "active_course": request.course_id.upper(),
            "previous_course": old_course,
            "previous_intent": request.intent.value,
            "previous_agent": result.agent_id,
            "previous_answer_summary": answer_summary,
            "previous_business_summary": business_summary,
            "conversation_summary": conversation,
            "last_evidence_ids": evidence_ids,
            "previous_evidence_ids": evidence_ids,
        }
        session.course_id = request.course_id.upper()

    @staticmethod
    def _question(request: AgentRequest) -> str:
        for key in ("text", "question", "problem", "query", "prompt"):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                return " ".join(value.split())
        return ""
