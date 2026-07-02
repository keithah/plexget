from __future__ import annotations

import re
from pathlib import Path

from plexget.nodes import PartRef

_ILLEGAL = re.compile(r'[/\\:*?"<>|]')


def sanitize_filename(name: str) -> str:
    cleaned = _ILLEGAL.sub("_", name).strip()
    return cleaned or "download"


def build_dest(out: Path, part: PartRef, mirror: bool) -> Path:
    dest = out
    if mirror:
        for segment in part.rel_dir:
            if segment:
                dest = dest / sanitize_filename(segment)
    return dest / sanitize_filename(part.filename)
