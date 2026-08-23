from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import cast
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
VENV_PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
DEPENDENCY_MARKER = VENV / ".xzd-dependencies"
SERVICES = ("postgres", "redis", "minio", "qdrant")
HOST_OVERRIDES = {
    "DATABASE_URL": "HOST_DATABASE_URL",
    "REDIS_URL": "HOST_REDIS_URL",
    "MINIO_ENDPOINT": "HOST_MINIO_ENDPOINT",
    "QDRANT_URL": "HOST_QDRANT_URL",
}
SECRET_NAMES = (
    "IFLYTEK_SPARK_API_KEY",
    "DASHSCOPE_API_KEY",
)
COMPOSE_PROJECT_NAME = "xinzhi-daoxue"
CONTAINER_NAMES = ("xzd-postgres", "xzd-redis", "xzd-minio", "xzd-qdrant")
REACT_ASSET_PREFIX = "/react-assets/assets/index-"
SERVICE_READY_TIMEOUT_SECONDS = 90
class LaunchError(RuntimeError):
    """A safe, user-facing launcher failure."""


class RuntimeCheck:
    """One redacted local-environment check result."""

    __slots__ = ("name", "passed", "detail", "repairable")

    def __init__(
        self,
        name: str,
        passed: bool,
        detail: str,
        repairable: bool = False,
    ) -> None:
        self.name = name
        self.passed = passed
        self.detail = detail
        self.repairable = repairable


class ProcessInfo:
    """Minimal process metadata used for safe project ownership checks."""

    __slots__ = ("pid", "parent_pid", "command_line")

    def __init__(self, pid: int, parent_pid: int, command_line: str) -> None:
        self.pid = pid
        self.parent_pid = parent_pid
        self.command_line = command_line

    pid: int
    parent_pid: int
    command_line: str


