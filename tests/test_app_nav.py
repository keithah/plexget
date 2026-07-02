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
