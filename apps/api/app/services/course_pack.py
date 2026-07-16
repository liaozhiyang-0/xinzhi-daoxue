from pathlib import Path

import yaml

from app.contracts import CoursePack
from app.core.config import PROJECT_ROOT
from app.core.errors import ConfigurationError


def load_course_pack(path: Path | None = None) -> CoursePack:
    target = (
        path
        or PROJECT_ROOT
        / "agent_configs"
        / "course_packs"
        / "course_ct_v1.yaml"
    )
    if not target.exists():
        raise ConfigurationError("CoursePack 文件不存在", details={"path": str(target)})
    try:
        payload = yaml.safe_load(target.read_text(encoding="utf-8"))
        return CoursePack.model_validate(payload)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise ConfigurationError(
            "CoursePack 加载失败", details={"path": str(target)}
        ) from exc
