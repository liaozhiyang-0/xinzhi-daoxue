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
    "XINGCHEN_API_KEY",
    "XINGCHEN_API_SECRET",
    "XINGCHEN_SOLVER_CT_FLOW_ID",
    "XINGCHEN_KNOWLEDGE_QA_FLOW_ID",
)
COMPOSE_PROJECT_NAME = "xinzhi-daoxue"
CONTAINER_NAMES = ("xzd-postgres", "xzd-redis", "xzd-minio", "xzd-qdrant")
FRONTEND_BUILD_ID = "20260810-role-aware-scenarios-v1"
RUNTIME_DEVELOPMENT_LAUNCH_MODES = {
    "ACADEMIC_PROBLEM_SOLVER": "default",
    "GENERAL_QUESTION_V1": "default",
    "LEARN_01_LOCAL_RETRIEVAL_V1": "default",
    "TEACH_01_LESSON_PREP_V1": "default",
    "TEACH_02_ASSIGNMENT_REVIEW_V1": "default",
    "RESEARCH_01_ACADEMIC_SEARCH_V1": "default",
    "RESEARCH_02_ACADEMIC_WRITING_V1": "default",
}


class LaunchError(RuntimeError):
    """A safe, user-facing launcher failure."""


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


def enable_runtime_development_profile(
    environment: dict[str, str],
) -> dict[str, str]:
    """Return an explicit local Runtime profile for the student entry paths.

    The profile enables every non-Xingchen business Runtime with a durable
    plan, including bounded external-research retrieval. It is a local
    development execution aid, not a production promotion: production keeps
    the normal semantic-evidence release gate.
    """

    app_env = environment.get("APP_ENV", "development").strip().lower()
    if app_env not in {"development", "test"}:
        raise LaunchError("--runtime-dev is only available in development or test")
    configured_modes = environment.get("AGENT_RUNTIME_LAUNCH_MODES", "").strip()
    if configured_modes:
        raise LaunchError(
            "--runtime-dev requires AGENT_RUNTIME_LAUNCH_MODES to be empty; "
            "configure production/canary launch modes explicitly instead"
        )
    runtime_environment = dict(environment)
    runtime_environment.update(
        {
            "AGENT_RUNTIME_SOLVER_ENABLED": "true",
            "AGENT_RUNTIME_GENERAL_ENABLED": "true",
            "AGENT_RUNTIME_KNOWLEDGE_QA_ENABLED": "true",
            "AGENT_RUNTIME_TEACHING_ENABLED": "true",
            "AGENT_RUNTIME_ACADEMIC_WRITING_ENABLED": "true",
            "AGENT_RUNTIME_EXTERNAL_RESEARCH_ENABLED": "true",
            "AGENT_RUNTIME_LAUNCH_MODES": ",".join(
                f"{agent_id}={mode}"
                for agent_id, mode in RUNTIME_DEVELOPMENT_LAUNCH_MODES.items()
            ),
            # This profile is a local development launch, never a release
            # promotion. Production remains fail-closed on semantic evidence.
            "AGENT_RUNTIME_RELEASE_GATE_REQUIRED": "false",
            "AGENT_RUNTIME_PLAN_PROPOSALS_ENABLED": "true",
        }
    )
    return runtime_environment


def configuration_summary(dotenv: dict[str, str]) -> dict[str, object]:
    return {
        "env_file": "configured" if (ROOT / ".env").is_file() else "missing",
        "xingchen_enabled": dotenv.get("XINGCHEN_ENABLED", "false").lower() == "true",
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
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        capture_output=capture,
        encoding="utf-8",
        errors="replace",
    )


def require_docker() -> None:
    if shutil.which("docker") is None:
        raise LaunchError("未找到 Docker。请先安装并启动 Docker Desktop。")
    if not docker_engine_ready():
        raise LaunchError("Docker Desktop 尚未运行。请启动 Docker Desktop 后重试。")


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
    require_docker()
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
    try:
        with urlopen(f"{base_url}/api/v1/health", timeout=2) as response:  # noqa: S310
            return cast(int, response.getcode()) == 200
    except (URLError, TimeoutError, OSError):
        return False


