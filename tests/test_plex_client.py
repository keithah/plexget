from types import SimpleNamespace

from plexget.plex_client import (
    PlexClient,
    ServerInfo,
    absolute_part_url,
    parts_for_item,
    EpisodeNode,
    ShowNode,
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
