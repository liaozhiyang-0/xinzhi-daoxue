from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "local_artifact_retention.yaml"


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    name: str
    relative_path: str
    max_age_days: int
    keep_latest_runs: int = 0


def load_policies(path: Path = POLICY_PATH) -> tuple[RetentionPolicy, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    policies: list[RetentionPolicy] = []
    for name, value in raw.items():
        if not isinstance(value, dict):
            raise ValueError(f"retention policy must be a mapping: {name}")
        relative_path = str(value.get("path", "")).strip()
        max_age_days = int(value.get("max_age_days", 30))
        keep_latest_runs = int(value.get("keep_latest_runs", 0))
        if not relative_path or max_age_days < 1 or keep_latest_runs < 0:
            raise ValueError(f"invalid retention policy: {name}")
        policies.append(
            RetentionPolicy(
                name=name,
                relative_path=relative_path,
                max_age_days=max_age_days,
                keep_latest_runs=keep_latest_runs,
            )
        )
    return tuple(policies)


def _protected_latest_runs(root: Path, count: int) -> set[Path]:
    if count <= 0:
        return set()
    runs = sorted(
        (path for path in root.iterdir() if path.is_dir() and not path.is_symlink()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return {
        child
        for run in runs[:count]
        for child in run.rglob("*")
        if child.is_file() and not child.is_symlink()
    }


def candidates(
    policy: RetentionPolicy,
    *,
    now: datetime | None = None,
) -> list[Path]:
    root = (ROOT / policy.relative_path).resolve()
    if not root.is_dir() or root == ROOT or ROOT not in root.parents:
        raise ValueError(f"retention path is not a project child directory: {root}")
    current = now or datetime.now().astimezone()
    cutoff = current - timedelta(days=policy.max_age_days)
    protected = _protected_latest_runs(root, policy.keep_latest_runs)
    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink() or path in protected:
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
        if modified < cutoff:
            result.append(path)
    return sorted(result)


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report or remove expired local evaluation/runtime caches."
    )
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="remove listed files; without this flag the command is dry-run",
    )
    args = parser.parse_args(argv)
    policies = load_policies(args.policy.resolve())
    total = 0
    for policy in policies:
        paths = candidates(policy)
        bytes_total = sum(_size(path) for path in paths)
        total += bytes_total
        print(
            f"{policy.name}: {len(paths)} files, "
            f"{bytes_total / 1024 / 1024:.1f} MiB "
            f"(older than {policy.max_age_days} days)"
        )
        if args.apply:
            for path in paths:
                path.unlink()
    action = "removed" if args.apply else "eligible"
    print(f"{action}: {total / 1024 / 1024:.1f} MiB")
    if not args.apply:
        print("dry-run only; pass --apply after reviewing the list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
