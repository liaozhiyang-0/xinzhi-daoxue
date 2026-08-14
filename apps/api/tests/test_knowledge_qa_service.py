from pathlib import Path
from typing import Any

from app.contracts import AgentRequest, RetrievalResult
from app.services.knowledge_qa_service import DISCLAIMER, KnowledgeQAService
from app.services.retrieval_context import RetrievalContextService

from tests.knowledge_test_utils import make_service


class _UnexpectedModelService:
    async def generate_for_task(self, *_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("cloud/model generation must not run")


class _RecordingContextService(RetrievalContextService):
    def __init__(self) -> None:
        super().__init__(2000)
        self.last_query_override: str | None = None

    def build(self, result: RetrievalResult, **kwargs: object):  # type: ignore[no-untyped-def]
        value = kwargs.get("query_override")
        self.last_query_override = value if isinstance(value, str) else None
        return super().build(result, **kwargs)  # type: ignore[arg-type]


async def test_knowledge_qa_skips_generation_when_cloud_is_disabled(
    tmp_path: Path,
) -> None:
    kb = make_service(
        tmp_path,
        {"CT": {"chapter.md": "# Capacitor\nCapacitor voltage is continuous."}},
    )
    service = KnowledgeQAService(
        kb,
        RetrievalContextService(2000),
        model_service=_UnexpectedModelService(),  # type: ignore[arg-type]
    )
    request = AgentRequest(
        session_id="s1",
        user_id="u1",
        scene="learning",
        course_id="CT",
        intent="general_qa",
        canonical_input={"question": "What is capacitor voltage continuity?"},
        options={"allow_cloud": False},
    )

    execution = await service.run_with_generation(
        "LEARN_01_LOCAL_RETRIEVAL_V1", request
    )

    assert execution.result.provider == "local"
    assert execution.result.structured_result["mode"] == "retrieval_only"


def test_local_knowledge_qa_is_explicitly_retrieval_only(tmp_path: Path) -> None:
    kb = make_service(
        tmp_path, {"CT": {"chapter.md": "# 戴维南定理\n线性含源一端口网络可以等效。"}}
    )
    service = KnowledgeQAService(kb, RetrievalContextService(2000))
    request = AgentRequest(
        session_id="s1",
        user_id="u1",
        scene="learning",
        course_id="CT",
        intent="general_qa",
        canonical_input={"question": "什么是戴维南定理"},
    )

    execution = service.run("LEARN_01_LOCAL_RETRIEVAL_V1", request)

    assert execution.result.provider == "local"
    assert execution.result.structured_result["mode"] == "retrieval_only"
    assert DISCLAIMER in execution.result.warnings
    assert "本地资料依据" in execution.result.answer
    assert execution.result.citations[0].startswith("kb://CT/")


def test_knowledge_qa_falls_back_to_local_lexical_search_when_rag_fails(
    tmp_path: Path,
) -> None:
    kb = make_service(
        tmp_path,
        {
            "AE": {
                "chapter.md": (
                    "# Switching regulator\n"
                    "A switching regulator controls output voltage with a "
                    "high-frequency "
                    "switch and an inductor."
                )
            }
        },
    )

    class BrokenRag:
        def search(self, **_: object) -> object:
            raise RuntimeError("embedding service unavailable")

    request = AgentRequest(
        session_id="s1",
        user_id="u1",
        scene="learning",
        course_id="AE",
        intent="explain_concept",
        canonical_input={"question": "switching regulator"},
    )
    execution = KnowledgeQAService(
        kb,
        RetrievalContextService(2000),
        rag_retrieval=BrokenRag(),  # type: ignore[arg-type]
    ).run("LEARN_01_LOCAL_RETRIEVAL_V1", request)

    assert execution.retrieval.hits
    assert "local_lexical_fallback:RuntimeError" in execution.retrieval.warnings
    assert "本地资料依据" in execution.result.answer
    assert "[S1]" in execution.result.answer


def test_knowledge_qa_compatibility_path_preserves_user_query_for_filtering(
    tmp_path: Path,
) -> None:
    context_service = _RecordingContextService()
    service = KnowledgeQAService(
        make_service(tmp_path, {"CT": {"chapter.md": "课程资料"}}),
        context_service,
    )
    request = AgentRequest(
        session_id="s-compat-query",
        user_id="u-compat-query",
        scene="teaching",
        course_id="CT",
        intent="lesson_prep",
        canonical_input={
            "question": "请设计电容电压连续性的课堂教案，并给出课程资料依据。"
        },
    )
    retrieval = RetrievalResult(
        query="电路理论",
        normalized_query="电路理论",
        course_ids=["CT"],
        latency_ms=0,
    )

    service.from_retrieval("LEARN_01_LOCAL_RETRIEVAL_V1", request, retrieval)

    assert (
        context_service.last_query_override
        == "请设计电容电压连续性的课堂教案，并给出课程资料依据。"
    )
