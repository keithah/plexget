from plexget.app import NavState, Level
from tests.fakes import FakeNode, part


def make_tree():
    ep1 = FakeNode("S01E01", "episode", True, parts=[part("S01E01.mkv", 100)])
    ep2 = FakeNode("S01E02", "episode", True, parts=[part("S01E02.mkv", 200)])
    season = FakeNode("Season 1", "season", False, children=[ep1, ep2])
    show_sev = FakeNode("Severance", "show", False, children=[season])
    show_silo = FakeNode("Silo", "show", False, children=[])
    return [show_sev, show_silo]


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


import pytest

from plexget.app import PlexGetApp


@pytest.mark.asyncio
async def test_pilot_enter_descends_and_leaf_downloads():
    tree = make_tree()
    queued = []
    app = PlexGetApp(tree, download_runner=queued.append)
    async with app.run_test() as pilot:
        # descend into Severance
        await pilot.press("enter")
        assert "Severance" in app.nav.breadcrumb()
        # descend into Season 1
        await pilot.press("enter")
        # select episode -> download
        await pilot.press("enter")
        assert len(queued) == 1
        assert queued[0][0].filename == "S01E01.mkv"
