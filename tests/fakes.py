from __future__ import annotations

from plexget.nodes import PartRef


class FakeNode:
    def __init__(self, label, kind, is_leaf, children=(), parts=()):
        self.label = label
        self.kind = kind
        self.is_leaf = is_leaf
        self._children = list(children)
        self._parts = list(parts)

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


def part(filename, size, rel_dir=()):
    return PartRef(
        url=f"http://server/{filename}",
        filename=filename,
        size=size,
        rel_dir=tuple(rel_dir),
    )
