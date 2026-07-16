from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROHIBITED_PATH_PARTS = {".local_inputs", ".local_outputs", "local_storage"}
PROHIBITED_SUFFIXES = (".xingchen.raw.yml", ".xingchen.raw.yaml")
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\bgh[opsu]_[A-Za-z0-9]{20,}\b"),
    "generic_api_token": re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|secret[_-]?key)\b"
        r"\s*[:=]\s*[\"']?(?!change_me|your_|example|not_required|missing)"
        r"[A-Za-z0-9_\-]{16,}"
    ),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        ROOT / item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    ]


def scan(paths: list[Path]) -> list[str]:
    findings: list[str] = []
    for path in paths:
        relative = path.relative_to(ROOT)
        parts = set(relative.parts)
        lowered = relative.as_posix().lower()
        if parts & PROHIBITED_PATH_PARTS or lowered.endswith(PROHIBITED_SUFFIXES):
            findings.append(f"prohibited_path:{relative.as_posix()}")
            continue
        if relative.name == ".env":
            findings.append("tracked_env:.env")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{name}:{relative.as_posix()}")
    return findings


def main() -> int:
    findings = scan(tracked_files())
    if findings:
        print("Sensitive file scan failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Sensitive file scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
