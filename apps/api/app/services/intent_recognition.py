from __future__ import annotations

import re
from collections.abc import Iterable

from app.contracts import AgentRequest, Intent
from app.contracts.intent import IntentRecognition
from app.services.external_research_answer import (
    is_academic_search_follow_up,
    is_academic_writing_source_follow_up,
)


class IntentRecognitionService:
    """Fast, local-first recognition with a provider-independent contract."""

    # A single boundary vocabulary is shared by the Supervisor and the legacy
    # router.  Keeping it here prevents one entry point from inheriting a stale
    # course merely because the UI kept the previous course hint.
    _cross_domain_topic_markers = (
        "\u4eba\u5de5\u667a\u80fd",
        "\u673a\u5668\u5b66\u4e60",
        "\u6df1\u5ea6\u5b66\u4e60",
        "\u751f\u6210\u5f0f\u4eba\u5de5\u667a\u80fd",
        "\u5927\u6a21\u578b",
        "transformer",
        "self-attention",
        "attention mechanism",
        "natural language processing",
        "computer vision",
        "large language model",
        "\u795e\u7ecf\u7f51\u7edc",
        "\u4e09\u6b21\u63e1\u624b",
        "\u7f51\u7edc\u534f\u8bae",
        "\u8ba1\u7b97\u673a\u7f51\u7edc",
        "tcp/ip",
        "syn+ack",
        "tcp",
        "http",
        "https",
        "dns",
        "websocket",
        "\u64cd\u4f5c\u7cfb\u7edf",
        "\u6570\u636e\u5e93",
        "sql",
        "linux",
        "python",
        "javascript",
    )
    _cross_domain_topic_patterns = (
        r"\bai\b",
        r"\bml\b",
        r"\bnlp\b",
        r"\bllm\b",
    )

    @classmethod
    def is_cross_domain_topic(cls, text: str) -> bool:
        """Return whether text is clearly outside the course catalog."""

        normalized = text.casefold()
        if any(
            marker.casefold() in normalized
            for marker in cls._cross_domain_topic_markers
        ):
            return True
        return any(
            re.search(pattern, text, flags=re.IGNORECASE)
            for pattern in cls._cross_domain_topic_patterns
        )

    # Use Unicode escapes for Chinese markers.  This keeps the route contract
    # stable when a Windows editor or shell changes the source-file encoding.
    _research_patterns = (
        r"(?:\u8fd1|\u8fc7\u53bb|\u6700\u8fd1)\s*(?:\d+|[\u4e00-\u9fa5]+)\s*\u5e74",
        r"\u524d\u6cbf|\u8fdb\u5c55|\u7814\u7a76\u73b0\u72b6|\u8d8b\u52bf|\u7efc\u8ff0|\u6587\u732e|\u8bba\u6587|\u5b66\u672f|\u68c0\u7d22|\u8bc1\u636e",
        r"research|paper|literature|state[- ]of[- ]the[- ]art|recent progress",
    )
    _research_recency_patterns = (
        r"(?:\u8fd1|\u8fc7\u53bb|\u6700\u8fd1)\s*(?:\d+|[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u4e24]+)\s*\u5e74",
        r"\u8fd1\u5e74\u6765|\u8fd1\u671f|\u6700\u65b0|recent|latest|last\s+(?:few|several)\s+years",
    )
    _research_topic_patterns = (
        r"\u67d4\u6027\u7535\u5b50|\u67d4\u6027\u5668\u4ef6|\u795e\u7ecf\u5f62\u6001|\u7535\u5b50\u76ae\u80a4|\u53ef\u7a7f\u6234|\u4f20\u611f\u5668|"
        r"flexible electronics?|neuromorphic|electronic skin|wearable|sensor",
    )
    _research_action_patterns = (
        r"\u5173\u952e\u8fdb\u5c55|\u6280\u672f\u65b9\u5411|\u53d1\u5c55\u8d8b\u52bf|\u7814\u7a76\u73b0\u72b6|\u503c\u5f97\u5173\u6ce8|\u5b66\u672f\u524d\u6cbf|\u7814\u7a76\u6210\u679c|\u7efc\u8ff0|\u7814\u7a76|"
        r"state[- ]of[- ]the[- ]art|recent progress|research trend",
    )
    _writing_patterns = (
        r"\u5199\u8bba\u6587|\u8bba\u6587\u5199\u4f5c|\u6da6\u8272|\u6539\u5199|\u6295\u7a3f|\u5f15\u7528\u68c0\u67e5|\u5b66\u672f\u8868\u8fbe",
        r"\u5199.{0,8}(?:\u8bba\u6587|\u6458\u8981|\u7efc\u8ff0|\u62a5\u544a)",
        r"(?:\u8bba\u6587|\u6458\u8981|\u7efc\u8ff0|\u62a5\u544a).{0,8}(?:\u5199\u4f5c|\u64b0\u5199|\u6539\u5199|\u6da6\u8272)",
        r"\u6765\u6e90\u4ec5\u9650|\u4ec5\u9650(?:\u4e0b\u9762|\u4ee5\u4e0b)(?:\u6587\u5b57|\u5185\u5bb9)",
    )
    _data_patterns = (
        r"\u6570\u636e|csv|excel|\u56de\u5f52|\u7edf\u8ba1|\u53ef\u89c6\u5316|\u76f8\u5173\u6027|\u663e\u8457\u6027|\u6837\u672c|AUC|p\u503c|\u7f3a\u5931\u503c|\u7f6e\u4fe1\u533a\u95f4|\u53d8\u91cf",
    )
    _negated_data_patterns = (
        r"(?:\u6ca1\u6709|\u672a|\u5c1a\u672a|\u6682\u65e0|\u5c1a\u65e0)"
        r"(?:\u63d0\u4f9b|\u7ed9\u51fa)?(?:.{0,4})?"
        r"(?:\u5b9e\u9a8c)?\u6570\u636e",
    )
    _teaching_patterns = (
        r"\u5907\u8bfe|\u6559\u6848|\u6559\u5b66\u8bbe\u8ba1|\u8bfe\u5802|\u6388\u8bfe|\u6559\u5b66\u76ee\u6807",
    )
    _assignment_patterns = (
        r"\u4f5c\u4e1a|\u6279\u6539|\u8bc4\u5206|\u5b66\u751f\u7b54\u6848|\u8bc4\u8bed|\u5224\u5206",
    )
    _solver_patterns = (
        r"\u6c42\u89e3|\u8ba1\u7b97|\u63a8\u5bfc|\u65b9\u7a0b|\u7535\u8def|\u7535\u963b|\u7535\u5bb9|\u7535\u611f|\u4f20\u9012\u51fd\u6570|\u62c9\u666e\u62c9\u65af|\u771f\u503c\u8868",
        r"solve|calculate|derive|circuit|equation|transfer function",
    )
    _concept_explanation_patterns = (
        r"\u89e3\u91ca|\u8bf4\u660e|\u662f\u4ec0\u4e48|\u4e3a\u4ec0\u4e48|\u5982\u4f55\u7406\u89e3|"
        r"\u4e3e\u4f8b|\u4f8b\u5b50|\u539f\u7406|\u6982\u5ff5|\u5b9a\u5f8b|\u5b9a\u7406|\u5173\u7cfb|\u533a\u522b|\u4f5c\u7528|\u4ecb\u7ecd",
    )
    _explicit_solver_action_patterns = (
        r"\u6c42\u89e3|\u8ba1\u7b97|\u63a8\u5bfc|\u5217\u65b9\u7a0b|\u6c42\u6570\u503c|\u5df2\u77e5|\u7ed9\u5b9a",
        r"solve|calculate|derive|compute|find the value|given",
    )
    _dynamic_circuit_patterns = (
        r"\u52a8\u6001\u7535\u8def|\u72b6\u6001\u53d8\u91cf|\u72b6\u6001\u65b9\u7a0b|\u5fae\u5206\u65b9\u7a0b",
        r"dynamic circuit|state variable|state equation|differential equation",
    )

    _capability_map = {
        "academic_search": (
            "academic_search",
            "evidence_review",
            "evidence_synthesis",
        ),
        "academic_writing": ("academic_writing", "citation_check"),
        "data_analysis": ("data_analysis", "structured_output"),
        "lesson_prep": ("lesson_design", "course_knowledge"),
        "assignment_review": ("answer_review", "course_knowledge"),
        "solve_problem": ("problem_solving", "deterministic_verification"),
        "explain_concept": ("course_knowledge", "grounded_answer"),
        "general_qa": ("general_answer",),
    }

    def recognize(self, request: AgentRequest) -> IntentRecognition:
        text = self._request_text(request)
        explicit = request.intent.value
        matched = self._match(text)
        continuity_intent = self._continuity_intent(request, text)
        intent = matched or continuity_intent or (
            explicit if explicit != Intent.UNKNOWN.value else "unknown"
        )
        if intent == "unknown":
            intent = "general_qa"

        capabilities = list(self._capability_map.get(intent, ("general_answer",)))
        needs_external = intent == "academic_search"
        needs_retrieval = needs_external or intent in {
            "explain_concept",
            "summarize_knowledge",
            "solve_problem",
            "lesson_prep",
            "assignment_review",
        }
        workflow = intent in {
            "academic_search",
            "academic_writing",
            "data_analysis",
        } or len(capabilities) >= 3
        confidence = self._confidence(text, intent, explicit, matched)
        return IntentRecognition(
            task_family=self._task_family(intent),
            intent=intent,
            capabilities=capabilities,
            selected_tools=(
                ["academic_search", "paper_reader"] if needs_external else []
            ),
            selected_skills=(
                ["academic-frontier"] if intent == "academic_search" else []
            ),
            complexity=(
                "complex" if workflow else "medium" if needs_retrieval else "simple"
            ),
            route_mode="workflow" if workflow else "single_agent",
            needs_retrieval=needs_retrieval,
            needs_external_retrieval=needs_external,
            needs_subagents=workflow,
            parallelizable=intent == "academic_search",
            confidence=confidence,
            reason_codes=list(
                dict.fromkeys(
                    [
                        *self._reason_codes(intent, explicit, matched, text),
                        *(["session_continuity"] if continuity_intent else []),
                    ]
                )
            ),
        )

    @classmethod
    def align_to_intent(
        cls, recognition: IntentRecognition, intent: str
    ) -> IntentRecognition:
        """Align metadata with the validated route target."""

        normalized = intent.strip() or "general_qa"
        capabilities = list(cls._capability_map.get(normalized, ("general_answer",)))
        needs_external = normalized == "academic_search"
        needs_retrieval = needs_external or normalized in {
            "explain_concept",
            "summarize_knowledge",
            "solve_problem",
            "lesson_prep",
            "assignment_review",
        }
        workflow = normalized in {
            "academic_search",
            "academic_writing",
            "data_analysis",
        }
        return recognition.model_copy(
            update={
                "task_family": cls._task_family(normalized),
                "intent": normalized,
                "capabilities": capabilities,
                "selected_tools": (
                    ["academic_search", "paper_reader"] if needs_external else []
                ),
                "selected_skills": (
                    ["academic-frontier"] if normalized == "academic_search" else []
                ),
                "complexity": (
                    "complex" if workflow else "medium" if needs_retrieval else "simple"
                ),
                "route_mode": "workflow" if workflow else "single_agent",
                "needs_retrieval": needs_retrieval,
                "needs_external_retrieval": needs_external,
                "needs_subagents": workflow,
                "parallelizable": normalized == "academic_search",
                "reason_codes": list(
                    dict.fromkeys(
                        [*recognition.reason_codes, "route_target_alignment"]
                    )
                ),
            }
        )

    def _continuity_intent(
        self, request: AgentRequest, text: str
    ) -> str | None:
        previous_agent = str(request.options.get("previous_agent", ""))
        previous_intent = str(request.options.get("previous_intent", ""))
        previous_summary = str(request.options.get("previous_answer_summary", ""))
        if not previous_agent and not previous_intent:
            return None
        if self._has(text, self._writing_patterns):
            return None
        if previous_agent == "RESEARCH_01_ACADEMIC_SEARCH_V1":
            if is_academic_writing_source_follow_up(
                text, previous_agent=previous_agent
            ):
                return None
            if is_academic_search_follow_up(
                text,
                previous_agent=previous_agent,
                previous_answer_summary=previous_summary,
                previous_query=str(
                    request.options.get("previous_external_query", "")
                ),
            ):
                return "academic_search"

        continuation_markers = (
            "\u521a\u624d",
            "\u4e0a\u9762",
            "\u4e4b\u524d",
            "\u4e0a\u4e00\u8f6e",
            "\u8fd9\u4e2a",
            "\u8fd9\u4e9b",
            "\u63a5\u7740",
            "\u7ee7\u7eed",
            "\u7136\u540e",
            "\u53e6\u5916",
            "\u8fd8\u6709",
            "\u8865\u5145",
            "\u989d\u5916",
            "\u66f4\u591a",
            "\u8fdb\u4e00\u6b65",
            "\u518d\u63d0\u4f9b",
            "only",
            "more",
            "continue",
            "previous",
        )
        if not self._has(text, continuation_markers):
            return None
        allowed = {
            "academic_search",
            "academic_writing",
            "data_analysis",
            "solve_problem",
            "explain_concept",
            "follow_up_question",
            "general_qa",
            "summarize_knowledge",
            "learning_advice",
            "check_simple_step",
        }
        return previous_intent if previous_intent in allowed else None

    @staticmethod
    def _request_text(request: AgentRequest) -> str:
        values: list[str] = []
        for key in (
            "text",
            "question",
            "query",
            "prompt",
            "problem",
            "writing_task",
            "analysis_goal",
            "data_description",
        ):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
        values.extend(item.filename for item in request.attachments)
        return "\n".join(values).strip()

    def _match(self, text: str) -> str | None:
        if self._has(text, self._dynamic_circuit_patterns) and self._has(
            text, self._solver_patterns
        ):
            return "solve_problem"
        if self._has(text, self._writing_patterns) and self._has(
            text, self._data_patterns
        ):
            # A staged "analyze first, then write" request is a data workflow
            # with a downstream writing step, not a pure writing request.
            # A negated data phrase is a boundary condition for writing, not
            # evidence that the user asked to analyze a dataset.
            if self._has(text, self._negated_data_patterns):
                return "academic_writing"
            return "data_analysis"
        # Conflicting workflow signals should not be forced into whichever
        # keyword group happens to be checked first.  Keep the request on the
        # clarification/general path so the next layer can ask for scope.
        if self._has(text, self._writing_patterns) and self._has(
            text, self._teaching_patterns
        ):
            return "general_qa"
        if self._has(text, self._writing_patterns):
            return "academic_writing"
        if self._has(text, self._data_patterns):
            return "data_analysis"
        if self._has(text, self._teaching_patterns):
            return "lesson_prep"
        if self._has(text, self._assignment_patterns):
            return "assignment_review"
        if self._research_match(text):
            return "academic_search"
        if self._has(text, self._concept_explanation_patterns) and not self._has(
            text, self._explicit_solver_action_patterns
        ):
            return "explain_concept"
        if self._has(text, self._solver_patterns):
            return "solve_problem"
        return None

    def _research_match(self, text: str) -> bool:
        if self._has(text, self._research_patterns):
            return True
        has_topic = self._has(text, self._research_topic_patterns)
        has_action = self._has(text, self._research_action_patterns)
        has_recency = self._has(text, self._research_recency_patterns)
        return has_topic and (has_action or has_recency)

    @staticmethod
    def _has(text: str, patterns: Iterable[str]) -> bool:
        return any(
            re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns
        )

    @staticmethod
    def _task_family(intent: str) -> str:
        if intent in {"academic_search", "academic_writing", "data_analysis"}:
            return "research"
        if intent in {"lesson_prep", "assignment_review"}:
            return "teaching"
        if intent == "solve_problem":
            return "solving"
        return "learning"

    @staticmethod
    def _confidence(
        text: str, intent: str, explicit: str, matched: str | None
    ) -> float:
        if matched is not None and text:
            return 0.94 if intent == "academic_search" else 0.88
        if explicit not in {Intent.UNKNOWN.value, Intent.GENERAL_QA.value}:
            return 0.90
        return 0.55 if text else 0.25

    @staticmethod
    def _reason_codes(
        intent: str, explicit: str, matched: str | None, text: str
    ) -> list[str]:
        reasons = [f"intent:{intent}"]
        if matched:
            reasons.append("keyword_signal")
        if explicit not in {Intent.UNKNOWN.value, Intent.GENERAL_QA.value}:
            reasons.append("explicit_intent")
        if text:
            reasons.append("request_text_present")
        return reasons
