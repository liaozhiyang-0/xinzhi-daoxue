from app.contracts import KnowledgeHit, RetrievalResult
from app.services.retrieval_context import RetrievalContextService


def hit(course_id: str, chunk_id: str, content: str) -> KnowledgeHit:
    return KnowledgeHit(
        chunk_id=chunk_id,
        course_id=course_id,
        course_name="测试课程",
        chapter="第一章",
        section="第一节",
        document_path="教材/第一章.md",
        title="第一节",
        content=content,
        score=8,
        source_ref=f"kb://{course_id}/教材/第一章.md#chunk-{chunk_id}",
    )


def test_context_packet_is_course_scoped_deduplicated_and_bounded() -> None:
    ct = hit("CT", "1", "甲" * 80)
    result = RetrievalResult(
        query="问题",
        normalized_query="问题",
        course_ids=["CT"],
        hits=[ct, ct.model_copy(), hit("AE", "2", "乙" * 80)],
        confidence=0.8,
        latency_ms=1,
    )

    packet = RetrievalContextService(50).build(
        result, course_id="CT", intent="general_qa"
    )

    assert len(packet.evidence) == 1
    assert len(packet.evidence[0].content) == 50
    assert all(ref.startswith("kb://CT/") for ref in packet.source_refs)


def test_context_packet_rejects_course_hits_without_topic_overlap() -> None:
    unrelated = hit(
        "CT", "unrelated", "电路理论的基本假设与基尔霍夫定律。"
    ).model_copy(update={"course_name": "电路理论"})
    result = RetrievalResult(
        query="请仅根据电路理论课程资料回答：火星殖民地超导电网第九章的量子引力推导。",
        normalized_query="火星殖民地超导电网第九章量子引力推导",
        course_ids=["CT"],
        hits=[unrelated],
        confidence=0.8,
        latency_ms=0,
    )

    packet = RetrievalContextService(1000).build(
        result, course_id="CT", intent="explain_concept"
    )

    assert packet.evidence_status == "insufficient"
    assert packet.evidence == []
    assert packet.source_refs == []
    assert any("主题不一致" in warning for warning in packet.warnings)


def test_context_packet_keeps_hits_with_a_topic_anchor() -> None:
    matching = hit("CT", "matching", "电容电压不能突变，需满足连续性条件。")
    result = RetrievalResult(
        query="为什么电容电压不能突变？",
        normalized_query="电容电压不能突变",
        course_ids=["CT"],
        hits=[matching],
        confidence=0.8,
        latency_ms=0,
    )

    packet = RetrievalContextService(1000).build(
        result, course_id="CT", intent="explain_concept"
    )

    assert packet.evidence_status == "partial"
    assert [item.chunk_id for item in packet.evidence] == ["matching"]


def test_context_packet_uses_explicit_question_for_topic_gate() -> None:
    matching = hit(
        "CT",
        "matching-explicit",
        "电容电压连续性与相关公式。",
    ).model_copy(update={"title": "电容电压连续性"})
    unrelated = hit("CT", "unrelated-explicit", "量子引力场的宇宙学推导。")
    result = RetrievalResult(
        query="电路理论",
        normalized_query="电路理论",
        course_ids=["CT"],
        hits=[matching, unrelated],
        confidence=0.8,
        latency_ms=0,
    )

    packet = RetrievalContextService(1000).build(
        result,
        course_id="CT",
        intent="lesson_prep",
        query_override="请解释电容电压连续性，并给出相关公式。",
    )

    assert [item.chunk_id for item in packet.evidence] == ["matching-explicit"]
    assert packet.query == "请解释电容电压连续性，并给出相关公式。"


def test_teaching_evidence_requires_topic_anchor_in_source_metadata() -> None:
    relevant = hit(
        "CT", "teaching-relevant", "电容电压连续性及其课堂解释。"
    ).model_copy(update={"title": "电容电压连续性"})
    incidental = hit(
        "CT", "teaching-incidental", "电路理论基本假设，正文顺带提到电压。"
    ).model_copy(update={"title": "电路理论的基本假设"})
    result = RetrievalResult(
        query="电路理论",
        normalized_query="电路理论",
        course_ids=["CT"],
        hits=[relevant, incidental],
        confidence=0.8,
        latency_ms=0,
    )

    packet = RetrievalContextService(1000).build(
        result,
        course_id="CT",
        intent="lesson_prep",
        query_override="请设计电容电压连续性的课堂教案。",
    )

    assert [item.chunk_id for item in packet.evidence] == ["teaching-relevant"]


