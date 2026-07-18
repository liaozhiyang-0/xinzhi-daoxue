from pathlib import Path

from app.contracts import AgentRequest
from app.services.knowledge_qa_service import KnowledgeQAService
from app.services.retrieval_context import RetrievalContextService

from tests.knowledge_test_utils import make_service


def test_explanation_artifact_contains_required_trace_fields(tmp_path: Path) -> None:
    kb = make_service(
        tmp_path, {"DE": {"chapter.md": "# 格雷码\n相邻代码只有一位不同。"}}
    )
    request = AgentRequest(
        session_id="s1",
        user_id="u1",
        scene="learning",
        course_id="DE",
        intent="explain_concept",
        canonical_input={"question": "格雷码的特点"},
    )

    artifact = (
        KnowledgeQAService(kb, RetrievalContextService(2000))
        .run("LEARN_01_LOCAL_RETRIEVAL_V1", request)
        .result.artifacts[0]
    )

    assert artifact.content["mode"] == "retrieval_only"
    assert artifact.content["question"] == "格雷码的特点"
    assert artifact.content["course_id"] == "DE"
    assert artifact.content["summary"]
    assert artifact.content["evidence_status"] in {
        "sufficient",
        "partial",
        "insufficient",
        "failed",
    }
    assert artifact.content["sources"] == artifact.source_refs
