from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, ListItem, ListView, Label, Static

from plexget.filtering import filter_items
from plexget.nodes import Node, PartRef


@dataclass
class Level:
    nodes: list
    filter_text: str = ""
    selected_index: int = 0
    label: str = "/"


class NavState:
    def __init__(self, levels: list[Level]):
        self.levels = levels

    def top(self) -> Level:
        return self.levels[-1]

    def current_nodes(self) -> list:
        return self.top().nodes

    def visible(self) -> list:
        lvl = self.top()
        return filter_items(lvl.nodes, lvl.filter_text, key=lambda n: n.label)

    def selected(self) -> Optional[Node]:
        vis = self.visible()
        if not vis:
            return None
        idx = min(self.top().selected_index, len(vis) - 1)
        return vis[idx]

    def set_filter(self, text: str) -> None:
        self.top().filter_text = text
        self.top().selected_index = 0

    def move(self, delta: int) -> None:
        vis = self.visible()
        if not vis:
            return
        idx = self.top().selected_index + delta
        self.top().selected_index = max(0, min(idx, len(vis) - 1))

    def push(self, nodes: list, label: str = "") -> None:
        if not label:
            sel = self.selected()
            label = sel.label if sel else "/"
        self.levels.append(Level(nodes, "", 0, label))

    def pop(self) -> bool:
        if len(self.levels) <= 1:
            return False
        self.levels.pop()
        return True

    def breadcrumb(self) -> str:
        if len(self.levels) == 1:
            return "/"
        return "/ " + " / ".join(lvl.label for lvl in self.levels[1:])
