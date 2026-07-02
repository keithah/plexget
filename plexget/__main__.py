from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Optional

import requests
from plexapi.myplex import MyPlexAccount, MyPlexPinLogin

from plexget import auth
from plexget.downloader import DownloadResult, run_jobs
from plexget.nodes import PartRef
from plexget.plex_client import PlexClient, ServerInfo, server_nodes


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="plexget")
    parser.add_argument("--out", type=Path, default=Path.cwd())
    parser.add_argument("--server", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--segments", type=int, default=1)
    parser.add_argument("--pin", action="store_true")
    return parser.parse_args(argv)


def choose_server(servers: list[ServerInfo], name: Optional[str]) -> ServerInfo:
    if name:
        for s in servers:
            if s.name.lower() == name.lower():
                return s
        raise SystemExit(f"No server named {name!r}. Available: "
                         + ", ".join(s.name for s in servers))
    if len(servers) == 1:
        return servers[0]
    if not servers:
        raise SystemExit("No Plex servers accessible on this account.")
    raise SystemExit("Multiple servers; pass --server NAME: "
                     + ", ".join(s.name for s in servers))


def make_download_runner(out: Path, mirror: bool, segments: int,
                         session_factory: Callable[[], object]) -> Callable[[list], None]:
    def run(parts: list[PartRef]) -> None:
        session = session_factory()
        run_jobs(parts, out, mirror=mirror, session=session, segments=segments)
    return run


def _prompt_server(servers: list[ServerInfo]) -> ServerInfo:
    for i, s in enumerate(servers, 1):
        print(f"  {i}. {s.name}")
    while True:
        choice = input("Select server #: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(servers):
            return servers[int(choice) - 1]


def main(argv=None) -> int:
    ns = parse_args(argv)
    account = auth.login(
        token=ns.token,
        force_pin=ns.pin,
        account_factory=lambda token, cid: MyPlexAccount(token=token),
        pin_factory=lambda cid: MyPlexPinLogin(oauth=False),
    )
    client = PlexClient(account)
    servers = client.list_servers()
    try:
        info = choose_server(servers, ns.server)
    except SystemExit:
        if not ns.server and len(servers) > 1:
            info = _prompt_server(servers)
        else:
            raise
    print(f"Connecting to {info.name}...")
    server, base_url, token = PlexClient.connect(info)
    nodes = server_nodes(server, base_url, token)
    mirror = True
    runner = make_download_runner(ns.out, mirror, ns.segments, requests.Session)
    from plexget.app import PlexGetApp
    PlexGetApp(nodes, download_runner=runner).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