class SingleInstanceLaunchLock:
    """Serialize local API starts for one port without killing unknown owners."""

    def __init__(self, port: int) -> None:
        self.path = ROOT / ".codex-tmp" / f"team-launcher-{port}.lock"
        self._file_descriptor: int | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                descriptor = os.open(
                    self.path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
            except FileExistsError as err:
                owner = self._owner_pid()
                if owner is not None and _process_is_running(owner):
                    raise LaunchError(
                        "another local API launch is already in progress; "
                        "wait for it to finish"
                    ) from err
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    continue
                continue
            os.write(descriptor, f"{os.getpid()}\n".encode("ascii"))
            self._file_descriptor = descriptor
            return
        raise LaunchError("could not acquire the local API launch lock")

    def release(self) -> None:
        descriptor = self._file_descriptor
        self._file_descriptor = None
        if descriptor is not None:
            os.close(descriptor)
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass

    def _owner_pid(self) -> int | None:
        try:
            value = self.path.read_text(encoding="ascii").strip()
            return int(value) if value else None
        except (OSError, ValueError):
            return None


def _process_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # Windows maps ``os.kill(pid, 0)`` to an actual termination attempt;
        # use a non-destructive process handle probe instead.
        import ctypes

        process_query_limited_information = 0x1000
        synchronize = 0x00100000
        wait_timeout = 0x00000102
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(
            process_query_limited_information | synchronize,
            False,
            pid,
        )
        if not handle:
            return ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED
        try:
            return kernel32.WaitForSingleObject(handle, 0) == wait_timeout
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().upper()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def ensure_env_file() -> Path:
    target = ROOT / ".env"
    if target.exists():
        return target
    source = ROOT / ".env.example"
    if not source.is_file():
        raise LaunchError("缺少 .env.example，无法初始化本地配置。")
    shutil.copyfile(source, target)
    print("[xzd] 已创建本机 .env；该文件已被 Git 忽略，不会上传。")
    print("[xzd] 国产模型基础调用只需填写 IFLYTEK_SPARK_API_KEY 和 DASHSCOPE_API_KEY。")
    return target


def build_host_environment(dotenv: dict[str, str]) -> dict[str, str]:
    environment = {**dotenv, **os.environ}
    defaults = {
        "DATABASE_URL": "postgresql+asyncpg://xzd_user:xzd_password@localhost:5432/xzd",
        "REDIS_URL": "redis://localhost:6379/0",
        "MINIO_ENDPOINT": "localhost:9000",
        "QDRANT_URL": "http://localhost:6333",
    }
    for runtime_name, host_name in HOST_OVERRIDES.items():
        environment[runtime_name] = environment.get(host_name) or defaults[runtime_name]
    environment["QDRANT_MODE"] = "server"
    environment["COMPOSE_PROJECT_NAME"] = COMPOSE_PROJECT_NAME
    environment.setdefault("APP_ENV", "development")
    environment.setdefault("RAG_CPU_MODE", "1")
    return environment




def configuration_summary(dotenv: dict[str, str]) -> dict[str, object]:
    return {
        "env_file": "configured" if (ROOT / ".env").is_file() else "missing",
        "provider_mode": "local_runtime",
        "secrets": {
            name: "configured" if bool(dotenv.get(name, "").strip()) else "missing"
            for name in SECRET_NAMES
        },
    }


def run_command(
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    capture: bool = False,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=False,
            text=True,
            capture_output=capture,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise LaunchError(
            f"Command timed out after {timeout_seconds:g}s: {' '.join(command)}. "
            "Check Docker or the affected service, then retry."
        ) from exc


def python_environment_ready() -> tuple[bool, str]:
    """Probe the project interpreter without exposing command output."""

    if not VENV_PYTHON.is_file():
        return False, "虚拟环境解释器缺失"
    result = run_command(
        [str(VENV_PYTHON), "-c", "import sys; print(sys.version_info[:2])"],
        capture=True,
    )
    if result.returncode != 0:
        return False, "虚拟环境解释器无法启动"
    return True, result.stdout.strip() or "可启动"


def _python_repair_candidates() -> list[Path]:
    """Find system interpreters that can rebuild a broken local venv."""

    candidates: list[Path] = []
    cfg = VENV / "pyvenv.cfg"
    if cfg.is_file():
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("home ="):
                home = Path(line.split("=", 1)[1].strip())
                candidates.append(
                    home / ("python.exe" if os.name == "nt" else "python")
                )
                break
    if os.name == "nt":
        launcher = shutil.which("py.exe") or shutil.which("py")
        if launcher:
            for version in ("3.13", "3.12", "3.11"):
                result = run_command(
                    [
                        launcher,
                        f"-{version}",
                        "-c",
                        "import sys; print(sys.executable)",
                    ],
                    capture=True,
                )
                if result.returncode == 0:
                    candidates.append(Path(result.stdout.strip()))
    current = Path(sys.executable)
    if VENV not in current.parents:
        candidates.append(current)
    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file() and resolved not in unique:
            unique.append(resolved)
    return unique


def repair_python_environment() -> None:
    """Rebuild only a broken venv, retaining a recoverable backup."""

    ready, _detail = python_environment_ready()
    if ready:
        return
    if not VENV.exists():
        # A missing environment is created by ensure_python_environment().
        # Only move an existing, broken environment into the recoverable
        # backup area.
        return
    candidates = _python_repair_candidates()
    if not candidates:
        raise LaunchError(
            "项目虚拟环境无法启动，且未找到可用系统 Python；"
            "请安装 Python 3.11-3.13 后运行 repair。"
        )
    backup_root = ROOT / ".codex-tmp" / "venv-backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / f"venv-{int(time.time())}"
    shutil.move(str(VENV), str(backup))
    try:
        result = run_command([str(candidates[0]), "-m", "venv", str(VENV)])
        if result.returncode != 0:
            raise LaunchError(
                "重建 Python 虚拟环境失败；旧环境已保存在 "
                ".codex-tmp/venv-backups。"
            )
        ready, _detail = python_environment_ready()
        if not ready:
            raise LaunchError("新建的 Python 虚拟环境仍无法启动；旧环境已保留备份。")
    except Exception:
        if VENV.exists():
            failed_backup = backup_root / f"failed-{int(time.time())}"
            shutil.move(str(VENV), str(failed_backup))
        shutil.move(str(backup), str(VENV))
        raise
    print(f"[xzd] 已重建 Python 虚拟环境；旧环境备份：{backup}")


def require_docker() -> None:
    if shutil.which("docker") is None:
        raise LaunchError("未找到 Docker。请先安装并启动 Docker Desktop。")
    if not docker_engine_ready():
        raise LaunchError("Docker Desktop 尚未运行。请启动 Docker Desktop 后重试。")


def _docker_desktop_path() -> Path | None:
    if os.name != "nt":
        return None
    candidates = [
        Path(os.environ.get("ProgramFiles", ""))
        / "Docker/Docker/Docker Desktop.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Programs/Docker/Docker/Docker Desktop.exe",
    ]
    return next((path for path in candidates if path.is_file()), None)


def start_docker_engine() -> bool:
    """Best-effort start of a local Docker engine, without elevated commands."""

    if docker_engine_ready():
        return True
    try:
        if os.name == "nt":
            executable = _docker_desktop_path()
            if executable is None:
                return False
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(  # noqa: S603
                [str(executable)],
                cwd=ROOT,
                creationflags=creation_flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif sys.platform == "darwin":
            if shutil.which("open") is None:
                return False
            run_command(["open", "-a", "Docker"], capture=True)
        elif shutil.which("systemctl") is not None:
            run_command(["systemctl", "--user", "start", "docker"], capture=True)
        else:
            return False
    except OSError:
        return False
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if docker_engine_ready():
            return True
        time.sleep(1)
    return False


def ensure_docker_engine() -> None:
    if shutil.which("docker") is None:
        raise LaunchError(
            "未找到 Docker CLI；请安装 Docker Desktop/Engine 后重新运行 start。"
        )
    if start_docker_engine():
        return
    raise LaunchError(
        "Docker 引擎未就绪，且无法自动启动。请手动启动 Docker Desktop，"
        "确认 `docker info` 成功后再运行 `.\\xzd.ps1 start`。"
    )


def docker_engine_ready() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def dependency_fingerprint() -> str:
    return hashlib.sha256((ROOT / "apps/api/pyproject.toml").read_bytes()).hexdigest()


def ensure_python_environment(*, refresh: bool) -> None:
    if not VENV_PYTHON.is_file():
        print(f"[xzd] 创建 Python 虚拟环境：{VENV.name}")
        result = run_command([sys.executable, "-m", "venv", str(VENV)])
        if result.returncode != 0:
            raise LaunchError(
                "创建 Python 虚拟环境失败。请确认已安装 Python 3.11-3.13。"
            )
    fingerprint = dependency_fingerprint()
    imports = run_command(
        [str(VENV_PYTHON), "-c", "import alembic, fastapi, uvicorn"], capture=True
    )
    marker = (
        DEPENDENCY_MARKER.read_text(encoding="utf-8").strip()
        if DEPENDENCY_MARKER.exists()
        else ""
    )
    if not refresh and imports.returncode == 0 and marker == fingerprint:
        print("[xzd] Python 依赖已就绪。")
        return
    print("[xzd] 安装或更新项目依赖（首次运行可能需要几分钟）...")
    result = run_command(
        [str(VENV_PYTHON), "-m", "pip", "install", "-e", "apps/api[dev]"]
    )
    if result.returncode != 0:
        raise LaunchError("Python 依赖安装失败。请检查网络和 pip 输出。")
    DEPENDENCY_MARKER.write_text(fingerprint, encoding="utf-8")


def start_dependencies(environment: dict[str, str]) -> None:
    ensure_docker_engine()
    conflicts = container_conflicts()
    if conflicts:
        names = ", ".join(conflicts)
        raise LaunchError(
            "发现其他旧 Compose 项目占用容器名："
            f"{names}。请先停止并重命名这些旧容器，数据卷不会被删除。"
        )
    print("[xzd] 启动 PostgreSQL、Redis、MinIO 和 Qdrant...")
    command = ["docker", "compose", "up", "-d", "--wait", *SERVICES]
    result = run_command(command, env=environment)
    if result.returncode != 0:
        raise LaunchError("基础服务启动失败。请运行 '.\\xzd.ps1 status' 查看状态。")
    wait_for_project_services(environment)


def wait_for_project_services(
    environment: dict[str, str],
    *,
    timeout_seconds: int = SERVICE_READY_TIMEOUT_SECONDS,
) -> None:
    """Wait for the exact project containers, with a bounded failure report."""

    deadline = time.monotonic() + timeout_seconds
    last_states: dict[str, dict[str, str]] = {}
    while True:
        last_states = compose_service_states(environment)
        if all(
            service in last_states
            and last_states[service]["state"] == "running"
            and (
                service == "qdrant"
                or "healthy" in last_states[service]["status"].lower()
            )
            for service in SERVICES
        ):
            return
        if time.monotonic() >= deadline:
            break
        time.sleep(1)
    summary = ", ".join(
        f"{service}={last_states.get(service, {}).get('status', 'missing')}"
        for service in SERVICES
    )
    raise LaunchError(
        "PostgreSQL/Redis/MinIO/Qdrant 在限定时间内未就绪："
        f"{summary}。请运行 `.\\xzd.ps1 status` 和 `docker compose logs --tail=80`。"
    )


def container_conflicts() -> list[str]:
    conflicts: list[str] = []
    for name in CONTAINER_NAMES:
        result = run_command(
            [
                "docker",
                "inspect",
                "--format",
                '{{index .Config.Labels "com.docker.compose.project"}}',
                name,
            ],
            capture=True,
        )
        if result.returncode != 0:
            continue
        owner = result.stdout.strip()
        if owner != COMPOSE_PROJECT_NAME:
            conflicts.append(f"{name} (owner={owner or 'unmanaged'})")
    return conflicts


def compose_service_states(environment: dict[str, str]) -> dict[str, dict[str, str]]:
    """Read project container state without exposing env values."""

    result = run_command(
        [
            "docker",
            "compose",
            "ps",
            "--format",
            "json",
            *SERVICES,
        ],
        env=environment,
        capture=True,
    )
    if result.returncode != 0:
        return {}
    states: dict[str, dict[str, str]] = {}
    try:
        decoded = json.loads(result.stdout)
    except json.JSONDecodeError:
        decoded = [
            json.loads(raw_line)
            for raw_line in result.stdout.splitlines()
            if raw_line.strip()
        ]
    items = decoded if isinstance(decoded, list) else [decoded]
    for item in items:
        if not isinstance(item, dict):
            continue
        service = str(item.get("Service") or item.get("Name") or "")
        if service in SERVICES:
            states[service] = {
                "state": str(item.get("State") or "unknown"),
                "status": str(item.get("Status") or ""),
            }
    return states


def runtime_checks(
    *, port: int = 8000, environment: dict[str, str] | None = None
) -> list[RuntimeCheck]:
    """Collect actionable, non-secret checks for the local development stack."""

    environment_supplied = environment is not None
    env = (
        environment
        if environment_supplied
        else build_host_environment(parse_dotenv(ROOT / ".env"))
    )
    dotenv_present = (ROOT / ".env").is_file()
    docker_ok = shutil.which("docker") is not None and docker_engine_ready()
    python_ok, python_detail = python_environment_ready()
    checks = [
        RuntimeCheck(
            "Python 3.11-3.13",
            (3, 11) <= sys.version_info[:2] < (3, 14),
            sys.version.split()[0],
        ),
        RuntimeCheck(
            "项目虚拟环境",
            python_ok,
            python_detail,
            repairable=True,
        ),
        RuntimeCheck(
            ".env",
            dotenv_present or environment_supplied,
            (
                "存在"
                if dotenv_present
                else "已提供显式运行环境"
                if environment_supplied
                else "缺失（start 可创建）"
            ),
            repairable=True,
        ),
        RuntimeCheck(
            ".env 未被 Git 跟踪",
            not bool(
                run_command(["git", "ls-files", ".env"], capture=True).stdout.strip()
            ),
            "安全",
        ),
        RuntimeCheck(
            "Docker 引擎",
            docker_ok,
            "运行中" if docker_ok else "不可用",
            repairable=True,
        ),
    ]
    if not docker_ok:
        checks.append(
            RuntimeCheck("基础容器", False, "无法检查 Docker 容器", repairable=True)
        )
    else:
        states = compose_service_states(env)
        for service in SERVICES:
            state = states.get(service)
            healthy = state is not None and state["state"] == "running" and (
                service == "qdrant" or "healthy" in state["status"].lower()
            )
            detail = state["status"] if state else "未创建或未运行"
            checks.append(
                RuntimeCheck(f"容器 {service}", healthy, detail, repairable=True)
            )
    listening = _listening_pids(port)
    api_groups = owned_api_groups(port) if listening else {}
    owned = sorted(api_groups)
    owned_listeners = {
        pid for member_pids in api_groups.values() for pid in member_pids
    }
    unknown = [pid for pid in listening if pid not in owned_listeners]
    if unknown:
        port_detail = f"未知进程占用：{','.join(map(str, unknown))}"
        port_ok = False
    elif len(owned) > 1:
        port_detail = f"本项目重复 API 进程：{','.join(map(str, owned))}"
        port_ok = False
    else:
        port_detail = "空闲" if not listening else f"本项目单实例：{owned[0]}"
        port_ok = True
    checks.append(RuntimeCheck(f"端口 :{port}", port_ok, port_detail))
    api_url = f"http://127.0.0.1:{port}"
    api_is_ready = api_ready(api_url)
    checks.append(
        RuntimeCheck(
            f"API :{port}",
            api_is_ready,
            "可访问" if api_is_ready else "未就绪",
            repairable=True,
        )
    )
    worker_required = env.get("TASK_EXECUTOR_MODE", "local").strip().lower() == "redis"
    worker_pids = owned_worker_pids() if worker_required else []
    worker_ok = not worker_required or len(worker_pids) == 1
    if worker_required:
        worker_detail = (
            f"本项目单实例：{worker_pids[0]}"
            if len(worker_pids) == 1
            else (
                "需要 1 个 Worker，当前 PID："
                f"{','.join(map(str, worker_pids)) or '无'}"
            )
        )
    else:
        worker_detail = "TASK_EXECUTOR_MODE=local，无需独立 Worker"
    checks.append(
        RuntimeCheck("Worker 单实例", worker_ok, worker_detail, repairable=True)
    )
    return checks


def print_runtime_checks(checks: list[RuntimeCheck]) -> int:
    print("芯智导学本地运行环境自检")
    for check in checks:
        print(f"[{'PASS' if check.passed else 'FAIL'}] {check.name}: {check.detail}")
    failed = sum(not check.passed for check in checks)
    print(f"结果：{len(checks) - failed}/{len(checks)} 通过")
    return 0 if failed == 0 else 1


def repair_runtime_environment(*, port: int = 8000) -> int:
    """Repair only project-owned, restartable local services.

    This intentionally does not remove containers, volumes, images, or files.
    """

    repair_python_environment()
    ensure_python_environment(refresh=False)
    dotenv = parse_dotenv(ensure_env_file())
    environment = build_host_environment(dotenv)
    listening = _listening_pids(port)
    api_groups = owned_api_groups(port) if listening else {}
    owned = sorted(api_groups)
    owned_listeners = {
        pid for member_pids in api_groups.values() for pid in member_pids
    }
    unknown = [pid for pid in listening if pid not in owned_listeners]
    if unknown:
        raise LaunchError(
            f"端口 {port} 被未知进程占用（PID {','.join(map(str, unknown))}），"
            "未自动接管。"
        )
    if len(owned) > 1:
        stop_stale_api(port)
    checks = runtime_checks(port=port, environment=environment)
    if not any(check.name == "Docker 引擎" and check.passed for check in checks):
        print("[xzd] Docker 引擎不可用；未执行破坏性操作。")
        return print_runtime_checks(checks)
    start_dependencies(environment)
    migrate_database(environment)
    base_url = f"http://127.0.0.1:{port}"
    if api_ready(base_url):
        if not owned_api_pids(port):
            raise LaunchError(f"端口 {port} 上是未知服务，未自动接管。")
        if not frontend_build_ready(base_url):
            stop_stale_api(port)
            return start_api(
                argparse.Namespace(
                    port=port,
                    reload=False,
                    open_browser=False,
                ),
                environment,
            )
        print(f"[xzd] API 已运行且前端版本正确：{base_url}")
        return print_runtime_checks(runtime_checks(port=port, environment=environment))
    if _listening_pids(port):
        if owned_api_pids(port):
            stop_stale_api(port)
        else:
            raise LaunchError(f"端口 {port} 上已有未知服务，未自动接管。")
    return start_api(
        argparse.Namespace(
            port=port,
            reload=False,
            open_browser=False,
        ),
        environment,
    )


def migrate_database(environment: dict[str, str]) -> None:
    print("[xzd] 应用数据库增量迁移...")
    result = run_command(
        [str(VENV_PYTHON), "-m", "alembic", "upgrade", "head"],
        cwd=ROOT / "apps/api",
        env=environment,
    )
    if result.returncode != 0:
        raise LaunchError("数据库迁移失败；请确认 PostgreSQL 已健康并检查上方日志。")


def api_ready(base_url: str) -> bool:
    for path in ("/health", "/api/v1/health"):
        try:
            with urlopen(f"{base_url}{path}", timeout=2) as response:  # noqa: S310
                if cast(int, response.getcode()) == 200:
                    return True
        except (URLError, TimeoutError, OSError):
            continue
    return False


def frontend_build_ready(base_url: str) -> bool:
    """Return whether the running service serves the current frontend build."""

    try:
        with urlopen(f"{base_url}/workspace", timeout=2) as response:  # noqa: S310
            html = response.read().decode("utf-8", errors="replace")
        return (
            '<div id="root"></div>' in html
            and REACT_ASSET_PREFIX in html
            and "legacy-workspace-contract" not in html
            and "workspace.js" not in html
        )
    except (URLError, TimeoutError, OSError, UnicodeError):
        return False


def _listening_pids(port: int) -> list[int]:
    """Find local listeners without using a broad process termination."""

    if os.name == "nt":
        result = run_command(["netstat", "-ano", "-p", "tcp"], capture=True)
        if result.returncode != 0:
            return []
        pids: set[int] = set()
        for line in result.stdout.splitlines():
            columns = line.split()
            if len(columns) < 5 or columns[0].upper() != "TCP":
                continue
            if columns[3].upper() != "LISTENING":
                continue
            local_port = columns[1].rsplit(":", 1)[-1]
            if local_port == str(port) and columns[4].isdigit():
                pids.add(int(columns[4]))
        return sorted(pids)

    result = run_command(["lsof", "-ti", f"tcp:{port}"], capture=True)
    if result.returncode != 0:
        return []
    return sorted({int(value) for value in result.stdout.split() if value.isdigit()})


def _process_command_line(pid: int) -> str:
    if os.name == "nt":
        result = run_command(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Process "
                f"-Filter 'ProcessId={pid}').CommandLine",
            ],
            capture=True,
        )
        return result.stdout.strip()
    result = run_command(["ps", "-p", str(pid), "-o", "command="], capture=True)
    return result.stdout.strip()


def _process_parent_pid(pid: int) -> int:
    if os.name == "nt":
        result = run_command(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Process "
                f"-Filter 'ProcessId={pid}').ParentProcessId",
            ],
            capture=True,
        )
    else:
        result = run_command(["ps", "-p", str(pid), "-o", "ppid="], capture=True)
    value = result.stdout.strip()
    return int(value) if value.isdigit() else 0


def _all_process_info() -> dict[int, ProcessInfo]:
    """Read process metadata in one platform-native query when possible."""

    if os.name == "nt":
        script = (
            "$items = Get-CimInstance Win32_Process | "
            "Select-Object ProcessId,ParentProcessId,CommandLine; "
            "if ($null -eq $items) { '[]' } "
            "else { $items | ConvertTo-Json -Compress }"
        )
        result = run_command(
            ["powershell.exe", "-NoProfile", "-Command", script], capture=True
        )
        if result.returncode != 0:
            return {}
        try:
            decoded = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {}
        items = decoded if isinstance(decoded, list) else [decoded]
        info: dict[int, ProcessInfo] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                pid_value = item.get("ProcessId")
                parent_pid_value = item.get("ParentProcessId")
                if not isinstance(pid_value, (int, str)):
                    continue
                if not isinstance(parent_pid_value, (int, str)):
                    parent_pid_value = 0
                pid = int(pid_value)
                parent_pid = int(parent_pid_value)
            except (TypeError, ValueError):
                continue
            info[pid] = ProcessInfo(
                pid=pid,
                parent_pid=parent_pid,
                command_line=str(item.get("CommandLine") or ""),
            )
        return info

    result = run_command(
        ["ps", "-e", "-o", "pid=", "-o", "ppid=", "-o", "command="],
        capture=True,
    )
    if result.returncode != 0:
        return {}
    info = {}
    for line in result.stdout.splitlines():
        columns = line.strip().split(maxsplit=2)
        if len(columns) != 3 or not columns[0].isdigit() or not columns[1].isdigit():
            continue
        pid, parent_pid = int(columns[0]), int(columns[1])
        info[pid] = ProcessInfo(pid, parent_pid, columns[2])
    return info


def _process_kind(command_line: str) -> str | None:
    """Return API/Worker only for commands carrying project-specific markers."""

    normalized = command_line.lower().replace("\\", "/")
    if (
        "uvicorn" in normalized
        and "app.main:app" in normalized
        and ("--app-dir apps/api" in normalized or "/apps/api" in normalized)
    ):
        return "api"
    if "apps/worker/worker.py" in normalized:
        return "worker"
    return None


def _process_info_for_pid(
    pid: int, process_map: dict[int, ProcessInfo]
) -> ProcessInfo:
    existing = process_map.get(pid)
    if existing is not None:
        return existing
    info = ProcessInfo(pid, _process_parent_pid(pid), _process_command_line(pid))
    process_map[pid] = info
    return info


def _project_root_for_pid(
    pid: int,
    kind: str,
    process_map: dict[int, ProcessInfo],
) -> int | None:
    current = pid
    root: int | None = None
    visited: set[int] = set()
    while current > 0 and current not in visited:
        visited.add(current)
        info = _process_info_for_pid(current, process_map)
        if _process_kind(info.command_line) == kind:
            root = current
        current = info.parent_pid
    return root


def _project_process_groups(
    kind: str,
    candidate_pids: list[int] | None = None,
) -> dict[int, set[int]]:
    process_map = _all_process_info()
    candidates = candidate_pids or sorted(process_map)
    groups: dict[int, set[int]] = {}
    for pid in candidates:
        root = _project_root_for_pid(pid, kind, process_map)
        if root is not None:
            groups.setdefault(root, set()).add(pid)
    return groups


def owned_api_groups(port: int) -> dict[int, set[int]]:
    """Group API listeners by their top project API ancestor."""

    return _project_process_groups("api", _listening_pids(port))


def owned_worker_pids() -> list[int]:
    """Return one PID per independent project Worker launch chain."""

    return sorted(_project_process_groups("worker"))


def stop_stale_worker() -> None:
    """Stop all confirmed project Worker launch chains before a clean restart."""

    groups = _project_process_groups("worker")
    if not groups:
        return
    for root_pid, member_pids in groups.items():
        _stop_project_process_tree(root_pid, member_pids)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and owned_worker_pids():
        time.sleep(0.25)
    remaining = owned_worker_pids()
    if remaining:
        raise LaunchError(
            "项目 Worker 仍未退出（PID "
            f"{','.join(map(str, remaining))}），请手动停止后重试。"
        )


def _stop_project_process_tree(root_pid: int, member_pids: set[int]) -> None:
    if os.name == "nt":
        result = run_command(
            ["taskkill", "/PID", str(root_pid), "/T", "/F"], capture=True
        )
    else:
        result = run_command(["kill", "-TERM", str(root_pid)], capture=True)
        for pid in sorted(member_pids - {root_pid}):
            run_command(["kill", "-TERM", str(pid)], capture=True)
    if result.returncode != 0 and _process_is_running(root_pid):
        raise LaunchError(
            f"项目 {root_pid} 进程链停止失败；未执行更宽范围的进程清理。"
        )


def stop_stale_api(port: int) -> None:
    """Stop only project API launch chains, never an unrelated listener."""

    groups = owned_api_groups(port)
    if not groups:
        raise LaunchError(
            f"端口 {port} 上运行的是未知服务，未自动终止；请先手动停止后重试。"
        )
    for root_pid, member_pids in groups.items():
        _stop_project_process_tree(root_pid, member_pids)
    deadline = time.time() + 10
    while time.time() < deadline and owned_api_groups(port):
        time.sleep(0.25)
    remaining_groups = owned_api_groups(port)
    remaining = sorted(remaining_groups)
    if remaining and os.name == "nt":
        for pid in remaining:
            run_command(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    f"Stop-Process -Id {pid} -Force",
                ],
                capture=True,
            )
        deadline = time.time() + 5
        while time.time() < deadline and owned_api_groups(port):
            time.sleep(0.25)
    remaining = sorted(owned_api_groups(port))
    if remaining:
        raise LaunchError(
            f"旧 Web 进程仍未退出（PID {','.join(map(str, remaining))}），请手动重启。"
        )


