from __future__ import annotations

import pytest
from app.services.evidence_references import (
    analyze_evidence_references,
    classify_evidence_reference,
)


@pytest.mark.parametrize(
    ("value", "kind"),
    [
        ("teacher-notes/AE-review.md#1", "path"),
        ("kb://AE/materials/chunk-1", "uri"),
        ("course_material:AE/chapter-1", "typed"),
        ("teacher-review", "opaque"),
    ],
)
def test_classify_evidence_reference(value: str, kind: str) -> None:
    assert classify_evidence_reference(value) == kind


def test_analyze_evidence_references_distinguishes_missing_and_untraceable() -> None:
    assert analyze_evidence_references([])["status"] == "missing"
    summary = analyze_evidence_references(["teacher-review", "kb://AE/chunk-1"])
    assert summary["status"] == "untraceable"
    assert summary["reference_count"] == 2
    assert summary["untraceable_references"] == ["teacher-review"]


def test_analyze_evidence_references_accepts_path_and_typed_refs() -> None:
    summary = analyze_evidence_references(
        ["teacher-notes/AE-review.md#1", "course_material:AE/chapter-1"]
    )
    assert summary["status"] == "traceable"
    assert summary["reference_kinds"] == ["path", "typed"]
