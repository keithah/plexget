from __future__ import annotations

from typing import Callable, TypeVar

T = TypeVar("T")


def _is_subsequence(needle: str, haystack: str) -> bool:
    it = iter(haystack)
    return all(ch in it for ch in needle)


def filter_items(items: list[T], query: str, key: Callable[[T], str] = str) -> list[T]:
    q = query.strip().lower()
    if not q:
        return list(items)
    return [item for item in items if _is_subsequence(q, key(item).lower())]
