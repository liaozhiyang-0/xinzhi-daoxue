from pathlib import Path

from tests.knowledge_test_utils import make_service


def test_overlapping_results_are_deduplicated(tmp_path: Path) -> None:
    repeated = "戴维南等效电路用于线性网络。" * 80
    service = make_service(tmp_path, {"CT": {"long.md": f"# 等效电路\n{repeated}"}})

    hits = service.search_result("戴维南等效电路", ["CT"], 5).hits

    assert len({hit.chunk_id for hit in hits}) == len(hits)
    assert len(hits) <= 2
