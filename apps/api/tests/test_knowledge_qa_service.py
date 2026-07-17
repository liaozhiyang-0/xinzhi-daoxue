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

    execution = service.run("LEARN_01_KNOWLEDGE_QA_V1", request)

    assert execution.result.provider == "local"
    assert execution.result.structured_result["mode"] == "retrieval_only"
    assert DISCLAIMER in execution.result.answer
    assert execution.result.citations[0].startswith("kb://CT/")
