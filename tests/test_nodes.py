from plexget.nodes import PartRef
from tests.fakes import FakeNode, part


def test_partref_is_frozen_and_hashable():
    p = PartRef(url="u", filename="f.mkv", size=10, rel_dir=("a", "b"))
    assert p.rel_dir == ("a", "b")
    assert hash(p)  # frozen dataclass is hashable


def test_leaf_enumerate_returns_own_parts():
    ep = FakeNode("S01E01", "episode", True, parts=[part("S01E01.mkv", 100)])
    assert [p.filename for p in ep.enumerate_parts()] == ["S01E01.mkv"]


def test_folder_enumerate_walks_all_descendant_leaves():
    s1 = FakeNode("Season 1", "season", False, children=[
        FakeNode("S01E01", "episode", True, parts=[part("S01E01.mkv", 100)]),
        FakeNode("S01E02", "episode", True, parts=[part("S01E02.mkv", 200)]),
    ])
    s2 = FakeNode("Season 2", "season", False, children=[
        FakeNode("S02E01", "episode", True, parts=[part("S02E01.mkv", 300)]),
    ])
    show = FakeNode("Severance", "show", False, children=[s1, s2])

    parts = show.enumerate_parts()
    assert [p.filename for p in parts] == ["S01E01.mkv", "S01E02.mkv", "S02E01.mkv"]
    assert sum(p.size for p in parts) == 600
