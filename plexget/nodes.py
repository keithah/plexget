from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PartRef:
    """A single downloadable file belonging to a media item."""

    url: str
    filename: str
    size: int
    rel_dir: tuple[str, ...] = ()


@runtime_checkable
class Node(Protocol):
    label: str
    kind: str  # server | library | show | season | episode | movie
    is_leaf: bool

    def children(self) -> list["Node"]:
        """Child nodes one level down (folders only)."""

    def parts(self) -> list[PartRef]:
        """Downloadable files for this node (leaves only)."""

    def enumerate_parts(self) -> list[PartRef]:
        """All downloadable files at/under this node."""