def owned_api_pids(port: int) -> list[int]:
    """Return one PID per independent API chain, not reload child processes."""

    return sorted(owned_api_groups(port))


def open_workspace(base_url: str) -> bool:
    url = f"{base_url.rstrip('/')}/workspace"
    try:
        opened = webbrowser.open(url, new=2)
    except (OSError, webbrowser.Error):
        opened = False
    if opened:
        print(f"[xzd] 已在默认浏览器打开：{url}")
    else:
        print(f"[xzd] 无法自动打开浏览器，请手动访问：{url}")
    return opened


def start_worker(environment: dict[str, str]) -> subprocess.Popen[bytes]:
    worker_environment = dict(environment)
    api_root = str(ROOT / "apps/api")
    existing_pythonpath = worker_environment.get("PYTHONPATH", "")
    worker_environment["PYTHONPATH"] = (
        api_root
        if not existing_pythonpath
        else os.pathsep.join((api_root, existing_pythonpath))
    )
    return subprocess.Popen(  # noqa: S603
        [str(VENV_PYTHON), str(ROOT / "apps/worker/worker.py")],
        cwd=ROOT,
        env=worker_environment,
    )


def start_api(args: argparse.Namespace, environment: dict[str, str]) -> int:
    base_url = f"http://127.0.0.1:{args.port}"
    command = [
        str(VENV_PYTHON),
        "-m",
        "uvicorn",
        "app.main:app",
        "--app-dir",
        "apps/api",
        "--host",
        "0.0.0.0",
        "--port",
        str(args.port),
    ]
    if args.reload:
        command.append("--reload")
    print(f"[xzd] 启动 Web：{base_url}/")
    launch_lock = SingleInstanceLaunchLock(args.port)
    launch_lock.acquire()
    process: subprocess.Popen[bytes] | None = None
    worker_process: subprocess.Popen[bytes] | None = None
    try:
        # Another launcher may have bound the port while this process waited
        # for the start lock. Reuse that service instead of spawning a second
        # API/worker process.
        if api_ready(base_url):
            launch_lock.release()
            if args.open_browser:
                open_workspace(base_url)
            return 0
        if environment.get("TASK_EXECUTOR_MODE", "local").strip().lower() == "redis":
            worker_pids = owned_worker_pids()
            if len(worker_pids) > 1:
                stop_stale_worker()
                worker_pids = []
            if not worker_pids:
                worker_process = start_worker(environment)
        process = subprocess.Popen(command, cwd=ROOT, env=environment)  # noqa: S603
        for _ in range(90):
            if worker_process is not None and worker_process.poll() is not None:
                raise LaunchError(
                    "Task Worker 启动失败；请检查 Redis 状态和 Worker 日志。"
                )
            if process.poll() is not None:
                raise LaunchError("FastAPI 启动失败；请查看上方服务器日志。")
            if api_ready(base_url):
                break
            time.sleep(0.5)
        else:
            raise LaunchError("FastAPI 在 45 秒内未就绪；请查看上方服务器日志。")
        print("\n[xzd] 服务已就绪")
        print(f"  统一首页：{base_url}/")
        print(f"  学生端：  {base_url}/student")
        print(f"  演示中心：{base_url}/demo?presentation=1")
        print(f"  系统状态：{base_url}/system")
        print("  按 Ctrl+C 停止 Web；需要停止容器时运行 '.\\xzd.ps1 stop'。\n")
        if args.open_browser:
            open_workspace(base_url)
        launch_lock.release()
        assert process is not None
        return int(process.wait())
    except KeyboardInterrupt:
        print("\n[xzd] 正在停止 Web...")
        return 0
    finally:
        launch_lock.release()
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        if worker_process is not None and worker_process.poll() is None:
            worker_process.terminate()
            try:
                worker_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker_process.kill()