def test_teaching_evidence_requires_multiple_topic_anchors_for_compound_query() -> None:
    relevant = hit(
        "CT", "teaching-compound", "电容电压连续性及其课堂讲解。"
    ).model_copy(update={"title": "电容电压连续性"})
    voltage_only = hit(
        "CT", "teaching-voltage-only", "电压源支路的列方程方法。"
    ).model_copy(update={"title": "对电压源支路的处理"})
    capacitor_only = hit(
        "CT", "teaching-capacitor-only", "电容的串联与并联。"
    ).model_copy(update={"title": "电容的串联与并联"})
    result = RetrievalResult(
        query="电路理论",
        normalized_query="电路理论",
        course_ids=["CT"],
        hits=[relevant, voltage_only, capacitor_only],
        confidence=0.8,
        latency_ms=0,
    )

    packet = RetrievalContextService(1000).build(
        result,
        course_id="CT",
        intent="lesson_prep",
        query_override="请为电容电压连续性设计一份45分钟课堂教案，包含目标、流程和形成性评价",
    )

    assert [item.chunk_id for item in packet.evidence] == ["teaching-compound"]


def test_topic_filter_ignores_chapter_numbers_and_generic_structure_words() -> None:
    unrelated = hit(
        "CT", "unrelated-numbered", "第九章介绍电路理论的基本假设与基尔霍夫定律。"
    ).model_copy(update={"course_name": "电路理论"})
    result = RetrievalResult(
        query="请仅根据电路理论课程资料回答：火星殖民地超导电网第九章的量子引力推导。",
        normalized_query="火星殖民地超导电网第九章量子引力推导",
        course_ids=["CT"],
        hits=[unrelated],
        confidence=0.8,
        latency_ms=0,
    )

    packet = RetrievalContextService(1000).build(
        result, course_id="CT", intent="explain_concept"
    )

    assert packet.evidence_status == "insufficient"
    assert packet.evidence == []


def test_teaching_evidence_requires_named_machine_topic_anchor() -> None:
    unrelated = hit(
        "CT", "asm", "算法状态机用于描述数字系统控制单元的工作流程。"
    ).model_copy(update={"title": "算法状态机"})
    matching = hit(
        "CT", "mealy-moore", "Mealy 与 Moore 状态机的输出定义和时序比较。"
    ).model_copy(update={"title": "Mealy/Moore 状态机"})
    result = RetrievalResult(
        query="数字电子技术",
        normalized_query="数字电子技术",
        course_ids=["CT"],
        hits=[unrelated, matching],
        confidence=0.8,
        latency_ms=0,
    )

    packet = RetrievalContextService(1000).build(
        result,
        course_id="CT",
        intent="lesson_prep",
        query_override="请设计 Mealy/Moore 状态机翻转课堂。",
    )

    assert [item.chunk_id for item in packet.evidence] == ["mealy-moore"]


def test_context_packet_blocks_static_point_evidence_without_bjt_anchor() -> None:
    mos = hit(
        "AE",
        "mos-static-point",
        "共源放大电路的静态工作点计算和动态指标分析。",
    ).model_copy(update={"course_name": "模拟电子技术"})
    result = RetrievalResult(
        query="根据BJT静态工作点设置和动态参数测试的实验失误制定复习计划",
        normalized_query="BJT静态工作点动态参数测试",
        course_ids=["AE"],
        hits=[mos],
        confidence=0.9,
        latency_ms=0,
    )

    packet = RetrievalContextService(1000).build(
        result, course_id="AE", intent="learning_advice"
    )

    assert packet.evidence_status == "insufficient"
    assert packet.evidence == []
    assert any("BJT/三极管" in warning for warning in packet.warnings)


def test_context_packet_blocks_generic_evidence_without_laplace_anchor() -> None:
    generic = hit(
        "CT",
        "generic-circuit",
        "电路课程强调从基础到拓展的逻辑主线与参数响应分析。",
    )
    result = RetrievalResult(
        query="拉普拉斯变换极点分布与时域响应稳定性复习路径",
        normalized_query="拉普拉斯 极点分布 时域响应 稳定性",
        course_ids=["CT"],
        hits=[generic],
        confidence=0.9,
        latency_ms=0,
    )

    packet = RetrievalContextService(1000).build(
        result, course_id="CT", intent="learning_advice"
    )

    assert packet.evidence_status == "insufficient"
    assert packet.evidence == []
    assert any("拉普拉斯/极点/稳定性" in warning for warning in packet.warnings)
