from types import SimpleNamespace

from plexget.plex_client import (
    PlexClient,
    ServerInfo,
    absolute_part_url,
    parts_for_item,
    EpisodeNode,
    MovieNode,
    ShowNode,
    LibraryNode,
    server_nodes,
)


def test_absolute_part_url_appends_token():
    url = absolute_part_url("http://host:32400", "/library/parts/1/file.mkv", "TOK")
    assert url == "http://host:32400/library/parts/1/file.mkv?X-Plex-Token=TOK"


def _fake_episode(title="S01E01", file="S01E01.mkv", size=100, key="/parts/1/f.mkv"):
    part = SimpleNamespace(key=key, file=f"/data/{file}", size=size)
    media = SimpleNamespace(parts=[part])
    return SimpleNamespace(title=title, media=[media])


def test_parts_for_item_reads_media_parts():
    ep = _fake_episode()
    parts = parts_for_item(ep, "http://host:32400", "TOK", rel_dir=("Show", "Season 01"))
    assert len(parts) == 1
    assert parts[0].filename == "S01E01.mkv"
    assert parts[0].size == 100
    assert parts[0].rel_dir == ("Show", "Season 01")
    assert parts[0].url.endswith("X-Plex-Token=TOK")


def test_episode_node_is_leaf_and_yields_parts():
    ep = _fake_episode()
    node = EpisodeNode(ep, base_url="http://host:32400", token="TOK",
                       rel_dir=("Severance", "Season 01"))
    assert node.is_leaf is True
    assert node.kind == "episode"
    parts = node.parts()
    assert parts[0].filename == "S01E01.mkv"
    assert node.enumerate_parts() == parts


def test_show_node_enumerates_all_episodes():
    ep1 = _fake_episode("S01E01", "S01E01.mkv", 100)
    ep2 = _fake_episode("S01E02", "S01E02.mkv", 200)
    season = SimpleNamespace(title="Season 1", index=1,
                             episodes=lambda: [ep1, ep2])
    show = SimpleNamespace(title="Severance", seasons=lambda: [season])
    node = ShowNode(show, base_url="http://host:32400", token="TOK")
    assert node.is_leaf is False
    parts = node.enumerate_parts()
    assert [p.filename for p in parts] == ["S01E01.mkv", "S01E02.mkv"]


def test_list_servers_filters_to_server_resources():
    r1 = SimpleNamespace(name="HomeServer", provides="server")
    r2 = SimpleNamespace(name="SomePlayer", provides="player")
    account = SimpleNamespace(resources=lambda: [r1, r2])
    servers = PlexClient(account).list_servers()
    assert [s.name for s in servers] == ["HomeServer"]
    assert isinstance(servers[0], ServerInfo)


def _fake_movie(title="Blade Runner", file="Blade.Runner.mkv", size=500, key="/parts/9/f.mkv"):
    part = SimpleNamespace(key=key, file=f"/movies/{file}", size=size)
    media = SimpleNamespace(parts=[part])
    return SimpleNamespace(title=title, media=[media])


def _fake_show_one_ep():
    ep = _fake_episode()
    season = SimpleNamespace(title="Season 1", index=1, episodes=lambda: [ep])
    return SimpleNamespace(title="Severance", seasons=lambda: [season])


def test_movie_node_is_leaf_and_yields_parts():
    node = MovieNode(_fake_movie(), base_url="http://host:32400", token="TOK")
    assert node.is_leaf is True
    assert node.kind == "movie"
    parts = node.parts()
    assert parts[0].filename == "Blade.Runner.mkv"
    assert parts[0].size == 500
    assert node.enumerate_parts() == parts


def test_library_node_dispatches_by_section_type():
    show_section = SimpleNamespace(title="TV", type="show",
                                   all=lambda: [_fake_show_one_ep()])
    movie_section = SimpleNamespace(title="Films", type="movie",
                                    all=lambda: [_fake_movie()])
    show_lib = LibraryNode(show_section, base_url="http://h:32400", token="TOK")
    movie_lib = LibraryNode(movie_section, base_url="http://h:32400", token="TOK")
    assert [c.kind for c in show_lib.children()] == ["show"]
    assert [c.kind for c in movie_lib.children()] == ["movie"]


def test_server_nodes_filters_to_show_and_movie_only():
    sections = [
        SimpleNamespace(title="TV", type="show", all=lambda: []),
        SimpleNamespace(title="Films", type="movie", all=lambda: []),
        SimpleNamespace(title="Music", type="artist", all=lambda: []),
        SimpleNamespace(title="Photos", type="photo", all=lambda: []),
    ]
    server = SimpleNamespace(library=SimpleNamespace(sections=lambda: sections))
    nodes = server_nodes(server, "http://h:32400", "TOK")
    assert [n.label for n in nodes] == ["TV", "Films"]


def test_parts_for_item_disambiguates_fileless_parts():
    p1 = SimpleNamespace(key="/parts/1/a", file="", size=10)
    p2 = SimpleNamespace(key="/parts/2/b", file="", size=20)
    item = SimpleNamespace(title="Untitled", media=[SimpleNamespace(parts=[p1, p2])])
    parts = parts_for_item(item, "http://h:32400", "TOK", rel_dir=())
    assert [p.filename for p in parts] == ["Untitled (1)", "Untitled (2)"]
