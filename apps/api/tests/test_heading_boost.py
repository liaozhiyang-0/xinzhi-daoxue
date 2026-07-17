from pathlib import Path

from tests.knowledge_test_utils import make_service


def test_exact_heading_is_boosted(tmp_path: Path) -> None:
    service = make_service(
        tmp_path,
        {
            "CT": {
                "heading.md": "# 戴维南定理\n用于线性含源一端口网络的等效。",
                "body.md": "# 其他定理\n这里顺带提到戴维南定理，但不是本节标题。",
            }
        },
    )

    result = service.search_result("戴维南定理", ["CT"], 2)

    assert result.hits[0].document_path == "heading.md"
    assert result.hits[0].score_components["exact_phrase_boost"] == 3.0
