import threading

import pytest

from plexget.app import NavState, Level, PlexGetApp
from plexget.downloader import DownloadResult, Progress
from tests.fakes import FakeNode, part


class BlockingFolder:
    """Folder node whose children() blocks until released (Guard 2 tests)."""

    kind = "show"
    is_leaf = False

    def __init__(self, label, entered, release, children):
        self.label = label
        self._entered = entered
        self._release = release
        self._children = list(children)

    def children(self):
        self._entered.set()
        self._release.wait(timeout=5)
        return list(self._children)

    def parts(self):
        return []

    def enumerate_parts(self):
        out = []
        for child in self._children:
            out.extend(child.enumerate_parts())
        return out


def make_tree():
    ep1 = FakeNode("S01E01", "episode", True, parts=[part("S01E01.mkv", 100)])
    ep2 = FakeNode("S01E02", "episode", True, parts=[part("S01E02.mkv", 200)])
    season = FakeNode("Season 1", "season", False, children=[ep1, ep2])
    show_sev = FakeNode("Severance", "show", False, children=[season])
    show_silo = FakeNode("Silo", "show", False, children=[])
    return [show_sev, show_silo]


def make_runner(queued):
    """Runner matching run(parts, on_progress=None) -> DownloadResult."""
    def run(parts, on_progress=None):
        queued.append(parts)
        return DownloadResult(succeeded=list(parts))
    return run


async def _settle(app, pilot):
    """Let threaded workers (and any workers they spawn) finish and UI settle."""
    for _ in range(6):
        await app.workers.wait_for_complete()
        await pilot.pause()


async def _wait_until(app, pilot, predicate, tries=80):
    """Poll the event loop (without blocking on workers) until predicate holds."""
    for _ in range(tries):
        if predicate():
            return
        await pilot.pause()
    raise AssertionError("condition not met within pilot polling window")


def _status_text(app):
    from textual.widgets import Static
    return str(app.query_one("#status", Static).render())


def test_visible_applies_filter():
    nav = NavState([Level(make_tree(), "", 0)])
    assert [n.label for n in nav.visible()] == ["Severance", "Silo"]
    nav.set_filter("sev")
    assert [n.label for n in nav.visible()] == ["Severance"]


def test_push_and_pop_restore_level():
    nav = NavState([Level(make_tree(), "sil", 0)])
    show = nav.selected()  # filtered -> Silo
    assert show.label == "Silo"
    nav.push(show.children())
    assert nav.current_nodes() == []  # Silo has no children
    assert nav.pop() is True
    # filter + selection restored
    assert nav.visible()[0].label == "Silo"
    assert nav.pop() is False  # at root now


def test_move_clamps_within_visible():
    nav = NavState([Level(make_tree(), "", 0)])
    nav.move(-1)
    assert nav.selected().label == "Severance"  # clamped at top
    nav.move(1)
    assert nav.selected().label == "Silo"
    nav.move(5)
    assert nav.selected().label == "Silo"  # clamped at bottom


def test_breadcrumb_reflects_depth():
    nav = NavState([Level(make_tree(), "", 0)])
    assert nav.breadcrumb() == "/"
    nav.push(make_tree()[0].children())  # into Severance
    assert "Severance" in nav.breadcrumb()

def test_app_title_is_cli_name():
    assert PlexGetApp.TITLE == "plexget"


@pytest.mark.asyncio
async def test_pilot_enter_descends_and_leaf_downloads():
    tree = make_tree()
    queued = []
    app = PlexGetApp(tree, download_runner=make_runner(queued))
    async with app.run_test() as pilot:
        # descend into Severance
        await pilot.press("enter")
        await _settle(app, pilot)
        assert "Severance" in app.nav.breadcrumb()
        # descend into Season 1
        await pilot.press("enter")
        await _settle(app, pilot)
        # select episode -> download
        await pilot.press("enter")
        await _settle(app, pilot)
        assert len(queued) == 1
        assert queued[0][0].filename == "S01E01.mkv"


@pytest.mark.asyncio
async def test_pilot_down_then_enter_selects_second_item():
    # Flat list of leaves; second is a distinct file we must target.
    alpha = FakeNode("Alpha", "movie", True, parts=[part("Alpha.mkv", 100)])
    bravo = FakeNode("Bravo", "movie", True, parts=[part("Bravo.mkv", 200)])
    queued = []
    app = PlexGetApp([alpha, bravo], download_runner=make_runner(queued))
    async with app.run_test() as pilot:
        await pilot.press("down")   # highlight the SECOND row
        await pilot.pause()
        await pilot.press("enter")  # download the highlighted (second) item
        await _settle(app, pilot)
    assert len(queued) == 1
    assert queued[0][0].filename == "Bravo.mkv"


