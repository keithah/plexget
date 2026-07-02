"""Fake in-memory library + simulated downloads for ``plexget --demo``.

Lets anyone try the TUI (and lets us record the README demo GIF) without a Plex
server or exposing a real library. No network, no files written.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from plexget.downloader import DownloadResult, Progress
from plexget.nodes import PartRef

GB = 1024 ** 3
MB = 1024 ** 2


class DemoNode:
    """A Node-protocol node backed by static in-memory data."""

    def __init__(self, label, kind, is_leaf, children=None, parts=None):
        self.label = label
        self.kind = kind
        self.is_leaf = is_leaf
        self._children = list(children or [])
        self._parts = list(parts or [])

    def children(self):
        return list(self._children)

    def parts(self):
        return list(self._parts)

    def enumerate_parts(self):
        if self.is_leaf:
            return list(self._parts)
        out = []
        for child in self._children:
            out.extend(child.enumerate_parts())
        return out


def _episode(show: str, season: int, ep: int, size: int) -> DemoNode:
    filename = f"{show} - S{season:02d}E{ep:02d}.mkv"
    part = PartRef(
        url=f"demo://{filename}",
        filename=filename,
        size=size,
        rel_dir=(show, f"Season {season:02d}"),
    )
    return DemoNode(f"S{season:02d}E{ep:02d}", "episode", True, parts=[part])


def _season(show: str, season: int, episodes: int) -> DemoNode:
    eps = [
        _episode(show, season, ep, size=(1400 + (ep * 137) % 900) * MB)
        for ep in range(1, episodes + 1)
    ]
    return DemoNode(f"Season {season:02d}", "season", False, children=eps)


def _show(title: str, seasons: int, episodes: int) -> DemoNode:
    return DemoNode(
        title,
        "show",
        False,
        children=[_season(title, s, episodes) for s in range(1, seasons + 1)],
    )


def _movie(title: str, size: int) -> DemoNode:
    filename = f"{title} (2024) Bluray-1080p.mkv"
    part = PartRef(url=f"demo://{filename}", filename=filename, size=size, rel_dir=(title,))
    return DemoNode(title, "movie", True, parts=[part])


def demo_nodes() -> list[DemoNode]:
    """Top-level fake libraries: TV Shows and Movies (all fictional)."""
    tv = DemoNode(
        "TV Shows",
        "library",
        False,
        children=[
            _show("Aurora Station", seasons=2, episodes=6),
            _show("The Cartographer", seasons=1, episodes=8),
            _show("Midnight Diner Club", seasons=3, episodes=6),
            _show("Quantum Beach", seasons=1, episodes=10),
        ],
    )
    movies = DemoNode(
        "Movies",
        "library",
        False,
        children=[
            _movie("The Last Lighthouse", size=int(11.4 * GB)),
            _movie("Neon Harbor", size=int(8.9 * GB)),
            _movie("Paper Kingdoms", size=int(14.2 * GB)),
            _movie("Sundown Express", size=int(9.7 * GB)),
        ],
    )
    return [tv, movies]


def demo_runner(
    parts: list[PartRef],
    on_progress: Optional[Callable[[Progress], None]] = None,
    *,
    sleep: Callable[[float], None] = time.sleep,
    steps: int = 12,
) -> DownloadResult:
    """Simulate a download: emit realistic progress, write nothing."""
    result = DownloadResult()
    speed_bps = 48.0 * MB  # a believable ~48 MB/s
    count = len(parts)
    for index, part in enumerate(parts, start=1):
        for step in range(1, steps + 1):
            done = int(part.size * step / steps)
            if on_progress:
                on_progress(Progress(part.filename, done, part.size, speed_bps, index, count))
            sleep(0.08)
        result.succeeded.append(part)
    return result
