from pathlib import Path

import pytest

from plexget import __main__ as m
from plexget.plex_client import ServerInfo


def test_parse_args_defaults():
    ns = m.parse_args([])
    assert ns.out == Path.cwd()
    assert ns.segments == 1
    assert ns.server is None
    assert ns.pin is False


def test_parse_args_values():
    ns = m.parse_args(["--out", "/tmp/x", "--server", "Home", "--segments", "4", "--pin"])
    assert ns.out == Path("/tmp/x")
    assert ns.server == "Home"
    assert ns.segments == 4
    assert ns.pin is True


def test_choose_server_by_name_case_insensitive():
    servers = [ServerInfo("HomeServer", object()), ServerInfo("NAS", object())]
    assert m.choose_server(servers, "homeserver").name == "HomeServer"


def test_choose_server_single_auto():
    servers = [ServerInfo("Only", object())]
    assert m.choose_server(servers, None).name == "Only"


def test_choose_server_ambiguous_raises():
    servers = [ServerInfo("A", object()), ServerInfo("B", object())]
    with pytest.raises(SystemExit):
        m.choose_server(servers, None)


def test_download_runner_invokes_segmented_per_part(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        m, "run_jobs",
        lambda parts, out, **kw: calls.append((parts, out, kw)) or m.DownloadResult(),
    )
    runner = m.make_download_runner(tmp_path, mirror=True, segments=4,
                                    session_factory=lambda: object())
    from plexget.nodes import PartRef
    runner([PartRef("u", "f.mkv", 10)])
    assert calls
    assert calls[0][2]["mirror"] is True


def test_choose_server_no_servers_raises():
    with pytest.raises(SystemExit):
        m.choose_server([], None)


def test_choose_server_unknown_name_raises():
    servers = [ServerInfo("A", object())]
    with pytest.raises(SystemExit):
        m.choose_server(servers, "nope")


def test_download_runner_forwards_segments(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        m, "run_jobs",
        lambda parts, out, **kw: captured.update(kw) or m.DownloadResult(),
    )
    runner = m.make_download_runner(tmp_path, mirror=False, segments=7,
                                    session_factory=lambda: object())
    from plexget.nodes import PartRef
    runner([PartRef("u", "f.mkv", 10)])
    assert captured["segments"] == 7
