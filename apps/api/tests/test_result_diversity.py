from collections import Counter
from pathlib import Path

from tests.knowledge_test_utils import make_service


def test_single_document_cannot_fill_all_results(tmp_path: Path) -> None:
    repeated = "负反馈放大电路改善稳定性。" * 80
    service = make_service(
        tmp_path,
        {
            "AE": {
                "a.md": f"# 负反馈\n{repeated}",
                "b.md": "# 负反馈组态\n负反馈放大电路有四种组态。",
            }
        },
    )

    hits = service.search_result("负反馈放大电路", ["AE"], 5).hits
    counts = Counter(hit.document_path for hit in hits)

    assert counts["a.md"] <= 2
    assert "b.md" in counts