def command_start(args: argparse.Namespace) -> int:
    if not (3, 11) <= sys.version_info[:2] < (3, 14):
        raise LaunchError("需要 Python 3.11-3.13；当前 Python 版本不受支持。")
    base_url = f"http://127.0.0.1:{args.port}"
    running_pids = owned_api_pids(args.port)
    force_reloaded = False
    if getattr(args, "force_reload", False) and api_ready(base_url):
        if not running_pids:
            raise LaunchError(
                f"端口 {args.port} 上的服务不是本项目 Uvicorn，未自动终止"
            )
        print("[xzd] 按请求强制重载本项目 Web 服务")
        stop_stale_api(args.port)
        running_pids = []
        force_reloaded = True
    if api_ready(base_url):
        if len(running_pids) == 0:
            raise LaunchError(
                f"端口 {args.port} 上运行的是未知服务，未自动复用；请先手动停止后重试。"
            )
        if not frontend_build_ready(base_url) or len(running_pids) > 1:
            reason = "重复 Web 进程" if len(running_pids) > 1 else "旧版 Web 服务"
            print(f"[xzd] 检测到{reason}，正在重启以加载最新代码和前端。")
            if not getattr(args, "force_reload", False):
                stop_stale_api(args.port)
    elif not force_reloaded and _listening_pids(args.port):
        if owned_api_pids(args.port):
            print(f"[xzd] 端口 {args.port} 上有未就绪的旧本项目 API，正在安全重启。")
            stop_stale_api(args.port)
        else:
            raise LaunchError(
                f"端口 {args.port} 上已有未知服务，未自动接管；请先手动停止后重试。"
            )
    if api_ready(base_url):
        print(f"[xzd] 服务已经运行：{base_url}")
        if args.open_browser:
            open_workspace(base_url)
        return 0
    dotenv = parse_dotenv(ensure_env_file())
    environment = build_host_environment(dotenv)
    repair_python_environment()
    ensure_python_environment(refresh=args.refresh_deps)
    start_dependencies(environment)
    migrate_database(environment)
    return start_api(args, environment)


