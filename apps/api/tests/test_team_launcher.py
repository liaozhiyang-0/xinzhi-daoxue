from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


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
            "IFLYTEK_SPARK_API_KEY": secret,
            "DASHSCOPE_API_KEY": secret,
        }
    )
    rendered = str(summary)
    assert secret not in rendered
    assert summary["provider_mode"] == "local_runtime"
    assert summary["secrets"]["IFLYTEK_SPARK_API_KEY"] == "configured"
    assert summary["secrets"]["DASHSCOPE_API_KEY"] == "configured"

def test_runtime_checks_report_project_services_without_secret_values(
    monkeypatch,
) -> None:
    launcher = load_launcher()
    monkeypatch.setattr(launcher, "python_environment_ready", lambda: (True, "3.13"))
    monkeypatch.setattr(launcher, "_listening_pids", lambda _port: [])
    monkeypatch.setattr(launcher, "owned_api_pids", lambda _port: [])
    monkeypatch.setattr(launcher, "docker_engine_ready", lambda: True)
    monkeypatch.setattr(
        launcher,
        "compose_service_states",
        lambda _environment: {
            "postgres": {"state": "running", "status": "Up (healthy)"},
            "redis": {"state": "running", "status": "Up (healthy)"},
            "minio": {"state": "running", "status": "Up (healthy)"},
            "qdrant": {"state": "running", "status": "Up"},
        },
    )
    monkeypatch.setattr(launcher, "api_ready", lambda _url: True)
    checks = launcher.runtime_checks(
        port=8031,
        environment={"DATABASE_URL": "postgresql://secret-host"},
    )
    assert all(check.passed for check in checks)
    assert "secret-host" not in str(checks)


def test_api_readiness_checks_root_health_endpoint_first(monkeypatch) -> None:
    launcher = load_launcher()
    requested: list[str] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def getcode(self) -> int:
            return 200

    def fake_urlopen(url: str, timeout: float):
        requested.append(f"{url}|{timeout}")
        return Response()

    monkeypatch.setattr(launcher, "urlopen", fake_urlopen)
    assert launcher.api_ready("http://127.0.0.1:8031")
    assert requested == ["http://127.0.0.1:8031/health|2"]


def test_frontend_build_check_matches_served_workspace_version(monkeypatch) -> None:
    launcher = load_launcher()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return (
                b'<script src="/debug-assets/ui-core.js?v='
                + launcher.FRONTEND_BUILD_ID.encode()
                + b'"></script>'
                b'<script src="/debug-assets/workspace.js?v='
                + launcher.FRONTEND_BUILD_ID.encode()
                + b'"></script>'
            )

    monkeypatch.setattr(launcher, "urlopen", lambda *_args, **_kwargs: Response())
    assert launcher.frontend_build_ready("http://127.0.0.1:8031")


def test_wait_for_services_reports_unready_dependencies(monkeypatch) -> None:
    launcher = load_launcher()
    monkeypatch.setattr(
        launcher,
        "compose_service_states",
        lambda _environment: {
            "postgres": {"state": "running", "status": "Up (health: starting)"},
            "redis": {"state": "running", "status": "Up (healthy)"},
        },
    )
    with pytest.raises(launcher.LaunchError, match="未就绪"):
        launcher.wait_for_project_services({}, timeout_seconds=0)


def test_reload_child_is_one_instance_but_independent_api_is_duplicate(
    monkeypatch,
) -> None:
    launcher = load_launcher()
    process_map = {
        100: launcher.ProcessInfo(
            100, 1, "python -m uvicorn app.main:app --app-dir apps/api --reload"
        ),
        101: launcher.ProcessInfo(101, 100, "python -c reload-child"),
        200: launcher.ProcessInfo(
            200, 1, "python -m uvicorn app.main:app --app-dir apps/api"
        ),
    }
    monkeypatch.setattr(launcher, "_all_process_info", lambda: process_map)
    monkeypatch.setattr(launcher, "_listening_pids", lambda _port: [101, 200])
    assert launcher.owned_api_pids(8000) == [100, 200]

    monkeypatch.setattr(launcher, "_listening_pids", lambda _port: [101])
    assert launcher.owned_api_pids(8000) == [100]


def test_worker_process_groups_deduplicate_parent_child(monkeypatch) -> None:
    launcher = load_launcher()
    process_map = {
        300: launcher.ProcessInfo(300, 1, "python apps/worker/worker.py"),
        301: launcher.ProcessInfo(301, 300, "python worker-child"),
        400: launcher.ProcessInfo(400, 1, "python apps/worker/worker.py"),
    }
    monkeypatch.setattr(launcher, "_all_process_info", lambda: process_map)
    assert launcher.owned_worker_pids() == [300, 400]


def test_launcher_main_reports_actionable_repair_failure(monkeypatch, capsys) -> None:
    launcher = load_launcher()
    monkeypatch.setattr(
        launcher,
        "repair_runtime_environment",
        lambda **_kwargs: (_ for _ in ()).throw(
            launcher.LaunchError("Redis 未就绪")
        ),
    )
    monkeypatch.setattr(launcher.sys, "argv", ["team_launcher.py", "repair"])
    assert launcher.main() == 1
    captured = capsys.readouterr()
    assert "Redis 未就绪" in captured.err
    assert "doctor" in captured.err


