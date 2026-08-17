"""Repository directory-drift check.

Verifies that the tracked repository layout matches the manifest in
``config/repo_layout.yaml``:

1. every required tracked path exists in the git index;
2. every required disk path exists in the working tree;
3. no forbidden path/suffix is tracked (secrets, caches, local state).

Exits 0 when the layout matches, 1 when drift is detected. Writes a JSON
report (``--report-json``) and a Markdown summary (``--report-md``) so CI can
surface a readable failure.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config" / "repo_layout.yaml"


def tracked_paths(root: Path) -> set[str]:
    """Return all tracked paths (POSIX form) from the git index."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        text=False,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git ls-files failed: {result.stderr.decode(errors='replace').strip()}"
        )
    return {
        raw.decode(errors="replace").replace("\\", "/")
        for raw in result.stdout.split(b"\0")
        if raw
    }


def check_layout(
    root: Path,
    manifest: dict[str, Any],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return (missing_required, forbidden_found) violation lists."""
    missing: list[dict[str, str]] = []
    forbidden: list[dict[str, str]] = []

    tracked = tracked_paths(root)
    tracked_top_level = {path.split("/", 1)[0] for path in tracked}

    required: dict[str, Any] = manifest.get("required_tracked", {})
    for path in required.get("top_level_files", []):
        if path not in tracked_top_level:
            missing.append(
                {"kind": "tracked", "path": path, "detail": "missing from git index"}
            )
    for path in required.get("top_level_directories", []):
        if path not in tracked_top_level:
            missing.append(
                {"kind": "tracked", "path": path, "detail": "missing from git index"}
            )
    for path in required.get("paths", []):
        # git only tracks files, so a required directory matches when any
        # tracked file lives under it.
        if path in tracked or any(p.startswith(f"{path}/") for p in tracked):
            continue
        missing.append(
            {"kind": "tracked", "path": path, "detail": "missing from git index"}
        )

    forbidden_cfg: dict[str, Any] = manifest.get("forbidden_tracked", {})
    forbidden_paths = set(forbidden_cfg.get("paths", []))
    forbidden_suffixes = tuple(forbidden_cfg.get("suffixes", []))
    for path in sorted(tracked):
        top = path.split("/", 1)[0]
        if top in forbidden_paths:
            forbidden.append(
                {
                    "kind": "tracked",
                    "path": path,
                    "detail": "forbidden top-level entry is tracked",
                }
            )
        elif forbidden_suffixes and path.lower().endswith(forbidden_suffixes):
            forbidden.append(
                {
                    "kind": "tracked",
                    "path": path,
                    "detail": "forbidden file suffix is tracked",
                }
            )

    disk_required: dict[str, Any] = manifest.get("required_disk", {})
    for path in disk_required.get("top_level", []):
        if not (root / path).exists():
            missing.append(
                {"kind": "disk", "path": path, "detail": "missing from working tree"}
            )

    return missing, forbidden


def write_report(
    root: Path,
    missing: list[dict[str, str]],
    forbidden: list[dict[str, str]],
    manifest_path: Path,
    report_json: Path | None,
    report_md: Path | None,
) -> None:
    report: dict[str, Any] = {
        "check": "repo_drift",
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest": str(manifest_path),
        "ok": not missing and not forbidden,
        "missing": missing,
        "forbidden": forbidden,
    }
    if report_json is not None:
        report_json.parent.mkdir(parents=True, exist_ok=True)
        report_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if report_md is not None:
        lines = ["# Repository drift check", ""]
        lines.append(f"- generated_at: `{report['generated_at']}`")
        lines.append(f"- manifest: `{manifest_path}`")
        lines.append(f"- result: {'OK' if report['ok'] else 'DRIFT DETECTED'}")
        if missing:
            lines.append("")
            lines.append("## Missing required entries")
            lines.append("")
            lines.append("| kind | path | detail |")
            lines.append("| --- | --- | --- |")
            for item in missing:
                lines.append(
                    f"| {item['kind']} | `{item['path']}` | {item['detail']} |"
                )
        if forbidden:
            lines.append("")
            lines.append("## Forbidden tracked entries")
            lines.append("")
            lines.append("| kind | path | detail |")
            lines.append("| --- | --- | --- |")
            for item in forbidden:
                lines.append(
                    f"| {item['kind']} | `{item['path']}` | {item['detail']} |"
                )
        report_md.parent.mkdir(parents=True, exist_ok=True)
        report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-md", type=Path)
    args = parser.parse_args()

    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    missing, forbidden = check_layout(args.root, manifest)
    write_report(
        args.root,
        missing,
        forbidden,
        args.manifest,
        args.report_json,
        args.report_md,
    )
    if missing or forbidden:
        print(
            f"repo drift detected: {len(missing)} missing, {len(forbidden)} forbidden"
        )
        for item in missing + forbidden:
            print(f"  - [{item['kind']}] {item['path']}: {item['detail']}")
        return 1
    print("repo layout matches manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
