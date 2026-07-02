# plexget — design spec

**Date:** 2026-07-02
**Status:** Approved (design), pending implementation plan

## Summary

`plexget` is a standalone Python terminal application that gives an "SFTP-like"
experience for pulling media files out of a Plex server. You log in with your
Plex account (PIN/link flow), pick a server, then navigate
`Libraries → Shows → Seasons → Episodes` (or `Libraries → Movies`) with an
**arrow-key TUI**. Pressing **Enter** on a single episode/movie downloads it;
pressing **→** on any node offers "download everything under this" (whole
show/season/movie folder). Downloads keep the **original file** (no transcode)
and show live progress including **speed (MB/s) and ETA**.

This is a fresh tool, not a modification of the existing .NET Reaparr app. It
reuses only the *concepts* of Plex auth and single-file download that Reaparr
implements.

## Goals

- Log into Plex with an account using the PIN/link flow; cache the token so
  re-launch skips the prompt.
- List all accessible servers and let the user choose one.
- Browse TV (Show → Season → Episode) and Movie libraries.
- Arrow-key navigation with type-to-filter, Enter to descend/download, ← to go
  back, → for a per-node action menu, and mouse-click support.
- Download a single episode/movie file, or everything under a folder (with a
  count + total-size confirmation first).
- Fast, streamed downloads of the original file, with a progress bar showing
  percent, transferred/total, **speed (MB/s)**, and **ETA**.

## Non-goals (YAGNI)

- No transcoding / quality selection — original file only.
- No music/photo libraries in v1 (TV + Movies only).
- No real SFTP/FUSE protocol server — it only *feels* like one.
- No upload, delete, or any server mutation.
- No parallel *multi-file* downloads in v1 (queue is sequential); optional
  *segmented single-file* parallelism is the one concurrency feature (see
  Downloads).

## Stack

- **Python 3.11+**, packaged with `pyproject.toml`, exposing a `plexget`
  console entry point.
