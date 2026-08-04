from __future__ import annotations

import re
from typing import Any

EVIDENCE_REFERENCE_STATUSES = frozenset({"missing", "traceable", "untraceable"})
EVIDENCE_REFERENCE_KINDS = frozenset({"path", "uri", "typed", "opaque"})
URI_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
TYPED_REFERENCE_RE = re.compile(r"^[a-z][a-z0-9_.-]*:[^\s]+$", re.IGNORECASE)


def classify_evidence_reference(value: Any) -> str:
    """Classify a reference without asserting that its target currently exists."""
    reference = str(value or "").strip()
    if not reference:
        return "opaque"
    if URI_RE.match(reference):
        return "uri"
    if TYPED_REFERENCE_RE.match(reference):
        return "typed"
    if "/" in reference or "\\" in reference:
        return "path"
    return "opaque"


def analyze_evidence_references(values: list[Any] | tuple[Any, ...]) -> dict[str, Any]:
    """Return a bounded, deterministic quality summary for evidence references."""
    references = list(
        dict.fromkeys(str(value).strip() for value in values if str(value).strip())
    )
    kinds = [classify_evidence_reference(value) for value in references]
    status = (
        "missing"
        if not references
        else "traceable"
        if all(kind != "opaque" for kind in kinds)
        else "untraceable"
    )
    return {
        "status": status,
        "reference_count": len(references),
        "reference_kinds": sorted(set(kinds)),
        "untraceable_references": [
            reference
            for reference, kind in zip(references, kinds, strict=True)
            if kind == "opaque"
        ],
    }