@pytest.mark.asyncio
async def test_pilot_typing_filters_list():
    tree = make_tree()  # ["Severance", "Silo"]
    app = PlexGetApp(tree, download_runner=make_runner([]))
    async with app.run_test() as pilot:
        for ch in "sil":
            await pilot.press(ch)
        await pilot.pause()
        assert [n.label for n in app.nav.visible()] == ["Silo"]
        # filter text is surfaced in the Input widget
        from textual.widgets import Input
        assert app.query_one("#filter", Input).value == "sil"


@pytest.mark.asyncio
async def test_pilot_leaf_download_renders_progress():
    leaf = FakeNode("Movie", "movie", True, parts=[part("File.mkv", 100_000_000)])
    prog = Progress("File.mkv", 50_000_000, 100_000_000, 2_000_000, 1, 1)

    def runner(parts, on_progress=None):
        if on_progress:
            on_progress(prog)
        return DownloadResult(succeeded=list(parts))

    app = PlexGetApp([leaf], download_runner=runner)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await _settle(app, pilot)
        from textual.widgets import Static
        text = str(app.query_one("#progress", Static).render())
    assert "MB/s" in text          # speed rendered
    assert "2.0 MB/s" in text      # speed_bps / 1e6
    assert "ETA 25s" in text       # (total-done)/speed_bps
    assert "50%" in text           # done/total
    assert "(47.7 MB/95.4 MB)" in text


@pytest.mark.asyncio
async def test_pilot_right_arrow_confirms_and_downloads_folder():
    tree = make_tree()
    queued = []
    app = PlexGetApp(tree, download_runner=make_runner(queued))
    async with app.run_test() as pilot:
        await pilot.press("right")   # enumerate off-thread, then open confirm
        await _settle(app, pilot)
        await pilot.press("y")       # confirm
        await _settle(app, pilot)
    assert len(queued) == 1
    # enumerate_parts walked Severance -> Season 1 -> both episodes
    assert [p.filename for p in queued[0]] == ["S01E01.mkv", "S01E02.mkv"]


@pytest.mark.asyncio
async def test_pilot_confirm_hint_renders_shortcut_keys():
    tree = make_tree()
    app = PlexGetApp(tree, download_runner=make_runner([]))
    async with app.run_test() as pilot:
        await pilot.press("right")
        await _settle(app, pilot)
        from textual.widgets import Label
        labels = [str(label.render()) for label in app.screen.query(Label)]
        assert "[y] download   [n] cancel" in labels


@pytest.mark.asyncio
async def test_pilot_right_arrow_cancel_downloads_nothing():
    tree = make_tree()
    queued = []
    app = PlexGetApp(tree, download_runner=make_runner(queued))
    async with app.run_test() as pilot:
        await pilot.press("right")
        await _settle(app, pilot)
        await pilot.press("n")       # cancel
        await _settle(app, pilot)
    assert queued == []


@pytest.mark.asyncio
async def test_pilot_second_download_rejected_while_active():
    # Guard 1: a download already in flight blocks starting another.
    leaf = FakeNode("Movie", "movie", True, parts=[part("File.mkv", 100)])
    release = threading.Event()
    calls = []

    def runner(parts, on_progress=None):
        calls.append(parts)
        release.wait(timeout=5)  # hold the download "in progress"
        return DownloadResult(succeeded=list(parts))

    app = PlexGetApp([leaf], download_runner=runner)
    try:
        async with app.run_test() as pilot:
            await pilot.press("enter")  # start first download (blocks in runner)
            await _wait_until(app, pilot, lambda: app._downloading and len(calls) == 1)
            await pilot.press("enter")  # attempt a second while first is active
            await _wait_until(app, pilot, lambda: "already in progress" in _status_text(app))
            assert len(calls) == 1  # second download was rejected
            release.set()  # let the first finish so teardown is clean
            await _wait_until(app, pilot, lambda: not app._downloading)
    finally:
        release.set()


@pytest.mark.asyncio
async def test_pilot_stale_descend_is_dropped():
    # Guard 2: a superseded folder-open worker's descend callback is ignored.
    entered = threading.Event()
    release = threading.Event()
    a_child = FakeNode("A-child", "episode", True, parts=[part("a.mkv", 1)])
    folder_a = BlockingFolder("Alpha", entered, release, [a_child])
    folder_b = FakeNode("Bravo", "show", False,
                        children=[FakeNode("B-child", "episode", True)])

    app = PlexGetApp([folder_a, folder_b], download_runner=make_runner([]))
    try:
        async with app.run_test() as pilot:
            await pilot.press("enter")  # open Alpha -> worker blocks in children()
            await _wait_until(app, pilot, lambda: entered.is_set())
            # Supersede it by navigating to Bravo instead.
            await pilot.press("down")
            await pilot.pause()
            await pilot.press("enter")  # open Bravo (fast) -> bumps _nav_gen
            await _wait_until(app, pilot, lambda: "Bravo" in app.nav.breadcrumb())
            release.set()               # Alpha's children() now resolves...
            await _settle(app, pilot)   # ...but its descend must be dropped
            assert "Bravo" in app.nav.breadcrumb()
            assert "Alpha" not in app.nav.breadcrumb()
    finally:
        release.set()
