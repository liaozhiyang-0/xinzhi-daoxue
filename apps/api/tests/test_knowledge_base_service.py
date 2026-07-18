from pathlib import Path

from app.contracts import KnowledgeHit
from app.contracts.knowledge import KnowledgeCourseId
from app.core.config import Settings
from app.services.knowledge_base import KnowledgeBaseService


def write_library(root: Path, filename: str, content: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / filename
    path.write_text(content, encoding="utf-8")
    return path


def build_service(tmp_path: Path) -> KnowledgeBaseService:
    ct = tmp_path / "电路理论"
    ae = tmp_path / "模电"
    de = tmp_path / "数电"
    write_library(
        ct,
        "第一章.md",
        "## 戴维南定理\n线性含源二端网络可以等效为电压源与电阻串联。",
    )
    write_library(ae, "第四章.md", "## 负反馈\n负反馈能够稳定放大倍数。")
    write_library(de, "第五章.md", "## 触发器\nD 触发器用于保存一位状态。")
    return KnowledgeBaseService(
        Settings(
            app_env="test",
            knowledge_ct_path=ct,
            knowledge_ae_path=ae,
            knowledge_de_path=de,
            knowledge_chunk_size_chars=300,
            knowledge_chunk_overlap_chars=20,
        )
    )


def test_indexes_three_local_markdown_libraries(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    statuses = service.refresh()
    assert [status.course_id for status in statuses] == ["CT", "AE", "DE"]
    assert all(status.available for status in statuses)
    assert sum(status.document_count for status in statuses) == 3
    assert sum(status.chunk_count for status in statuses) == 3


def test_chinese_search_is_course_scoped_and_path_safe(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    hits = service.search("戴维南等效电路", ["CT"], 3)
    assert hits
    assert hits[0].course_id == "CT"
    assert hits[0].document_path == "第一章.md"
    assert hits[0].source_ref.startswith("kb://CT/")
    assert str(tmp_path) not in hits[0].source_ref
    assert not service.search("戴维南等效电路", ["AE"], 3)


def test_normalizes_node_terminology(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    ct_root = service.settings.knowledge_ct_path
    write_library(ct_root, "第三章.md", "## 结点电压法\n结点方程按 KCL 列写。")
    service.refresh()
    hits = service.search("节点电压法", ["CT"], 1)
    assert hits[0].title == "结点电压法"


def test_de_schmitt_hysteresis_expansion_and_boost_are_course_local(
    tmp_path: Path,
) -> None:
    service = build_service(tmp_path)
    service.refresh()

    expanded = service.expand_query("施密特触发器为什么具有回差特性", ["DE"])
    assert "施密特触发电路" in expanded
    assert "回差电压" in expanded
    de_concept = KnowledgeHit(
        course_id="DE",
        course_name="数字电子技术",
        title="工作原理",
        chapter="第九章",
        section="施密特触发电路",
        document_path="第九章.md",
        content_type="concept",
        content="电路中的正反馈形成两个不同的阈值。",
        score=1,
        source_ref="kb://DE/第九章.md#chunk-1",
    )
    de_unrelated = de_concept.model_copy(
        update={"content": "D 触发器用于保存一位状态。"}
    )
    ct_same_text = de_concept.model_copy(
        update={
            "course_id": KnowledgeCourseId.CIRCUIT_THEORY,
            "course_name": "电路理论",
            "source_ref": "kb://CT/第一章.md#chunk-1",
        }
    )

    assert (
        service.retrieval_topic_bonus("施密特触发器为什么具有回差特性？", de_concept)
        == 0.008
    )
    assert (
        service.retrieval_topic_bonus("施密特触发器为什么具有回差特性？", de_unrelated)
        == 0
    )
    assert (
        service.retrieval_topic_bonus("施密特触发器为什么具有回差特性？", ct_same_text)
        == 0
    )


def test_ct_series_resonance_boost_requires_matching_mechanism(
    tmp_path: Path,
) -> None:
    service = build_service(tmp_path)
    service.refresh()

    expanded = service.expand_query("串联谐振时电路有哪些特征", ["CT"])
    assert "电压谐振" in expanded
    resonance_concept = KnowledgeHit(
        course_id="CT",
        course_name="电路理论",
        title="RLC 支路的阻抗与导纳",
        chapter="第十章",
        section="RLC 支路的阻抗与导纳",
        document_path="第十章.md",
        content_type="concept",
        content="串联谐振时感抗和容抗互消，电路呈阻性，电压和电流同相。",
        score=1,
        source_ref="kb://CT/第十章.md#chunk-1",
    )
    unrelated = resonance_concept.model_copy(
        update={"content": "RLC 串联电路的方波响应与阻尼有关。"}
    )
    de_same_text = resonance_concept.model_copy(
        update={
            "course_id": KnowledgeCourseId.DIGITAL_ELECTRONICS,
            "course_name": "数字电子技术",
            "source_ref": "kb://DE/第九章.md#chunk-1",
        }
    )

    assert (
        service.retrieval_topic_bonus("串联谐振时电路有哪些特征？", resonance_concept)
        == 0.008
    )
    assert service.retrieval_topic_bonus("串联谐振时电路有哪些特征？", unrelated) == 0
    assert (
        service.retrieval_topic_bonus("串联谐振时电路有哪些特征？", de_same_text) == 0
    )
