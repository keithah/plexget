from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, ListItem, ListView, Label, Static

from plexget.downloader import DownloadResult, Progress
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


# Runner signature: run(parts, on_progress=None) -> DownloadResult
DownloadRunner = Callable[..., DownloadResult]


class PlexGetApp(App):
    CSS = "ListView { height: 1fr; } #status, #progress { height: auto; }"
    BINDINGS = [
        Binding("left", "back", "Back"),
        Binding("right", "action", "Download folder"),
        Binding("enter", "select", "Open/Download"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, nodes, download_runner: DownloadRunner):
        super().__init__()
        self.nav = NavState([Level(list(nodes), "", 0)])
        self._download_runner = download_runner
        # Guard 1: at most one download in flight (a cancelled worker's blocking
        # session.get()/segment pool keeps running, so we must not start a second).
        self._downloading: bool = False
        # Guard 2: generation token so a superseded nav worker's UI callback
        # (fired after the user navigated away) is dropped.
        self._nav_gen: int = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self.nav.breadcrumb(), id="crumb")
        yield ListView(id="list")
        yield Input(placeholder="type to filter", id="filter")
        yield Static("", id="progress")
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

    # --- selection / filter syncing -------------------------------------

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        # ListView owns up/down navigation natively; mirror its highlight into
        # NavState so nav.selected() tracks the visible cursor.
        if event.list_view.index is not None:
            self.nav.top().selected_index = event.list_view.index

    def on_input_changed(self, event: Input.Changed) -> None:
        self.nav.set_filter(event.value)
        self._refresh()

    def on_key(self, event) -> None:
        # Type-to-filter: the ListView keeps focus, so printable keys that it
        # does not consume bubble up here. Build the filter string from them.
        # Navigation keys (arrows/enter) are not printable and are ignored; the
        # 'q' quit binding is left alone. This handler does not run while the
        # ConfirmScreen modal is active (guarded below) so y/n stay modal keys.
        if isinstance(self.screen, ConfirmScreen):
            return
        if event.key == "backspace":
            current = self.nav.top().filter_text
            if current:
                self._apply_filter(current[:-1])
            event.stop()
            return
        char = event.character
        if char is not None and len(char) == 1 and char.isprintable():
            if event.key == "q":  # reserved for the quit binding
                return
            self._apply_filter(self.nav.top().filter_text + char)
            event.stop()

    def _apply_filter(self, text: str) -> None:
        self.nav.set_filter(text)
        inp = self.query_one("#filter", Input)
        with self.prevent(Input.Changed):
            inp.value = text
        self._refresh()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # ListView consumes its own "enter" binding (select_cursor) before it
        # reaches the App-level binding, so drive selection off this message.
        # Sync selected_index from the live cursor so Enter targets the
        # highlighted row even if the Highlighted message has not settled yet.
        if event.list_view.index is not None:
            self.nav.top().selected_index = event.list_view.index
        self.action_select()

    # --- actions --------------------------------------------------------

    def action_back(self) -> None:
        if self.nav.pop():
            # Drop any in-flight descend for the level we just left.
            self._nav_gen += 1
            with self.prevent(Input.Changed):
                self.query_one("#filter", Input).value = self.nav.top().filter_text
            self._refresh()

    def action_select(self) -> None:
        node = self.nav.selected()
        if node is None:
            return
        # children()/parts() may hit the network; run off the UI thread.
        self._nav_gen += 1
        self._open_node(node, self._nav_gen)

    def action_action(self) -> None:
        node = self.nav.selected()
        if node is None:
            return
        # enumerate_parts() can walk an entire show/library over the network;
        # compute it off the UI thread, then push the confirm modal.
        self._nav_gen += 1
        self._prepare_folder(node, self._nav_gen)

    # --- thread workers -------------------------------------------------

    @work(thread=True, exclusive=True, group="nav")
    def _open_node(self, node, gen: int) -> None:
        if node.is_leaf:
            parts = node.parts()
            self.call_from_thread(self._begin_download, parts)
        else:
            children = node.children()
            self.call_from_thread(self._descend, children, node.label, gen)

    @work(thread=True, exclusive=True, group="nav")
    def _prepare_folder(self, node, gen: int) -> None:
        parts = node.enumerate_parts()
        self.call_from_thread(self._confirm_folder, parts, gen)

    @work(thread=True, exclusive=True, group="download")
    def _download(self, parts: list[PartRef]) -> None:
        def on_progress(progress: Progress) -> None:
            self.call_from_thread(self._update_progress, progress)

        result = self._download_runner(parts, on_progress=on_progress)
        self.call_from_thread(self._download_done, result)

    # --- UI-thread callbacks --------------------------------------------

    def _descend(self, children: list, label: str, gen: int) -> None:
        if gen != self._nav_gen:  # user navigated away before this resolved
            return
        self.nav.push(children, label=label)
        with self.prevent(Input.Changed):
            self.query_one("#filter", Input).value = ""
        self._refresh()

    def _confirm_folder(self, parts: list[PartRef], gen: int) -> None:
        if gen != self._nav_gen:  # stale enumerate result for a node we left
            return
        if not parts:
            return

        def on_result(confirmed: Optional[bool]) -> None:
            if confirmed:
                self._begin_download(parts)

        self.push_screen(ConfirmScreen(_summarize(parts)), on_result)

    def _begin_download(self, parts: list[PartRef]) -> None:
        if self._downloading:
            self.query_one("#status", Static).update(
                "A download is already in progress — wait for it to finish."
            )
            return
        self._downloading = True
        self.query_one("#status", Static).update(f"Queued {len(parts)} file(s)")
        self._download(parts)

    def _update_progress(self, p: Progress) -> None:
        pct = (p.done / p.total * 100) if p.total else 0.0
        mbps = p.speed_bps / 1e6
        eta = (p.total - p.done) / p.speed_bps if p.speed_bps else 0.0
        self.query_one("#progress", Static).update(
            f"{p.filename}  {pct:.0f}% ({p.done}/{p.total})  "
            f"{mbps:.1f} MB/s  ETA {eta:.0f}s  [{p.index}/{p.count}]"
        )

    def _download_done(self, result: DownloadResult) -> None:
        self._downloading = False
        succeeded = len(result.succeeded)
        msg = f"Done: {succeeded} succeeded"
        if result.failed:
            names = ", ".join(pref.filename for pref, _err in result.failed)
            msg += f"; {len(result.failed)} failed: {names}"
        self.query_one("#status", Static).update(msg)