def test_repair_does_not_delete_or_recreate_data(monkeypatch) -> None:
    launcher = load_launcher()
    calls: list[str] = []
    monkeypatch.setattr(launcher, "ensure_env_file", lambda: Path(".env"))
    monkeypatch.setattr(launcher, "parse_dotenv", lambda _path: {})
    monkeypatch.setattr(launcher, "repair_python_environment", lambda: None)
    monkeypatch.setattr(launcher, "ensure_python_environment", lambda **_kwargs: None)
    monkeypatch.setattr(
        launcher,
        "runtime_checks",
        lambda **_kwargs: [launcher.RuntimeCheck("Docker 引擎", True, "运行中")],
    )
    monkeypatch.setattr(launcher, "_listening_pids", lambda _port: [])
    monkeypatch.setattr(
        launcher, "start_dependencies", lambda _env: calls.append("start")
    )
    monkeypatch.setattr(
        launcher, "migrate_database", lambda _env: calls.append("migrate")
    )
    monkeypatch.setattr(launcher, "api_ready", lambda _url: True)
    monkeypatch.setattr(launcher, "owned_api_pids", lambda _port: [1234])
    monkeypatch.setattr(launcher, "frontend_build_ready", lambda _url: True)
    monkeypatch.setattr(launcher, "print_runtime_checks", lambda _checks: 0)
    assert launcher.repair_runtime_environment(port=8031) == 0
    assert calls == ["start", "migrate"]


def test_parser_exposes_repair_command() -> None:
    launcher = load_launcher()
    args = launcher.build_parser().parse_args(["repair", "--port", "8031"])
    assert args.command == "repair"
    assert args.port == 8031


def test_parser_passes_port_to_doctor() -> None:
    launcher = load_launcher()
    args = launcher.build_parser().parse_args(["doctor", "--port", "8031"])
    assert args.command == "doctor"
    assert args.port == 8031


def test_repair_refuses_unknown_port_owner(monkeypatch) -> None:
    launcher = load_launcher()
    monkeypatch.setattr(launcher, "repair_python_environment", lambda: None)
    monkeypatch.setattr(launcher, "ensure_python_environment", lambda **_kwargs: None)
    monkeypatch.setattr(launcher, "ensure_env_file", lambda: Path(".env"))
    monkeypatch.setattr(launcher, "parse_dotenv", lambda _path: {})
    monkeypatch.setattr(launcher, "_listening_pids", lambda _port: [9876])
    monkeypatch.setattr(launcher, "owned_api_pids", lambda _port: [])
    with pytest.raises(launcher.LaunchError, match="未知进程"):
        launcher.repair_runtime_environment(port=8031)


def test_python_environment_probe_captures_version_output(
    monkeypatch, tmp_path: Path
) -> None:
    launcher = load_launcher()
    interpreter = tmp_path / "python.exe"
    interpreter.write_bytes(b"")
    monkeypatch.setattr(launcher, "VENV_PYTHON", interpreter)
    monkeypatch.setattr(
        launcher,
        "run_command",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout="(3, 13)\n"
        ),
    )
    assert launcher.python_environment_ready() == (True, "(3, 13)")


def test_launch_lock_rejects_a_second_local_api_start(monkeypatch, tmp_path) -> None:
    launcher = load_launcher()
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    first = launcher.SingleInstanceLaunchLock(8000)
    second = launcher.SingleInstanceLaunchLock(8000)
    first.acquire()
    try:
        with pytest.raises(launcher.LaunchError, match="already in progress"):
            second.acquire()
    finally:
        first.release()


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


def test_open_workspace_uses_workspace_url(monkeypatch) -> None:
    launcher = load_launcher()
    opened: list[tuple[str, int]] = []
    monkeypatch.setattr(
        launcher.webbrowser,
        "open",
        lambda url, new: opened.append((url, new)) or True,
    )

    assert launcher.open_workspace("http://127.0.0.1:8000/") is True
    assert opened == [("http://127.0.0.1:8000/workspace", 2)]


