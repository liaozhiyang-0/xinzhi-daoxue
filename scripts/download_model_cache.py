"""Download a public ModelScope model into a local Transformers directory.

This is an operational bootstrap helper for real local RAG models. It uses
parallel HTTP range requests for large files, resumes partial chunks, and only
publishes a completed file after its expected byte count is verified.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_FILES = (
    "config.json",
    "config_sentence_transformers.json",
    "configuration.json",
    "modules.json",
    "model.safetensors",
    "README.md",
    "sentence_bert_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "1_Pooling/config.json",
)


def _url(endpoint: str, repo: str, revision: str, path: str) -> str:
    return (
        f"{endpoint.rstrip('/')}/models/{repo}/resolve/{revision}/"
        f"{urllib.parse.quote(path)}"
    )


def _file_list(endpoint: str, repo: str, revision: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {"Revision": revision, "Recursive": "true"}
    )
    api = (
        f"{endpoint.rstrip('/')}/api/v1/models/{repo}/repo/files?{query}"
    )
    with urllib.request.urlopen(api, timeout=30) as response:
        payload = json.load(response)
    files = payload.get("Data", {}).get("Files", [])
    return [
        {"path": item["Path"], "size": int(item.get("Size", 0))}
        for item in files
        if item.get("Type") == "blob"
    ]


def _download_small(url: str, target: Path, size: int) -> None:
    if target.exists() and target.stat().st_size == size:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url,
                headers={"Range": f"bytes=0-{size - 1}"},
            )
            temporary = target.with_suffix(target.suffix + ".tmp")
            with (
                urllib.request.urlopen(request, timeout=60) as response,
                temporary.open("wb") as output,
            ):
                shutil.copyfileobj(response, output)
            if temporary.stat().st_size != size:
                temporary.unlink(missing_ok=True)
                raise RuntimeError(f"file size mismatch for {target}")
            os.replace(temporary, target)
            return
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1 + attempt)


def _download_range(
    *,
    url: str,
    parts_dir: Path,
    part_index: int,
    start: int,
    end: int,
) -> Path:
    target = parts_dir / f"{part_index:06d}.part"
    expected = end - start + 1
    if target.exists() and target.stat().st_size == expected:
        return target
    temporary = target.with_suffix(".tmp")
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url,
                headers={"Range": f"bytes={start}-{end}"},
            )
            with (
                urllib.request.urlopen(request, timeout=120) as response,
                temporary.open("wb") as output,
            ):
                shutil.copyfileobj(response, output)
            actual_size = temporary.stat().st_size
            if actual_size != expected:
                temporary.unlink(missing_ok=True)
                raise RuntimeError(
                    f"range size mismatch for {url}: "
                    f"expected {expected}, got {actual_size}"
                )
            os.replace(temporary, target)
            return target
        except Exception:
            temporary.unlink(missing_ok=True)
            if attempt == 3:
                raise
            time.sleep(1 + attempt)
    raise RuntimeError(f"unreachable download failure for {url}")


def _download_large(
    *,
    url: str,
    target: Path,
    size: int,
    chunk_size: int,
    workers: int,
) -> None:
    if target.exists() and target.stat().st_size == size:
        return
    parts_dir = target.parent / f".{target.name}.parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    ranges = [
        (index, start, min(size - 1, start + chunk_size - 1))
        for index, start in enumerate(range(0, size, chunk_size))
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                _download_range,
                url=url,
                parts_dir=parts_dir,
                part_index=index,
                start=start,
                end=end,
            )
            for index, start, end in ranges
        ]
        for future in concurrent.futures.as_completed(futures):
            future.result()
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("wb") as output:
        for index, _, _ in ranges:
            output.write((parts_dir / f"{index:06d}.part").read_bytes())
    if temporary.stat().st_size != size:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"final size mismatch for {target}")
    os.replace(temporary, target)
    shutil.rmtree(parts_dir)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="AI-ModelScope/bge-small-zh-v1.5")
    parser.add_argument("--revision", default="master")
    parser.add_argument("--endpoint", default="https://modelscope.cn")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--chunk-mb", type=int, default=1)
    parser.add_argument(
        "--all-files",
        action="store_true",
        help="download every file listed by the public repository API",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    files = _file_list(args.endpoint, args.repo, args.revision)
    known = {item["path"]: item["size"] for item in files}
    selected = (
        [item["path"] for item in files]
        if args.all_files
        else [item for item in DEFAULT_FILES if item in known]
    )
    for relative in selected:
        target = args.output_dir / relative
        url = _url(args.endpoint, args.repo, args.revision, relative)
        size = known[relative]
        print(f"downloading {relative} ({size} bytes)", flush=True)
        if size > args.chunk_mb * 1024 * 1024:
            _download_large(
                url=url,
                target=target,
                size=size,
                chunk_size=args.chunk_mb * 1024 * 1024,
                workers=max(1, args.workers),
            )
        else:
            _download_small(url, target, size)
    print(f"completed {args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
