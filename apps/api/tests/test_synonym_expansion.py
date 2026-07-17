from pathlib import Path

from tests.knowledge_test_utils import make_service


def test_course_synonym_expansion_is_visible(tmp_path: Path) -> None:
    service = make_service(tmp_path, {})

    expanded = service.expand_query("thevenin 等效", ["CT"])

    assert "戴维南" in expanded
    assert "戴维宁" in expanded
