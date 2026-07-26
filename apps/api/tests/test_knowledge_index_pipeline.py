from __future__ import annotations

import json
import struct
from pathlib import Path

from app.contracts import AgentRequest, KnowledgeHit, RetrievalResult
from app.core.config import Settings
from app.services.knowledge_audit import KnowledgeAuditScanner, checksum_file
from app.services.knowledge_base import KnowledgeBaseService
from app.services.knowledge_index import KnowledgeIndexBuilder, semantic_chunks
from app.services.retrieval_context import RetrievalContextService
from app.services.task_runner import TaskRunner


def roots(tmp_path: Path) -> dict[str, Path]:
    values = {
        course: tmp_path / course
        for course in ("CT", "AE", "DE", "SS", "DSP", "COMM")
    }
    for root in values.values():
        root.mkdir()
    return values


def png(width: int = 16, height: int = 8) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", width, height)


def scanner(values: dict[str, Path]) -> KnowledgeAuditScanner:
    return KnowledgeAuditScanner(values, max_parse_bytes=1024 * 1024)


def builder(values: dict[str, Path], output: Path) -> KnowledgeIndexBuilder:
    return KnowledgeIndexBuilder(
        roots=values,
        output_root=output,
        max_parse_bytes=1024 * 1024,
        chunk_size=300,
        overlap_chars=30,
    )


def test_scanner_finds_courses_text_images_and_does_not_modify_sources(
    tmp_path: Path,
) -> None:
    values = roots(tmp_path)
    document = values["CT"] / "第一章.md"
    document.write_text(
        "# 第一章\n\n![电路图](images/circuit.png)\n\n电路分析方法。",
        encoding="utf-8",
    )
    image = values["CT"] / "images" / "circuit.png"
    image.parent.mkdir()
    image.write_bytes(png())
    before = {path: checksum_file(path) for path in (document, image)}

    result = scanner(values).scan()

    assert [item.course_id for item in result.courses] == [
        "CT",
        "AE",
        "DE",
        "SS",
        "DSP",
        "COMM",
    ]
    assert len(result.manifest) == 2
    assert len(result.images) == 1
    assert result.images[0].parent_document_id is not None
    assert {path: checksum_file(path) for path in before} == before


def test_scanner_reports_broken_orphan_empty_and_mojibake_files(
    tmp_path: Path,
) -> None:
    values = roots(tmp_path)
    (values["AE"] / "broken.md").write_text(
        "# 放大电路\n![缺失](images/missing.jpg)\n锟斤拷",
        encoding="utf-8",
    )
    (values["AE"] / "empty.md").write_bytes(b"")
    orphan = values["AE"] / "images" / "orphan.png"
    orphan.parent.mkdir()
    orphan.write_bytes(png())

    result = scanner(values).scan(["AE"])
    issue_types = {item.issue_type for item in result.issues}

    assert {"broken_image_link", "orphan_image", "empty_file"} <= issue_types
    assert "possible_mojibake" in issue_types


def test_manifest_id_is_stable_and_checksum_changes(tmp_path: Path) -> None:
    values = roots(tmp_path)
    path = values["DE"] / "第一章.md"
    path.write_text("# 第一章\n逻辑代数基础。", encoding="utf-8")
    first = scanner(values).scan(["DE"]).manifest[0]

    path.write_text("# 第一章\n逻辑代数与卡诺图。", encoding="utf-8")
    second = scanner(values).scan(["DE"]).manifest[0]

    assert first.document_id == second.document_id
    assert first.checksum != second.checksum
    assert not Path(second.source_path).is_absolute()


def test_incremental_builder_reuses_unchanged_chunks(tmp_path: Path) -> None:
    values = roots(tmp_path)
    (values["CT"] / "第一章.md").write_text(
        "# 第一章\n\n## 结点法\n\n根据 KCL 列写结点方程。",
        encoding="utf-8",
    )
    index_builder = builder(values, tmp_path / "indexes")

    _, first = index_builder.build(["CT"], incremental=True)
    _, second = index_builder.build(["CT"], incremental=True)

    assert first.rebuilt_document_count == 1
    assert first.chunk_count > 0
    assert second.rebuilt_document_count == 0
    assert second.reused_chunk_count == first.chunk_count


