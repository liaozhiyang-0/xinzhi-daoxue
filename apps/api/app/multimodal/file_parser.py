from __future__ import annotations

from collections.abc import Sequence

from app.contracts import FileReference, InputType


def detect_input_type(files: Sequence[FileReference], *, has_text: bool) -> InputType:
    if not files:
        return InputType.TEXT
    has_pdf = any(item.content_type == "application/pdf" for item in files)
    has_images = any(item.content_type.startswith("image/") for item in files)
    if has_pdf and not has_images and not has_text:
        return InputType.PDF
    if has_images and not has_pdf and not has_text:
        return InputType.IMAGE
    return InputType.MIXED
