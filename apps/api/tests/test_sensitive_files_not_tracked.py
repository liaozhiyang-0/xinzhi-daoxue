import subprocess
import sys
from pathlib import Path


def test_sensitive_file_scan_passes() -> None:
    root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [sys.executable, "scripts/check_sensitive_files.py"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_local_input_directory_is_not_tracked() -> None:
    root = Path(__file__).resolve().parents[3]
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    assert ".local_inputs/" not in tracked


def test_local_textbook_directories_are_ignored() -> None:
    root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [
            "git",
            "-c",
            "core.quotePath=false",
            "check-ignore",
            "电路理论/sample.md",
            "模电/sample.md",
            "数电/sample.md",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    ignored = set(result.stdout.splitlines())
    assert ignored == {"电路理论/sample.md", "模电/sample.md", "数电/sample.md"}