def test_course_scoped_build_preserves_other_course_outputs(tmp_path: Path) -> None:
    values = roots(tmp_path)
    (values["CT"] / "chapter.md").write_text(
        "# Circuit\n\nKirchhoff current law.", encoding="utf-8"
    )
    (values["AE"] / "chapter.md").write_text(
        "# Amplifier\n\nNegative feedback stabilizes gain.", encoding="utf-8"
    )
    index_builder = builder(values, tmp_path / "indexes")
    index_builder.build(incremental=False)
    before = [
        json.loads(line)
        for line in index_builder.chunk_cache_path.read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    ae_before = [item for item in before if item["course_id"] == "AE"]

    (values["CT"] / "chapter.md").write_text(
        "# Circuit\n\nKirchhoff current law and voltage law.", encoding="utf-8"
    )
    audit, result = index_builder.build(["CT"], incremental=True)
    after = [
        json.loads(line)
        for line in index_builder.chunk_cache_path.read_text(
            encoding="utf-8"
        ).splitlines()
    ]

    assert {item.course_id for item in audit.manifest} == {"CT", "AE"}
    assert result.rebuilt_document_count == 1
    assert [item for item in after if item["course_id"] == "AE"] == ae_before


def test_scanner_reports_near_duplicate_documents(tmp_path: Path) -> None:
    values = roots(tmp_path)
    paragraph = (
        "This intentionally long paragraph describes the same reusable electronics "
        "concept with enough characters for near duplicate detection in the audit."
    )
    (values["CT"] / "first.md").write_text(
        f"# First\n\n{paragraph}\n\nUnique A", encoding="utf-8"
    )
    (values["CT"] / "second.md").write_text(
        f"# Second\n\n{paragraph}\n\nUnique B", encoding="utf-8"
    )

    result = scanner(values).scan(["CT"])

    assert any(item.issue_type == "near_duplicate_document" for item in result.issues)


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    values = roots(tmp_path)
    (values["CT"] / "第一章.md").write_text("# 概念\n内容。", encoding="utf-8")
    output = tmp_path / "indexes"

    _, result = builder(values, output).build(["CT"], dry_run=True)

    assert result.dry_run is True
    assert not output.exists()


def test_semantic_chunks_keep_heading_formula_and_image_context(
    tmp_path: Path,
) -> None:
    values = roots(tmp_path)
    document = values["CT"] / "第二章.md"
    text = (
        "# 第二章\n\n## 欧姆定律\n\n公式 $U=RI$ 与其解释保持在同一段。\n\n"
        "![电阻电路](images/r.png)\n\n图示为电阻连接。"
    )
    document.write_text(text, encoding="utf-8")
    image = values["CT"] / "images" / "r.png"
    image.parent.mkdir()
    image.write_bytes(png())
    audit = scanner(values).scan(["CT"])
    entry = next(item for item in audit.manifest if item.source_type == "markdown")

    chunks = semantic_chunks(
        entry=entry,
        text=text,
        chunk_size=300,
        overlap_chars=20,
        images=audit.images,
    )

    formula_chunk = next(item for item in chunks if "U=RI" in item.text)
    assert formula_chunk.title == "欧姆定律"
    assert "解释" in formula_chunk.text
    assert formula_chunk.related_images == ("kb-image://CT/images/r.png",)


def test_semantic_chunks_enforce_hard_limit_for_long_sentence_and_overlap(
    tmp_path: Path,
) -> None:
    values = roots(tmp_path)
    document = values["CT"] / "long.md"
    text = "# Long\n\n" + ("continuous_formula_token " * 80)
    document.write_text(text, encoding="utf-8")
    audit = scanner(values).scan(["CT"])
    entry = next(item for item in audit.manifest if item.source_type == "markdown")

    chunks = semantic_chunks(
        entry=entry,
        text=text,
        chunk_size=300,
        overlap_chars=80,
        images=(),
    )

    assert len(chunks) > 1
    assert max(len(item.text) for item in chunks) <= 300


def test_build_assigns_image_to_parent_chunk(tmp_path: Path) -> None:
    values = roots(tmp_path)
    document = values["CT"] / "chapter.md"
    document.write_text(
        "# Circuit\n\n![resistor](images/r.png)\n\nResistor circuit context.",
        encoding="utf-8",
    )
    image = values["CT"] / "images" / "r.png"
    image.parent.mkdir()
    image.write_bytes(png())

    audit, _ = builder(values, tmp_path / "indexes").build(incremental=False)

    assert audit.images[0].parent_document_id is not None
    assert audit.images[0].parent_chunk_id is not None


def test_runtime_retrieval_is_course_scoped_and_returns_related_image(
    tmp_path: Path,
) -> None:
    values = roots(tmp_path)
    (values["CT"] / "第一章.md").write_text(
        "# 电容电压\n\n![波形](images/wave.png)\n\n电容电压不能突变。",
        encoding="utf-8",
    )
    image = values["CT"] / "images" / "wave.png"
    image.parent.mkdir()
    image.write_bytes(png())
    (values["AE"] / "第一章.md").write_text("# 放大器\n负反馈。", encoding="utf-8")
    settings = Settings(
        app_env="test",
        knowledge_ct_path=values["CT"],
        knowledge_ae_path=values["AE"],
        knowledge_de_path=values["DE"],
        knowledge_ss_path=values["SS"],
        knowledge_dsp_path=values["DSP"],
        knowledge_comm_path=values["COMM"],
        knowledge_chunk_size_chars=300,
        _env_file=None,
    )
    service = KnowledgeBaseService(settings)

    result = service.search_result("为什么电容电压不能突变", ["CT"], 3)

    assert result.retrieval_mode == "sparse_bm25_v1"
    assert result.hits
    assert all(hit.course_id == "CT" for hit in result.hits)
    assert result.hits[0].related_images[0].resource_uri.startswith("kb-image://CT/")
    assert not service.search("电容电压不能突变", ["AE"], 3)


def test_retrieval_matrix_covers_course_concepts_methods_formulas_and_timing(
    tmp_path: Path,
) -> None:
    values = roots(tmp_path)
    documents = {
        "CT": {
            "concept.md": "# 戴维南定理\n\n戴维南定理用于线性含源一端口网络等效。",
            "method.md": "# 结点电压法 方法\n\n结点电压法先选参考结点再列写方程。",
        },
        "AE": {
            "concept.md": "# 负反馈概念\n\n负反馈可以稳定放大倍数并改善性能。",
            "formula.md": "# 电压增益公式\n\n电压增益公式为 $A_v=U_o/U_i$。",
            "unrelated.md": (
                "# 二极管\n\n![特性曲线](images/diode.png)\n二极管伏安特性。"
            ),
        },
        "DE": {
            "concept.md": "# 卡诺图概念\n\n卡诺图用于逻辑函数化简。",
            "timing.md": "# D触发器时序\n\nD触发器具有建立时间和保持时间。",
        },
    }
    for course, entries in documents.items():
        for relative, content in entries.items():
            path = values[course] / relative
            path.write_text(content, encoding="utf-8")
    image = values["AE"] / "images" / "diode.png"
    image.parent.mkdir()
    image.write_bytes(png())
    settings = Settings(
        app_env="test",
        knowledge_ct_path=values["CT"],
        knowledge_ae_path=values["AE"],
        knowledge_de_path=values["DE"],
        knowledge_ss_path=values["SS"],
        knowledge_dsp_path=values["DSP"],
        knowledge_comm_path=values["COMM"],
        knowledge_chunk_size_chars=300,
        _env_file=None,
    )
    service = KnowledgeBaseService(settings)

    cases = (
        ("CT", "戴维南定理", "戴维南"),
        ("CT", "结点电压法步骤", "结点电压法"),
        ("AE", "负反馈概念", "负反馈"),
        ("AE", "电压增益公式 Av", "电压增益公式"),
        ("DE", "卡诺图概念", "卡诺图"),
        ("DE", "D触发器建立时间", "D触发器时序"),
    )
    for course_id, query, expected_title in cases:
        result = service.search_result(query, [course_id], 3)
        assert result.hits
        assert expected_title in result.hits[0].title
        assert all(hit.course_id == course_id for hit in result.hits)
        assert all(
            hit.source_ref.startswith(f"kb://{course_id}/") for hit in result.hits
        )

    formula = service.search_result("电压增益公式 Av", ["AE"], 3)
    assert not formula.hits[0].related_images
    noise = service.search_result("!!!", ["CT"], 3)
    assert not noise.hits
    assert noise.confidence is None


def test_context_packet_numbers_evidence_and_formats_images(tmp_path: Path) -> None:
    values = roots(tmp_path)
    (values["DE"] / "第五章.md").write_text(
        "# D 触发器\nD 触发器保存一位状态。", encoding="utf-8"
    )
    settings = Settings(
        app_env="test",
        knowledge_ct_path=values["CT"],
        knowledge_ae_path=values["AE"],
        knowledge_de_path=values["DE"],
        knowledge_ss_path=values["SS"],
        knowledge_dsp_path=values["DSP"],
        knowledge_comm_path=values["COMM"],
        knowledge_chunk_size_chars=300,
        _env_file=None,
    )
    result: RetrievalResult = KnowledgeBaseService(settings).search_result(
        "D触发器", ["DE"], 3
    )
    packet = RetrievalContextService(1000).build(
        result, course_id="DE", intent="explain_concept"
    )

    assert packet.evidence[0].evidence_id == "S1"
    formatted = packet.to_retrieved_context()
    assert "[S1]" in formatted
    assert "kb://DE/" in formatted
    assert str(tmp_path) not in formatted


def test_learning_context_adapter_keeps_packet_and_warnings() -> None:
    empty = RetrievalResult(
        query="未知问题",
        normalized_query="未知问题",
        course_ids=["CT"],
        hits=[],
        confidence=None,
        warnings=["无结果"],
        latency_ms=0,
    )
    packet = RetrievalContextService(1000).build(
        empty, course_id="CT", intent="general_qa"
    )
    request = json.loads(
        '{"session_id":"s","user_id":"u","course_id":"CT",'
        '"intent":"general_qa","canonical_input":{"text":"问题"}}'
    )

    augmented = TaskRunner._with_learning_context(
        AgentRequest.model_validate(request), packet
    )

    assert augmented.canonical_input["text"] == "问题"
    assert "evidence_status: insufficient" in augmented.options["retrieved_context"]
    assert augmented.options["retrieval_context_packet"]["warnings"]


def test_context_packet_statuses_conflicts_and_cross_course_filtering() -> None:
    def hit(chunk_id: str, course_id: str, content: str) -> KnowledgeHit:
        return KnowledgeHit(
            chunk_id=chunk_id,
            document_id=f"DOC_{chunk_id}",
            course_id=course_id,
            course_name={"CT": "电路理论", "AE": "模拟电子技术"}[course_id],
            chapter="第一章",
            document_path=f"{chunk_id}.md",
            title="同一概念的不同来源",
            content_type="concept",
            content=content,
            score=10,
            source_ref=f"kb://{course_id}/{chunk_id}.md#chunk-1",
        )

    conflicting = RetrievalResult(
        query="测试概念",
        normalized_query="测试概念",
        course_ids=["CT"],
        hits=[
            hit("one", "CT", "来源一给出结论甲。"),
            hit("two", "CT", "来源二给出不同结论乙。"),
        ],
        confidence=0.8,
        latency_ms=0,
    )
    sufficient = RetrievalContextService(1000).build(
        conflicting, course_id="CT", intent="general_qa"
    )
    assert sufficient.evidence_status == "sufficient"
    assert [item.evidence_id for item in sufficient.evidence] == ["S1", "S2"]

    partial = RetrievalContextService(1000).build(
        conflicting.model_copy(
            update={"hits": conflicting.hits[:1], "confidence": 0.5}
        ),
        course_id="CT",
        intent="general_qa",
    )
    assert partial.evidence_status == "partial"

    cross_course = RetrievalContextService(1000).build(
        conflicting.model_copy(
            update={"hits": [hit("wrong", "AE", "跨课程内容。")], "confidence": 0.8}
        ),
        course_id="CT",
        intent="general_qa",
    )
    assert cross_course.evidence_status == "insufficient"
    assert not cross_course.evidence
    assert any("跨课程" in warning for warning in cross_course.warnings)
