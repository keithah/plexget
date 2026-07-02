# plexget

[![CI](https://github.com/keithah/plexget/actions/workflows/ci.yml/badge.svg)](https://github.com/keithah/plexget/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

An **SFTP-style terminal browser and downloader for your Plex media.** Log in
with your Plex account, pick a server, arrow-key your way through your libraries,
and pull down a single episode/movie — or a whole season/show — with a live
progress bar.

```
┌─ plexget ─────────────────────────┐
│ Severance                         │
│ > Season 1                        │
│   Season 2                        │
│    [→ download entire show]       │
└───────────────────────────────────┘
filter: sev_        ↓ S01E01.mkv  42%  38.6 MB/s  ETA 0:31
```

## Features

- **PIN login** via `plex.tv/link` — works with 2FA, no password typed into the
  tool; the token is cached so you only do it once.
- **Browse** TV (Show → Season → Episode) and Movie libraries with an arrow-key
  TUI and **type-to-filter**.
- **Download** a single episode/movie (**Enter**) or **everything under a
  folder** (**→**, with a "N files, X GB?" confirmation).
- **Original files**, streamed with a live **speed (MB/s) + ETA** readout.
- **`--segments N`** parallel-range mode for faster single-file downloads.
- Whole-folder downloads mirror the `Show/Season/…` layout; already-downloaded
  files (matching size) are skipped; partial files are cleaned up on interrupt.

## Install

### Download a binary (no Python needed)

Grab the standalone executable for your platform from the
[latest release](https://github.com/keithah/plexget/releases/latest):

| Platform | Asset |
|----------|-------|
| Linux (x86_64) | `plexget-linux-x86_64` |
| macOS (Apple Silicon) | `plexget-macos-arm64` |
| macOS (Intel) | `plexget-macos-x86_64` |
| Windows (x86_64) | `plexget-windows-x86_64.exe` |

```bash
chmod +x plexget-macos-arm64
./plexget-macos-arm64
```

> macOS may quarantine the download — if it's blocked, run
> `xattr -d com.apple.quarantine ./plexget-macos-arm64` (or allow it in
> System Settings → Privacy & Security).

### From source

```bash
git clone https://github.com/keithah/plexget
cd plexget
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/plexget
```

## Usage

```bash
plexget                 # PIN login, pick a server, browse
plexget --out ~/Media   # choose the download directory
plexget --server Home   # skip the server picker (name match, case-insensitive)
plexget --segments 4    # faster single-file downloads (parallel byte ranges)
plexget --pin           # force re-login (ignore the cached token)
```

### Keys

| Key | Action |
|-----|--------|
| ↑ / ↓ | Move selection |
| *type* | Filter the current list |
| Enter | Open a folder, or download the selected file |
| ← | Back up a level |
| → | Download everything under the selected item (with confirmation) |
| q | Quit |

## How it works

Auth uses `python-plexapi`'s PIN login; the resulting token and a stable client
id are cached at your platform config dir (`~/.config/plexget/auth.json` on
Linux/macOS). Navigation and metadata come from the Plex API; downloads stream
the original file's `/library/parts/…` URL directly from your server with
`requests`. All blocking network work runs on Textual worker threads so the UI
never freezes.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest      # full test suite (network fully mocked)
```

Releases and the binary-build pipeline are documented in
[RELEASING.md](RELEASING.md); changes in [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE)
