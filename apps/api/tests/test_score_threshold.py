from pathlib import Path

from tests.knowledge_test_utils import make_service


def test_minimum_score_returns_explicit_no_result_warning(tmp_path: Path) -> None:
    service = make_service(
        tmp_path,
        {"CT": {"a.md": "# 电阻\n欧姆定律描述电压与电流。"}},
        knowledge_min_score_v2=1_000_000.0,
    )

    result = service.search_result("电阻", ["CT"], 5)

    assert result.hits == []
    assert result.confidence is None
    assert any("最低分阈值" in warning for warning in result.warnings)
