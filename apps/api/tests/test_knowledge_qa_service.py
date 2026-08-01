from pathlib import Path

from app.contracts import AgentRequest
from app.services.knowledge_qa_service import DISCLAIMER, KnowledgeQAService
from app.services.retrieval_context import RetrievalContextService

from tests.knowledge_test_utils import make_service


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
