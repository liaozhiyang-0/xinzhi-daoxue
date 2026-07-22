#!/usr/bin/env python3
"""Generate the deterministic, Git-scoped repository file catalog."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Final

import yaml

PROJECT_ROOT: Final = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT: Final = PROJECT_ROOT / "docs" / "repository_file_catalog.md"

ROOT_ROLES: Final[dict[str, str]] = {
    ".dockerignore": "Docker 构建上下文排除规则。",
    ".env.example": "无密钥的环境变量模板；本机真实值写入被忽略的 `.env`。",
    ".gitattributes": "Git 文本属性与跨平台换行规则。",
    ".gitignore": "本地密钥、教材、索引、缓存、上传物与运行数据排除规则。",
    "AGENTS.md": "仓库工程、安全、验证和发布约束。",
    "README.md": "项目入口说明、能力边界、配置和启动指引。",
    "docker-compose.yml": "PostgreSQL、Redis、MinIO、Qdrant 与 API 的本地编排。",
    "pytest.ini": "根目录 Pytest 发现与运行配置。",
    "ruff.toml": "Ruff 静态检查和格式规则。",
    "xzd.cmd": "Windows CMD 统一启动器入口。",
    "xzd.ps1": "Windows PowerShell 统一启动器入口。",
    "xzd.sh": "Linux/macOS 统一启动器入口。",
    "打开芯智导学.cmd": "Windows 双击启动并打开学生工作台的便捷入口。",
}

TOP_LEVEL_ROLES: Final[dict[str, str]] = {
    ".github": "GitHub Actions 持续集成。",
    "agent_configs": "Agent 注册表、冻结工作流与课程包配置。",
    "apps": "FastAPI 主应用、静态前端和 Worker 边界。",
    "archive_legacy": "退出活动架构的历史资料与代码隔离区。",
    "config": "跨运行环境的基础配置。",
    "docs": "现行架构、运行、评测、知识库与验收文档。",
    "evaluation": "可复现评测数据集、基线、模式与报告模板。",
    "knowledge_config": "课程资料元数据、OCR 覆盖和分块策略。",
    "local_knowledge": "可提交的小型示例知识与目录占位；非教材原文。",
    "scripts": "启动、诊断、迁移、索引、评测和发布辅助脚本。",
    "tests": "仓库级配置和静态边界测试。",
}

TEXT_SUFFIXES: Final = {
    ".cmd",
    ".css",
    ".dockerignore",
    ".env",
    ".example",
    ".gitattributes",
    ".gitignore",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".mako",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".svg",
    ".toml",
    ".yaml",
    ".yml",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Catalog path; defaults to docs/repository_file_catalog.md",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when the committed catalog differs from regeneration.",
    )
    return parser.parse_args()


def git_publishable_files(output: Path) -> list[Path]:
    command = [
        "git",
        "-c",
        "core.quotePath=false",
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    relative_output = output.resolve().relative_to(PROJECT_ROOT).as_posix()
    names = {
        name
        for item in completed.stdout.split(b"\0")
        if item
        for name in [item.decode("utf-8")]
        if (PROJECT_ROOT / name).is_file()
    }
    names.add(relative_output)
    return [PROJECT_ROOT / name for name in sorted(names, key=str.casefold)]


def read_text(path: Path) -> str:
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in ROOT_ROLES:
        return ""
    try:
        return path.read_text(encoding="utf-8")[:131_072]
    except (OSError, UnicodeDecodeError):
        return ""


def clean(value: str, limit: int = 150) -> str:
    normalized = re.sub(r"\s+", " ", value).strip().strip("#")
    normalized = normalized.replace("|", "\\|").replace("`", "'")
    if len(normalized) > limit:
        return normalized[: limit - 1].rstrip() + "…"
    return normalized


def markdown_title(text: str) -> str | None:
    for line in text.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return clean(match.group(1))
    return None


def python_description(path: Path, text: str) -> str:
    relative = path.relative_to(PROJECT_ROOT).as_posix()
    if path.name.startswith("test_"):
        subject = path.stem.removeprefix("test_").replace("_", " ")
        return f"回归测试：{subject}。"
    if "/alembic/versions/" in f"/{relative}":
        return f"增量数据库迁移：{path.stem.replace('_', ' ')}。"
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return "Python 模块（目录清单生成时无法解析语法，需人工复核）。"
    docstring = ast.get_docstring(tree)
    if docstring:
        first_sentence = re.split(r"(?<=[。.!?])\s+", docstring.strip(), maxsplit=1)[0]
        return clean(first_sentence)
    definitions = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if definitions:
        preview = "、".join(definitions[:5])
        suffix = " 等" if len(definitions) > 5 else ""
        return f"Python 模块；定义 {preview}{suffix}。"
    if path.name == "__init__.py":
        return "Python 包边界与对外导出。"
    return "Python 配置或执行模块。"


def structured_description(path: Path, text: str) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError):
        return "结构化配置或数据文件（内容需由对应加载器校验）。"
    if isinstance(data, dict):
        keys = "、".join(clean(str(key), 35) for key in list(data)[:6])
        return f"结构化配置或数据；顶层字段：{keys}。"
    if isinstance(data, list):
        return f"结构化数据集；包含 {len(data)} 个顶层条目。"
    return "结构化配置或数据文件。"


def describe(path: Path, output: Path) -> str:
    relative = path.relative_to(PROJECT_ROOT).as_posix()
    if path.resolve() == output.resolve():
        return "本脚本生成的 Git 范围逐文件清单。"
    if relative in ROOT_ROLES:
        return ROOT_ROLES[relative]
    if path.name == ".gitkeep":
        return "保留空目录结构的占位文件。"

    text = read_text(path)
    suffix = path.suffix.lower()
    if suffix == ".py":
        description = python_description(path, text)
    elif suffix == ".md":
        title = markdown_title(text)
        description = f"文档：{title}。" if title else "Markdown 说明文档。"
    elif suffix in {".yaml", ".yml", ".json"}:
        description = structured_description(path, text)
    elif suffix == ".html":
        title_match = re.search(
            r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL
        )
        title = clean(title_match.group(1)) if title_match else path.stem
        description = f"静态前端页面：{title}。"
    elif suffix == ".css":
        description = f"静态前端样式：{path.stem.replace('_', ' ')}。"
    elif suffix == ".js":
        description = f"静态前端交互逻辑：{path.stem.replace('_', ' ')}。"
    elif suffix in {".ps1", ".sh", ".cmd"}:
        description = f"跨平台运行脚本：{path.stem.replace('_', ' ')}。"
    elif suffix in {".toml", ".ini"}:
        description = "项目、工具或运行时配置。"
    elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
        description = "界面验收、测试或文档使用的图像资产。"
    elif suffix in {".woff", ".woff2", ".ttf"}:
        description = "本地前端字体资产，避免运行时依赖外部 CDN。"
    elif suffix == ".mako":
        description = "Alembic 数据库迁移文件模板。"
    else:
        description = "仓库配置、资产或占位文件。"

    if relative.startswith("archive_legacy/"):
        return f"历史隔离：{description} 不参与活动运行链。"
    return description


def render(files: list[Path], output: Path) -> str:
    relative_paths = [path.relative_to(PROJECT_ROOT) for path in files]
    top_counts = Counter(path.parts[0] for path in relative_paths)
    extension_counts = Counter(
        path.suffix.lower() or "[无扩展名]" for path in relative_paths
    )
    directories: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        parent = path.relative_to(PROJECT_ROOT).parent.as_posix()
        directories[parent].append(path)

    active_count = sum(path.parts[0] != "archive_legacy" for path in relative_paths)
    archive_count = sum(path.parts[0] == "archive_legacy" for path in relative_paths)

    lines = [
        "# 仓库逐文件目录（自动生成）",
        "",
        (
            "> 本文档只覆盖 `git ls-files --cached --others --exclude-standard` "
            "可见的可发布文件，"
        ),
        (
            "> 因而不会读取或列出 `.env`、教材原文、向量索引、上传文件、"
            "数据库、模型缓存和测试临时文件。"
        ),
        (
            "> 文件职责由路径、模块文档字符串、Markdown 标题和结构化文件"
            "顶层字段确定；它是导航清单，不替代源码。"
        ),
        "",
        f"- 可发布文件总数：**{len(files)}**",
        f"- 活动文件：**{active_count}**",
        f"- 历史隔离文件：**{archive_count}**",
        "- 重新生成：`python scripts/generate_repository_catalog.py`",
        "- 漂移检查：`python scripts/generate_repository_catalog.py --check`",
        "",
        "## 顶层范围",
        "",
        "| 路径 | 文件数 | 职责 |",
        "|---|---:|---|",
    ]
    sorted_top_counts = sorted(
        top_counts.items(), key=lambda item: item[0].casefold()
    )
    for name, count in sorted_top_counts:
        role = TOP_LEVEL_ROLES.get(
            name, ROOT_ROLES.get(name, "仓库根文件或项目组成部分。")
        )
        lines.append(f"| `{name}` | {count} | {role} |")

    lines.extend(
        [
            "",
            "## 文件类型统计",
            "",
            "| 扩展名 | 数量 |",
            "|---|---:|",
        ]
    )
    for extension, count in sorted(
        extension_counts.items(), key=lambda item: (-item[1], item[0])
    ):
        lines.append(f"| `{extension}` | {count} |")

    lines.extend(["", "## 逐目录文件清单", ""])
    for directory in sorted(directories, key=str.casefold):
        heading = "仓库根目录" if directory == "." else directory
        lines.extend(
            [
                f"### `{heading}`",
                "",
                "| 文件 | 状态 | 功能 |",
                "|---|---|---|",
            ]
        )
        for path in sorted(
            directories[directory],
            key=lambda item: item.name.casefold(),
        ):
            relative = path.relative_to(PROJECT_ROOT).as_posix()
            status = "历史隔离" if relative.startswith("archive_legacy/") else "活动"
            lines.append(
                f"| `{path.name}` | {status} | {describe(path, output)} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    output = args.output
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    output = output.resolve()
    try:
        output.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise SystemExit("--output must remain inside the repository") from exc

    content = render(git_publishable_files(output), output)
    if args.check:
        current = output.read_text(encoding="utf-8") if output.exists() else ""
        if current != content:
            print(f"repository catalog is stale: {output.relative_to(PROJECT_ROOT)}")
            return 1
        print(f"repository catalog is current: {output.relative_to(PROJECT_ROOT)}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8", newline="\n")
    print(f"generated {output.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
