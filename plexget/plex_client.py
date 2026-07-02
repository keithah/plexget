from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlencode

from plexget.nodes import Node, PartRef


@dataclass
class ServerInfo:
    name: str
    resource: object


def absolute_part_url(base_url: str, part_key: str, token: str) -> str:
    base = base_url.rstrip("/")
    query = urlencode({"X-Plex-Token": token})
    return f"{base}{part_key}?{query}"


def parts_for_item(item, base_url: str, token: str, rel_dir: tuple[str, ...]) -> list[PartRef]:
    refs: list[PartRef] = []
    all_parts = [
        part
        for media in (getattr(item, "media", []) or [])
        for part in (getattr(media, "parts", []) or [])
    ]
    multi = len(all_parts) > 1
    for index, part in enumerate(all_parts, start=1):
        raw = getattr(part, "file", "") or ""
        filename = os.path.basename(raw)
        if not filename:
            title = os.path.basename(getattr(item, "title", "") or "") or "download"
            filename = f"{title} ({index})" if multi else title
        refs.append(
            PartRef(
                url=absolute_part_url(base_url, part.key, token),
                filename=filename,
                size=int(getattr(part, "size", 0) or 0),
                rel_dir=rel_dir,
            )
        )
    return refs


class EpisodeNode:
    kind = "episode"
    is_leaf = True

    def __init__(self, episode, *, base_url, token, rel_dir):
        self._ep = episode
        self._base_url = base_url
        self._token = token
        self._rel_dir = rel_dir
        self.label = getattr(episode, "title", "episode")

    def children(self):
        return []

    def parts(self):
        return parts_for_item(self._ep, self._base_url, self._token, self._rel_dir)

    def enumerate_parts(self):
        return self.parts()


class MovieNode:
    kind = "movie"
    is_leaf = True

    def __init__(self, movie, *, base_url, token, rel_dir=()):
        self._movie = movie
        self._base_url = base_url
        self._token = token
        self._rel_dir = rel_dir
        self.label = getattr(movie, "title", "movie")

    def children(self):
        return []

    def parts(self):
        return parts_for_item(self._movie, self._base_url, self._token, self._rel_dir)

    def enumerate_parts(self):
        return self.parts()


class SeasonNode:
    kind = "season"
    is_leaf = False

    def __init__(self, season, *, base_url, token, show_title):
        self._season = season
        self._base_url = base_url
        self._token = token
        self._show_title = show_title
        self.label = getattr(season, "title", "Season")

    def _rel_dir(self):
        return (self._show_title, self.label)

    def children(self):
        return [
            EpisodeNode(ep, base_url=self._base_url, token=self._token,
                        rel_dir=self._rel_dir())
            for ep in self._season.episodes()
        ]

    def parts(self):
        return []

    def enumerate_parts(self):
        out = []
        for child in self.children():
            out.extend(child.enumerate_parts())
        return out


class ShowNode:
    kind = "show"
    is_leaf = False

    def __init__(self, show, *, base_url, token):
        self._show = show
        self._base_url = base_url
        self._token = token
        self.label = getattr(show, "title", "Show")

    def children(self):
        return [
            SeasonNode(season, base_url=self._base_url, token=self._token,
                       show_title=self.label)
            for season in self._show.seasons()
        ]

    def parts(self):
        return []

    def enumerate_parts(self):
        out = []
        for child in self.children():
            out.extend(child.enumerate_parts())
        return out


class LibraryNode:
    is_leaf = False

    def __init__(self, section, *, base_url, token):
        self._section = section
        self._base_url = base_url
        self._token = token
        self.label = getattr(section, "title", "Library")
        self.kind = "library"

    def children(self):
        section_type = getattr(self._section, "type", "")
        if section_type == "show":
            return [
                ShowNode(show, base_url=self._base_url, token=self._token)
                for show in self._section.all()
            ]
        return [
            MovieNode(movie, base_url=self._base_url, token=self._token)
            for movie in self._section.all()
        ]

    def parts(self):
        return []

    def enumerate_parts(self):
        out = []
        for child in self.children():
            out.extend(child.enumerate_parts())
        return out


def server_nodes(server, base_url: str, token: str) -> list[Node]:
    nodes = []
    for section in server.library.sections():
        if getattr(section, "type", "") in ("show", "movie"):
            nodes.append(LibraryNode(section, base_url=base_url, token=token))
    return nodes


class PlexClient:
    def __init__(self, account):
        self._account = account

    def list_servers(self) -> list[ServerInfo]:
        servers = []
        for resource in self._account.resources():
            if "server" in (getattr(resource, "provides", "") or ""):
                servers.append(ServerInfo(name=resource.name, resource=resource))
        return servers

    @staticmethod
    def connect(server_info: ServerInfo):
        server = server_info.resource.connect()
        return server, server._baseurl, server._token