- **Dependencies:**
  - `textual` — arrow-key TUI, mouse, progress widgets.
  - `python-plexapi` — PIN auth (`MyPlexPinLogin`), server discovery
    (`MyPlexAccount.resources()`), connection selection, library navigation.
  - `requests` — chunked streaming download so we control the progress/speed
    readout (plexapi's own `.download()` gives no progress callback).
  - `platformdirs` — cross-platform config/token directory.
- **Standalone git repo** at `~/src/plexget` (independent of Reaparr).

## Module layout

```
plexget/
  pyproject.toml
  README.md
  plexget/
    __init__.py
    __main__.py        # entry point: parse flags, run auth, launch app
    auth.py            # PIN login + token cache
    plex_client.py     # plexapi wrapper: servers, libraries, media, part URLs
    nodes.py           # uniform Node model the UI navigates
    downloader.py      # streaming download queue with progress/speed
    app.py             # Textual App: list, filter, breadcrumb, keybindings
  tests/
    test_nodes.py
    test_downloader.py
    test_filter.py
    test_app_nav.py
```

### `auth.py`
- `login(force_pin=False) -> MyPlexAccount`.
- Token cache at `<platformdirs config>/plexget/auth.json` storing the auth
  token and a stable `X-Plex-Client-Identifier` (generated once, reused so the
  token stays valid).
- On launch: if a cached token exists, construct `MyPlexAccount(token=...)` and
  verify; on failure fall back to `MyPlexPinLogin` — print the `plex.tv/link`
  URL + code, poll until approved, then persist the token.
- Respects `PLEX_TOKEN` env var / `--token` flag to skip the flow entirely.

### `plex_client.py`
- `list_servers() -> list[ServerInfo]` — `account.resources()` filtered to
  `provides == "server"`, owned + shared.
- `connect(server_info) -> PlexServer` — `resource.connect()` (plexapi picks a
  reachable local/remote connection); raises a clear error if none reachable.
- `list_libraries(server)` — `server.library.sections()` filtered to `movie`
  and `show` types.
- Navigation helpers returning plexapi objects: shows, seasons, episodes,
  movies.
- `resolve_download(media_item) -> list[PartRef]` where a `PartRef` has
  `url` (absolute, token-appended), `filename`, `size` (bytes). An
  episode/movie may have multiple parts/files; each becomes a `PartRef`.
- `enumerate_leaves(node) -> list[PartRef]` — walk everything downloadable
  beneath a folder node (for the → whole-folder action and its size preview).
- **All methods are plain blocking calls**; the UI always invokes them from a
  Textual thread-worker (see app.py).

### `nodes.py`
- A `Node` protocol/dataclass decoupling the UI from Plex types:
  - `label: str`, `kind: Literal["server","library","show","season",
    "episode","movie"]`
  - `is_leaf: bool` (episode/movie files are leaves; folders are not)
  - `children() -> list[Node]` (folders only)
  - `parts() -> list[PartRef]` (leaves — the file(s) to download)
  - `enumerate_parts() -> list[PartRef]` (any node — self if leaf, else all
    descendant leaves; used by the → action)
- Keeps `app.py` free of plexapi-specific branching and makes the tree unit
  testable with a fake client.

### `downloader.py`
- `DownloadJob` = ordered list of `(PartRef, dest_path)`.
- Destination rules:
  - Single leaf → file goes directly into `--out` (default: current dir).
  - Whole-folder job → **mirror the Plex hierarchy** under `--out`
    (`Show/Season 01/S01E01.mkv`) to avoid collisions.
  - Filenames sanitized for the local filesystem.
- Streaming: one `requests.Session` (keep-alive), `stream=True`, large chunk
  size (e.g. 1 MiB), write to `dest.part` temp then atomic rename on success.
- **Skip-existing:** if the final file exists with the same byte size, skip.
- **Speed/ETA:** track bytes/second over a short rolling window; expose a
  progress callback carrying `(filename, done_bytes, total_bytes, speed_bps,
  index, count)`.
- **Reliability:** one automatic retry per file on network error; on repeated
  failure mark the file failed and continue the queue; return a summary of
  successes/failures.
- **Speed feature (single large file):** optional segmented download — split a
  large file into N byte-range requests (HTTP `Range`) fetched by a small
  thread pool and reassembled, for higher throughput on high-latency links.
  Guarded by a `--segments N` flag (default 1 = plain stream); only used for a
  single leaf, never across a multi-file queue (queue stays sequential).
- Runs inside a Textual thread-worker; progress is posted to the UI via
  `post_message` / `call_from_thread`.

### `app.py` (Textual)
- Layout: breadcrumb header (current path) · scrollable list (current level) ·
  filter `Input` at the bottom · a progress panel that appears during
  downloads (filename, bar, `done/total`, **MB/s**, **ETA**, `file i/N`).
- **Navigation stack** of levels; each level holds its `Node` list + current
  filter text + selection index, so ← restores exactly where you were.
- Keybindings:
  - `↑/↓` move selection; mouse click selects.
  - printable keys → append to filter; `Backspace` edits it; list filters
    case-insensitively (substring/fuzzy).
  - `Enter` → folder: push its `children()` (fetched in a worker); leaf: queue
    its `parts()` and start downloading.
  - `←` (or `Backspace` when filter empty) → pop level; at top level → quit
    prompt.
  - `→` → open action menu (modal): "Download everything under this" — first
    runs `enumerate_parts()` in a worker to get **count + total size**, shows a
    confirm ("Download 8 files, 18.4 GB?"), then queues on yes.
  - `q` / `Ctrl-C` → quit; cancels in-flight download and deletes its `.part`.
- Because plexapi/requests block, **every network action is dispatched to a
  `@work(thread=True)` worker**; the UI thread only renders and handles keys.

### `__main__.py`
- Flags: `--out DIR` (download target), `--server NAME` (skip picker if it
  matches), `--token TOKEN` / `PLEX_TOKEN`, `--segments N` (single-file
  parallelism), `--pin` (force re-auth).
- Flow: `login()` → `list_servers()` (or match `--server`) → launch Textual
  `App` seeded with the server list.

## Data flow

```
login() ──token──> MyPlexAccount
      └─ list_servers() ─> [ServerInfo]  ──user picks──> connect() ─> PlexServer
                                                              │
                          list_libraries ─> Nodes ─┐          │
     ↑↓ filter Enter ← →  (Textual App navigates Node tree)   │
                                                    │          │
     Enter/→ ─> PartRef(s) ─> DownloadJob ─> downloader (thread worker)
                                                    │
                          progress (bytes, speed, ETA) ─> UI progress panel
```

## Error handling

| Failure | Behavior |
|---|---|
| Cached token invalid | Fall back to PIN login automatically. |
| PIN rejected / times out | Message + offer retry. |
| No reachable server connection | Error toast, return to server picker. |
| Library/list fetch error | Error toast, stay on current level. |
| Download network error | Retry once; then mark file failed, continue queue. |
| Partial download interrupted (quit) | Delete `.part` temp; final file untouched. |
| End of multi-file job with failures | Summary panel lists failed files. |

## Testing

- **`test_nodes.py`** — with a fake `plex_client`, verify children/leaf
  classification, `enumerate_parts` counts + summed sizes across a show.
- **`test_filter.py`** — the pure fuzzy/substring filter over a label list.
- **`test_downloader.py`** — stream a fake `requests` response into a temp dir:
  correct bytes written, atomic rename, skip-existing on size match, retry on
  injected failure, hierarchy path building, filename sanitization. Speed
  callback fires with plausible values.
- **`test_app_nav.py`** — Textual `App.run_test()` pilot over the mock client:
  arrow → Enter descends, ← restores level + filter, typing filters the list,
  → opens the confirm menu with the enumerated count. No live Plex calls.
- No test hits the real Plex network; plexapi and requests are mocked.

## Open questions / deferred

- Segmented download default count (start at 1; tune later).
- Whether to remember last-used server/out-dir in config (deferred to v2).
- Resume of a partially-downloaded `.part` across runs (v1 re-downloads;
  Range-resume deferred).