def test_start_reuses_running_api_without_starting_dependencies(monkeypatch) -> None:
    launcher = load_launcher()
    opened: list[str] = []
    monkeypatch.setattr(launcher, "api_ready", lambda _base_url: True)
    monkeypatch.setattr(launcher, "frontend_build_ready", lambda _base_url: True)
    monkeypatch.setattr(launcher, "owned_api_pids", lambda _port: [1234])
    monkeypatch.setattr(
        launcher, "open_workspace", lambda base_url: opened.append(base_url) or True
    )
    monkeypatch.setattr(
        launcher,
        "ensure_python_environment",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    args = SimpleNamespace(
        port=8000,
        open_browser=True,
        refresh_deps=False,
        reload=False,
    )

    assert launcher.command_start(args) == 0
    assert opened == ["http://127.0.0.1:8000"]


def test_start_restarts_duplicate_owned_api_processes(monkeypatch) -> None:
    launcher = load_launcher()
    stopped: list[int] = []
    monkeypatch.setattr(launcher, "api_ready", lambda _base_url: True)
    monkeypatch.setattr(launcher, "frontend_build_ready", lambda _base_url: True)
    monkeypatch.setattr(launcher, "owned_api_pids", lambda _port: [1234, 5678])
    monkeypatch.setattr(
        launcher, "stop_stale_api", lambda port: stopped.append(port)
    )
    args = SimpleNamespace(
        port=8000,
        open_browser=False,
        refresh_deps=False,
        reload=False,
    )

    assert launcher.command_start(args) == 0
    assert stopped == [8000]


def test_force_reload_restarts_one_owned_api_process(monkeypatch) -> None:
    launcher = load_launcher()
    stopped: list[int] = []
    readiness = iter([True, False, False])
    monkeypatch.setattr(launcher, "api_ready", lambda _base_url: next(readiness))
    monkeypatch.setattr(launcher, "owned_api_pids", lambda _port: [1234])
    monkeypatch.setattr(
        launcher, "stop_stale_api", lambda port: stopped.append(port)
    )
    monkeypatch.setattr(launcher, "ensure_env_file", lambda: Path("missing.env"))
    monkeypatch.setattr(launcher, "ensure_python_environment", lambda **_kwargs: None)
    monkeypatch.setattr(launcher, "start_dependencies", lambda _environment: None)
    monkeypatch.setattr(launcher, "migrate_database", lambda _environment: None)
    monkeypatch.setattr(
        launcher, "start_api", lambda _args, _environment: 0
    )
    args = SimpleNamespace(
        port=8000,
        open_browser=False,
        refresh_deps=False,
        reload=False,
        force_reload=True,
    )

    assert launcher.command_start(args) == 0
    assert stopped == [8000]


def test_stop_stops_owned_api_worker_before_base_services(monkeypatch) -> None:
    launcher = load_launcher()
    calls: list[str] = []
    monkeypatch.setattr(launcher, "require_docker", lambda: None)
    monkeypatch.setattr(launcher, "parse_dotenv", lambda _path: {})
    monkeypatch.setattr(launcher, "build_host_environment", lambda _dotenv: {})
    monkeypatch.setattr(launcher, "owned_api_groups", lambda port: {1234: {1234}})
    monkeypatch.setattr(
        launcher,
        "stop_stale_api",
        lambda port: calls.append(f"api:{port}"),
    )
    monkeypatch.setattr(launcher, "stop_stale_worker", lambda: calls.append("worker"))

    def fake_run_command(command, **_kwargs):
        calls.append("docker")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(launcher, "run_command", fake_run_command)

    assert launcher.command_stop(SimpleNamespace(port=8031)) == 0
    assert calls == ["api:8031", "worker", "docker"]


def test_stop_does_not_touch_unknown_listener(monkeypatch) -> None:
    launcher = load_launcher()
    calls: list[str] = []
    monkeypatch.setattr(launcher, "require_docker", lambda: None)
    monkeypatch.setattr(launcher, "parse_dotenv", lambda _path: {})
    monkeypatch.setattr(launcher, "build_host_environment", lambda _dotenv: {})
    monkeypatch.setattr(launcher, "owned_api_groups", lambda _port: {})
    monkeypatch.setattr(launcher, "stop_stale_api", lambda _port: calls.append("api"))
    monkeypatch.setattr(launcher, "stop_stale_worker", lambda: calls.append("worker"))
    monkeypatch.setattr(
        launcher,
        "run_command",
        lambda _command, **_kwargs: (
            calls.append("docker") or SimpleNamespace(returncode=0)
        ),
    )

    assert launcher.command_stop(SimpleNamespace(port=8000)) == 0
    assert calls == ["worker", "docker"]


def test_stop_reports_bounded_docker_shutdown(monkeypatch) -> None:
    launcher = load_launcher()
    monkeypatch.setattr(launcher, "require_docker", lambda: None)
    monkeypatch.setattr(launcher, "parse_dotenv", lambda _path: {})
    monkeypatch.setattr(launcher, "build_host_environment", lambda _dotenv: {})
    monkeypatch.setattr(launcher, "owned_api_groups", lambda _port: {})
    monkeypatch.setattr(launcher, "stop_stale_worker", lambda: None)

    def timed_out_run(command, **kwargs):
        assert command[:3] == ["docker", "compose", "stop"]
        assert kwargs["timeout_seconds"] == 30
        raise launcher.LaunchError("命令在 30 秒内未完成")

    monkeypatch.setattr(launcher, "run_command", timed_out_run)
    with pytest.raises(launcher.LaunchError, match="30 秒"):
        launcher.command_stop(SimpleNamespace(port=8000))


def test_double_click_launcher_uses_unified_local_startup() -> None:
    root = Path(__file__).resolve().parents[3]
    launcher = (root / "打开芯智导学.cmd").read_text(encoding="utf-8")

    assert "scripts\\team_launcher.py" in launcher
    assert "start --open-browser" in launcher
    assert "--with-cloud" not in launcher
    assert "uvicorn" not in launcher.lower()
