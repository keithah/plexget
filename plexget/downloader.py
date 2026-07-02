from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from plexget.nodes import PartRef

_ILLEGAL = re.compile(r'[/\\:*?"<>|]')


def sanitize_filename(name: str) -> str:
    cleaned = _ILLEGAL.sub("_", name).strip()
    if cleaned in ("", ".", ".."):
        return "download"
    return cleaned


def build_dest(out: Path, part: PartRef, mirror: bool) -> Path:
    dest = out
    if mirror:
        for segment in part.rel_dir:
            if segment:
                dest = dest / sanitize_filename(segment)
    return dest / sanitize_filename(part.filename)


@dataclass
class Progress:
    filename: str
    done: int
    total: int
    speed_bps: float
    index: int
    count: int


@dataclass
class DownloadResult:
    succeeded: list = field(default_factory=list)
    failed: list = field(default_factory=list)


def download_part(
    part: PartRef,
    dest: Path,
    *,
    session,
    on_progress: Optional[Callable[[Progress], None]] = None,
    chunk_size: int = 1 << 20,
    now: Callable[[], float] = time.monotonic,
    index: int = 1,
    count: int = 1,
) -> bool:
    if dest.exists() and part.size and dest.stat().st_size == part.size:
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    start = now()
    done = 0

    with session.get(part.url, stream=True, timeout=30) as resp:
        resp.raise_for_status()
        total = part.size or int(resp.headers.get("content-length", 0))
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                fh.write(chunk)
                done += len(chunk)
                elapsed = max(now() - start, 1e-9)
                if on_progress:
                    on_progress(
                        Progress(part.filename, done, total, done / elapsed, index, count)
                    )

    tmp.replace(dest)
    return True


def run_jobs(
    parts: list[PartRef],
    out: Path,
    *,
    mirror: bool,
    session,
    on_progress: Optional[Callable[[Progress], None]] = None,
    retries: int = 1,
    now: Callable[[], float] = time.monotonic,
) -> DownloadResult:
    result = DownloadResult()
    count = len(parts)
    for index, part in enumerate(parts, start=1):
        dest = build_dest(out, part, mirror)
        attempts = 0
        while True:
            attempts += 1
            try:
                download_part(
                    part, dest, session=session, on_progress=on_progress,
                    now=now, index=index, count=count,
                )
                result.succeeded.append(part)
                break
            except Exception as exc:  # noqa: BLE001 - queue must survive any file error
                if attempts <= retries:
                    continue
                result.failed.append((part, str(exc)))
                break
    return result
