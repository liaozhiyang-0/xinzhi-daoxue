from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEFAULT_AGENT_PROVIDER", "mock")
os.environ.setdefault("ALLOW_MOCK_FALLBACK", "true")
os.environ.setdefault("XINGCHEN_ENABLED", "false")

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


def export_openapi(output: Path) -> None:
    settings = Settings(
        app_env="test",
        test_database_url="sqlite+aiosqlite:///./openapi-export.db",
        default_agent_provider="mock",
    )
    schema = create_app(settings).openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    output = ROOT / "docs" / "api" / "openapi.json"
    export_openapi(output)
    print(f"OpenAPI exported: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