def frontend_build_ready(base_url: str) -> bool:
    """Return whether the running service serves the current frontend build."""

    try:
        with urlopen(f"{base_url}/workspace", timeout=2) as response:  # noqa: S310
            html = response.read().decode("utf-8", errors="replace")
        return (
            f"ui-core.js?v={FRONTEND_BUILD_ID}" in html
            and f"workspace.js?v={FRONTEND_BUILD_ID}" in html
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


def stop_stale_api(port: int) -> None:
    """Stop only an old Uvicorn process belonging to this application."""

    candidates = []
    for pid in _listening_pids(port):
        command_line = _process_command_line(pid).lower()
        if "uvicorn" in command_line and "app.main:app" in command_line:
            candidates.append(pid)
    if not candidates:
        raise LaunchError(
            f"端口 {port} 上运行的是未知服务，未自动终止；请先手动停止后重试。"
        )
    for pid in candidates:
        command = (
            ["taskkill", "/PID", str(pid), "/T", "/F"]
            if os.name == "nt"
            else ["kill", str(pid)]
        )
        result = run_command(command, capture=True)
        if result.returncode != 0:
            raise LaunchError(f"旧 Web 进程 {pid} 停止失败，请手动重启。")
    deadline = time.time() + 10
    while time.time() < deadline and owned_api_pids(port):
        time.sleep(0.25)
    remaining = owned_api_pids(port)
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
        while time.time() < deadline and owned_api_pids(port):
            time.sleep(0.25)
    remaining = owned_api_pids(port)
    if remaining:
        raise LaunchError(
            f"旧 Web 进程仍未退出（PID {','.join(map(str, remaining))}），请手动重启。"
        )


def owned_api_pids(port: int) -> list[int]:
    """Return only Uvicorn processes that belong to this application."""

    owned: list[int] = []
    for pid in _listening_pids(port):
        command_line = _process_command_line(pid).lower()
        if "uvicorn" in command_line and "app.main:app" in command_line:
            owned.append(pid)
    return owned


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
    process = subprocess.Popen(command, cwd=ROOT, env=environment)  # noqa: S603
    try:
        for _ in range(90):
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
        if args.with_cloud:
            result = run_command(
                [
                    str(VENV_PYTHON),
                    str(ROOT / "scripts/demo_cli.py"),
                    "preflight",
                    "--base-url",
                    base_url,
                    "--with-cloud",
                ],
                env=environment,
            )
            if result.returncode != 0:
                print("[xzd] 云端 Preflight 存在失败项；Web 仍保持运行。")
        return int(process.wait())
    except KeyboardInterrupt:
        print("\n[xzd] 正在停止 Web...")
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def command_start(args: argparse.Namespace) -> int:
    if not (3, 11) <= sys.version_info[:2] < (3, 14):
        raise LaunchError("需要 Python 3.11-3.13；当前 Python 版本不受支持。")
    base_url = f"http://127.0.0.1:{args.port}"
    running_pids = owned_api_pids(args.port)
    runtime_dev = bool(getattr(args, "runtime_dev", False))
    if getattr(args, "force_reload", False) and api_ready(base_url):
        if not running_pids:
            raise LaunchError(
                f"端口 {args.port} 上的服务不是本项目 Uvicorn，未自动终止"
            )
        print("[xzd] 按请求强制重载本项目 Web 服务")
        stop_stale_api(args.port)
        running_pids = []
    if api_ready(base_url):
        if runtime_dev and not getattr(args, "force_reload", False):
            raise LaunchError(
                "--runtime-dev needs --force-reload when the local API is "
                "already running"
            )
        if len(running_pids) == 0:
            raise LaunchError(
                f"端口 {args.port} 上运行的是未知服务，未自动复用；请先手动停止后重试。"
            )
        if not frontend_build_ready(base_url) or len(running_pids) > 1:
            reason = "重复 Web 进程" if len(running_pids) > 1 else "旧版 Web 服务"
            print(f"[xzd] 检测到{reason}，正在重启以加载最新代码和前端。")
            stop_stale_api(args.port)
    if api_ready(base_url):
        print(f"[xzd] 服务已经运行：{base_url}")
        if args.open_browser:
            open_workspace(base_url)
        return 0
    dotenv = parse_dotenv(ensure_env_file())
    environment = build_host_environment(dotenv)
    if runtime_dev:
        environment = enable_runtime_development_profile(environment)
    ensure_python_environment(refresh=args.refresh_deps)
    start_dependencies(environment)
    migrate_database(environment)
    return start_api(args, environment)


def command_stop(_: argparse.Namespace) -> int:
    require_docker()
    environment = build_host_environment(parse_dotenv(ROOT / ".env"))
    result = run_command(["docker", "compose", "stop", *SERVICES], env=environment)
    if result.returncode != 0:
        raise LaunchError("停止基础服务失败。")
    print("[xzd] 基础服务已停止，数据卷仍保留。")
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


def command_doctor(_: argparse.Namespace) -> int:
    checks: list[tuple[str, bool, str]] = []
    version_ok = (3, 11) <= sys.version_info[:2] < (3, 14)
    checks.append(("Python 3.11-3.13", version_ok, sys.version.split()[0]))
    checks.append(
        (
            ".env",
            (ROOT / ".env").is_file(),
            "存在" if (ROOT / ".env").is_file() else "首次 start 自动创建",
        )
    )
    checks.append(
        (
            ".env 未被 Git 跟踪",
            not bool(
                run_command(["git", "ls-files", ".env"], capture=True).stdout.strip()
            ),
            "安全",
        )
    )
    docker_cli = shutil.which("docker") is not None
    checks.append(("Docker CLI", docker_cli, "已安装" if docker_cli else "未安装"))
    docker_ready = docker_cli and docker_engine_ready()
    checks.append(
        ("Docker Desktop", docker_ready, "运行中" if docker_ready else "未运行")
    )
    dotenv = parse_dotenv(ROOT / ".env")
    summary = configuration_summary(dotenv)
    print("芯智导学本地环境检查")
    for name, passed, detail in checks:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    print("[INFO] 云端配置（仅显示是否配置，不显示值）：")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    failed = sum(not passed for _, passed, _ in checks)
    print(f"结果：{len(checks) - failed}/{len(checks)} 通过")
    return 1 if failed else 0


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
    if args.with_cloud:
        command.append("--with-cloud")
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
        "--with-cloud", action="store_true", help="启动后执行一次真实云端检查"
    )
    start.add_argument(
        "--open-browser", action="store_true", help="就绪后打开学生工作台"
    )
    start.add_argument(
        "--runtime-dev",
        action="store_true",
        help="development/test：以 Runtime 默认接管本地通用问答与知识问答",
    )
    start.set_defaults(handler=command_start)
    commands.add_parser("stop", help="停止本地基础服务").set_defaults(
        handler=command_stop
    )
    commands.add_parser("status", help="显示本地服务状态").set_defaults(
        handler=command_status
    )
    commands.add_parser("doctor", help="安全检查本机环境和配置").set_defaults(
        handler=command_doctor
    )
    preflight = commands.add_parser("preflight", help="检查会议演示所需能力")
    preflight.add_argument("--base-url", default="http://127.0.0.1:8000")
    preflight.add_argument("--with-cloud", action="store_true")
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
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
