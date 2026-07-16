import os
import subprocess
import sys
from pathlib import Path


def run_alembic(root: Path, database: Path, *args: str) -> None:
    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["TEST_DATABASE_URL"] = f"sqlite+aiosqlite:///{database}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=root / "apps" / "api",
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_migration_upgrade_downgrade_upgrade(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    database = tmp_path / "migration.db"
    run_alembic(root, database, "upgrade", "head")
    run_alembic(root, database, "downgrade", "-1")
    run_alembic(root, database, "upgrade", "head")