def command_stop(args: argparse.Namespace) -> int:
    require_docker()
    environment = build_host_environment(parse_dotenv(ROOT / ".env"))
    port = int(getattr(args, "port", 8000))
    if owned_api_groups(port):
        stop_stale_api(port)
    stop_stale_worker()
    result = run_command(
        ["docker", "compose", "stop", *SERVICES],
        env=environment,
        timeout_seconds=30,
    )
    if result.returncode != 0:
        raise LaunchError("停止基础服务失败。")
    print("[xzd] API/Worker 与基础服务已停止，数据卷仍保留。")
    return 0


def command_status(_: argparse.Namespace) -> int:
    require_docker()
    environment = build_host_environment(parse_dotenv(ROOT / ".env"))
    result = run_command(["docker", "compose", "ps", *SERVICES], env=environment)
    if result.returncode != 0:
        raise LaunchError("无法读取基础服务状态。")
    print(
        "[xzd] Web API: "
        + ("ready" if api_ready("http://127.0.0.1:8000") else "not running on :8000")
    )
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    dotenv = parse_dotenv(ROOT / ".env")
    checks = runtime_checks(
        port=args.port,
        environment=build_host_environment(dotenv),
    )
    dotenv = parse_dotenv(ROOT / ".env")
    summary = configuration_summary(dotenv)
    result = print_runtime_checks(checks)
    print("[INFO] Runtime 配置（仅显示是否配置，不显示值）：")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return result


