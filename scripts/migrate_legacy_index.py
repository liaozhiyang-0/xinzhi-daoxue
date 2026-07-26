from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="保留旧索引并构建当前真实文本 Embedding 版本"
    )
    value.add_argument(
        "--course",
        action="append",
        choices=("CT", "AE", "DE", "SS", "DSP", "COMM"),
    )
    value.add_argument("--batch-size", type=int)
    value.add_argument("--dry-run", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    command = [
        sys.executable,
        str(ROOT / "scripts" / "knowledge_base_cli.py"),
        "build",
        "--rag",
        "--text",
    ]
    for course in args.course or []:
        command.extend(["--course", course])
    if args.batch_size:
        command.extend(["--batch-size", str(args.batch_size)])
    if args.dry_run:
        command.append("--dry-run")
    print(
        json.dumps(
            {
                "mode": "legacy_to_versioned_real_embedding",
                "legacy_index_deleted": False,
                "command": command,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
