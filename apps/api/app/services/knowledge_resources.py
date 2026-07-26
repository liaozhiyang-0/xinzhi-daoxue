from __future__ import annotations

from pathlib import Path, PurePosixPath

from app.core.config import Settings

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
TEXT_EXTENSIONS = {".md", ".txt"}


def resolve_course_resource(
    settings: Settings,
    *,
    course_id: str,
    relative_path: str,
    image_only: bool = False,
    text_only: bool = False,
) -> Path:
    if course_id not in settings.knowledge_paths:
        raise ValueError("未知课程编号")
    normalized = PurePosixPath(relative_path)
    if normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError("知识库资源路径不安全")
    root = settings.knowledge_paths[course_id].resolve()
    target = (root / normalized).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("知识库资源路径越界") from exc
    if image_only and target.suffix.casefold() not in IMAGE_EXTENSIONS:
        raise ValueError("资源不是允许的知识库图片")
    if text_only and target.suffix.casefold() not in TEXT_EXTENSIONS:
        raise ValueError("资源不是允许的知识库文本")
    if not target.is_file():
        raise FileNotFoundError("知识库资源不存在")
    return target


def resolve_kb_image_uri(settings: Settings, uri: str) -> Path:
    prefix = "kb-image://"
    if not uri.startswith(prefix):
        raise ValueError("不是 kb-image URI")
    value = uri.removeprefix(prefix)
    course_id, separator, relative = value.partition("/")
    if not separator or not relative:
        raise ValueError("kb-image URI 格式无效")
    return resolve_course_resource(
        settings,
        course_id=course_id,
        relative_path=relative,
        image_only=True,
    )
