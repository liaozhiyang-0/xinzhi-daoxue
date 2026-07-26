from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.multimodal.image_batch import ImageItemResult


def merge_multimodal_results(
    results: Sequence[ImageItemResult],
) -> dict[str, Any]:
    ordered = sorted(results, key=lambda item: item.image_index)
    conflicts = list(
        dict.fromkeys(conflict for item in ordered for conflict in item.conflicts)
    )
    uncertain = list(
        dict.fromkeys(value for item in ordered for value in item.uncertain_info)
    )
    successful = [item for item in ordered if item.status == "success"]
    confidence = (
        sum(item.confidence for item in successful) / len(successful)
        if successful
        else 0.0
    )
    return {
        "items": [item.model_dump(mode="json") for item in ordered],
        "recognized_text": "\n".join(
            item.recognized_text for item in successful if item.recognized_text
        ),
        "diagram_description": "\n".join(
            item.diagram_description for item in successful if item.diagram_description
        ),
        "confidence": confidence,
        "conflicts": conflicts,
        "uncertain_info": uncertain,
        "failed_count": len(ordered) - len(successful),
    }
