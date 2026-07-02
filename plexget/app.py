from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
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


def _summarize(parts: list[PartRef]) -> str:
    total = sum(p.size for p in parts)
    gb = total / (1024 ** 3)
    return f"Download {len(parts)} file(s), {gb:.2f} GB?"


class ConfirmScreen(ModalScreen):
    """Yes/no confirmation for a whole-folder download."""

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("enter", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "No"),
    ]

    def __init__(self, message: str):
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        yield Vertical(Label(self._message), Label("[y] download   [n] cancel"))

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class PlexGetApp(App):
    CSS = "ListView { height: 1fr; } #status { height: auto; }"
    BINDINGS = [
        Binding("left", "back", "Back"),
        Binding("right", "action", "Download folder"),
        Binding("enter", "select", "Open/Download"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, nodes, download_runner: Callable[[list], None]):
        super().__init__()
        self.nav = NavState([Level(list(nodes), "", 0)])
        self._download_runner = download_runner

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self.nav.breadcrumb(), id="crumb")
        yield ListView(id="list")
        yield Input(placeholder="type to filter", id="filter")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()
        self.query_one("#list", ListView).focus()

    def _refresh(self) -> None:
        lv = self.query_one("#list", ListView)
        lv.clear()
        for node in self.nav.visible():
            marker = "/" if not node.is_leaf else ""
            lv.append(ListItem(Label(f"{node.label}{marker}")))
        lv.index = self.nav.top().selected_index
        self.query_one("#crumb", Static).update(self.nav.breadcrumb())

    def on_input_changed(self, event: Input.Changed) -> None:
        self.nav.set_filter(event.value)
        self._refresh()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # ListView consumes its own "enter" binding (select_cursor) before it
        # reaches the App-level binding, so drive selection off this message
        # instead when focus is on the list.
        self.action_select()

    def action_back(self) -> None:
        if self.nav.pop():
            self.query_one("#filter", Input).value = self.nav.top().filter_text
            self._refresh()

    def action_select(self) -> None:
        node = self.nav.selected()
        if node is None:
            return
        if node.is_leaf:
            self._start(node.parts())
        else:
            self.nav.push(node.children(), label=node.label)
            self.query_one("#filter", Input).value = ""
            self._refresh()

    def action_action(self) -> None:
        node = self.nav.selected()
        if node is None:
            return
        parts = node.enumerate_parts()
        if not parts:
            return

        def on_result(confirmed: bool) -> None:
            if confirmed:
                self._start(parts)

        self.push_screen(ConfirmScreen(_summarize(parts)), on_result)

    def _start(self, parts: list[PartRef]) -> None:
        self.query_one("#status", Static).update(f"Queued {len(parts)} file(s)")
        self._download_runner(parts)
