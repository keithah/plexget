from plexget.demo import demo_nodes, demo_runner
from plexget.downloader import DownloadResult, Progress
from plexget.nodes import Node, PartRef


def test_demo_nodes_conform_to_node_protocol():
    nodes = demo_nodes()
    assert [n.label for n in nodes] == ["TV Shows", "Movies"]
    for n in nodes:
        assert isinstance(n, Node)  # runtime-checkable protocol
        assert not n.is_leaf


def test_demo_tree_enumerates_real_partrefs():
    tv = demo_nodes()[0]
    parts = tv.enumerate_parts()
    assert parts, "TV library should enumerate episodes"
    assert all(isinstance(p, PartRef) and p.size > 0 for p in parts)
    # a leaf episode yields exactly its own part
    show = tv.children()[0]
    season = show.children()[0]
    episode = season.children()[0]
    assert episode.is_leaf
    assert len(episode.parts()) == 1


def test_demo_runner_reports_progress_and_succeeds():
    part = PartRef("demo://x.mkv", "x.mkv", 100 * 1024 * 1024)
    seen = []
    result = demo_runner([part], on_progress=seen.append, sleep=lambda _s: None, steps=4)
    assert isinstance(result, DownloadResult)
    assert result.succeeded == [part]
    assert result.failed == []
    assert seen and isinstance(seen[0], Progress)
    assert seen[-1].done == part.size  # finishes at 100%
    assert all(p.count == 1 and p.index == 1 for p in seen)