def command_repair(args: argparse.Namespace) -> int:
    return repair_runtime_environment(port=args.port)


def command_preflight(args: argparse.Namespace) -> int:
    if not VENV_PYTHON.is_file():
        raise LaunchError("虚拟环境尚未创建；请先运行 '.\\xzd.ps1 start'。")
    command = [
        str(VENV_PYTHON),
        str(ROOT / "scripts/demo_cli.py"),
        "preflight",
        "--base-url",
        args.base_url,
    ]
    return run_command(
        command, env=build_host_environment(parse_dotenv(ROOT / ".env"))
    ).returncode


def command_index(args: argparse.Namespace) -> int:
    if not (3, 11) <= sys.version_info[:2] < (3, 14):
        raise LaunchError("需要 Python 3.11-3.13；当前 Python 版本不受支持。")
    dotenv = parse_dotenv(ensure_env_file())
    environment = build_host_environment(dotenv)
    ensure_python_environment(refresh=False)
    require_docker()
    command = [
        str(VENV_PYTHON),
        str(ROOT / "scripts/knowledge_base_cli.py"),
        "build",
        "--rag",
    ]
    if args.course:
        command.extend(["--course", args.course])
    if args.text_only:
        command.append("--text")
    print("[xzd] 构建本地知识库索引；模型首次下载可能需要较长时间。")
    result = run_command(command, env=environment)
    if result.returncode != 0:
        raise LaunchError("知识库索引构建失败；请检查课程目录、Qdrant 和上方日志。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="芯智导学统一启动器")
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start", help="准备环境并启动完整本地应用")
    start.add_argument("--port", type=int, default=8000)
    start.add_argument("--reload", action="store_true", help="开发时启用代码热重载")
    start.add_argument(
        "--force-reload",
        action="store_true",
        help="仅重启已识别的本项目 Uvicorn 服务并加载最新代码",
    )
    start.add_argument(
        "--refresh-deps", action="store_true", help="强制刷新 Python 依赖"
    )
    start.add_argument(
        "--open-browser", action="store_true", help="就绪后打开学生工作台"
    )
    start.set_defaults(handler=command_start)
    stop = commands.add_parser("stop", help="停止 API/Worker 与本地基础服务")
    stop.add_argument("--port", type=int, default=8000)
    stop.set_defaults(handler=command_stop)
    commands.add_parser("status", help="显示本地服务状态").set_defaults(
        handler=command_status
    )
    doctor = commands.add_parser("doctor", help="安全检查本机环境和配置")
    doctor.add_argument("--port", type=int, default=8000)
    doctor.set_defaults(handler=command_doctor)
    repair = commands.add_parser(
        "repair",
        help="修复项目自有容器、迁移和单实例 API（不删除数据）",
    )
    repair.add_argument("--port", type=int, default=8000)
    repair.set_defaults(handler=command_repair)
    preflight = commands.add_parser("preflight", help="检查会议演示所需能力")
    preflight.add_argument("--base-url", default="http://127.0.0.1:8000")
    preflight.set_defaults(handler=command_preflight)
    index = commands.add_parser("index", help="为本机课程资料构建 RAG 索引")
    index.add_argument("--course", choices=("CT", "AE", "DE", "SS", "DSP", "COMM"))
    index.add_argument("--text-only", action="store_true")
    index.set_defaults(handler=command_index)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.handler(args))
    except LaunchError as exc:
        print(f"[xzd] 错误：{exc}", file=sys.stderr)
        print(
            "[xzd] 建议：先运行 "
            f"'.\\xzd.ps1 doctor -Port {getattr(args, 'port', 8000)}' "
            "查看脱敏检查结果；可修复项再运行 "
            f"'.\\xzd.ps1 repair -Port {getattr(args, 'port', 8000)}'。",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
