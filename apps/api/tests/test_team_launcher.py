from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace


def load_launcher() -> ModuleType:
    root = Path(__file__).resolve().parents[3]
    path = root / "scripts/team_launcher.py"
    spec = importlib.util.spec_from_file_location("team_launcher", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dotenv_parser_supports_comments_quotes_and_equals(tmp_path: Path) -> None:
    launcher = load_launcher()
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# comment\nPLAIN=value\nQUOTED="hello world"\nURL=https://example.test?a=b\n',
        encoding="utf-8",
    )
    assert launcher.parse_dotenv(env_file) == {
        "PLAIN": "value",
        "QUOTED": "hello world",
        "URL": "https://example.test?a=b",
    }


def test_host_runtime_uses_host_endpoints(monkeypatch) -> None:
    launcher = load_launcher()
    for name in (
        "DATABASE_URL",
        "REDIS_URL",
        "MINIO_ENDPOINT",
        "QDRANT_URL",
        "HOST_DATABASE_URL",
        "HOST_REDIS_URL",
        "HOST_MINIO_ENDPOINT",
        "HOST_QDRANT_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    environment = launcher.build_host_environment(
        {
            "DATABASE_URL": "postgresql://postgres:5432/db",
            "HOST_DATABASE_URL": "postgresql://localhost:5432/db",
            "HOST_REDIS_URL": "redis://localhost:6379/0",
            "HOST_MINIO_ENDPOINT": "localhost:9000",
            "HOST_QDRANT_URL": "http://localhost:6333",
        }
    )
    assert environment["DATABASE_URL"] == "postgresql://localhost:5432/db"
    assert environment["REDIS_URL"] == "redis://localhost:6379/0"
    assert environment["MINIO_ENDPOINT"] == "localhost:9000"
    assert environment["QDRANT_MODE"] == "server"
    assert environment["COMPOSE_PROJECT_NAME"] == "xinzhi-daoxue"


def test_configuration_summary_never_returns_secret_values() -> None:
    launcher = load_launcher()
    secret = "this-value-must-never-be-returned"
    summary = launcher.configuration_summary(
        {
            "XINGCHEN_ENABLED": "true",
            "XINGCHEN_API_KEY": secret,
            "XINGCHEN_API_SECRET": secret,
        }
    )
    rendered = str(summary)
    assert secret not in rendered
    assert summary["secrets"]["XINGCHEN_API_KEY"] == "configured"
    assert summary["secrets"]["XINGCHEN_SOLVER_CT_FLOW_ID"] == "missing"


def test_compose_uses_stable_project_and_volume_names() -> None:
    root = Path(__file__).resolve().parents[3]
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "name: xinzhi-daoxue" in compose
    for volume in ("postgres", "redis", "minio", "qdrant"):
        assert f"name: xinzhi-daoxue_xzd_{volume}_data" in compose


def test_container_conflicts_only_reports_foreign_owners(monkeypatch) -> None:
    launcher = load_launcher()

    def fake_run(command, **_kwargs):
        container = command[-1]
        owners = {
            "xzd-postgres": "xinzhi-daoxue",
            "xzd-redis": "legacy-project",
            "xzd-minio": "",
        }
        if container == "xzd-qdrant":
            return SimpleNamespace(returncode=1, stdout="")
        return SimpleNamespace(returncode=0, stdout=owners[container])

    monkeypatch.setattr(launcher, "run_command", fake_run)
    assert launcher.container_conflicts() == [
        "xzd-redis (owner=legacy-project)",
        "xzd-minio (owner=unmanaged)",
    ]
