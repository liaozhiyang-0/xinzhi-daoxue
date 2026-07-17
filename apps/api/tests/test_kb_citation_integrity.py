from pathlib import Path, PurePosixPath

from tests.knowledge_test_utils import make_service


def test_hit_citation_checksum_and_relative_path_are_integral(tmp_path: Path) -> None:
    service = make_service(
        tmp_path, {"CT": {"教材/第四章.md": "# 戴维南定理\n线性网络等效方法。"}}
    )

    hit = service.search_result("戴维南定理", ["CT"], 1).hits[0]

    assert hit.source_ref.startswith("kb://CT/教材/第四章.md#chunk-")
    assert len(hit.document_checksum) == 64
    assert not PurePosixPath(hit.document_path).is_absolute()
    assert ".." not in PurePosixPath(hit.document_path).parts
