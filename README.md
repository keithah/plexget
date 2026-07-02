# plexget

An SFTP-style terminal browser and downloader for your Plex media.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Usage

```bash
plexget                 # PIN login, pick a server, browse
plexget --out ~/Media   # choose download directory
plexget --server Home   # skip the server picker
plexget --segments 4    # faster single-file downloads (parallel ranges)
plexget --pin           # force re-login
```

Navigation: **↑/↓** move · **type** to filter · **Enter** open folder / download file ·
**←** back · **→** download everything under the selected item.

Downloads keep the original file. Whole-folder downloads mirror the
Show/Season layout under your output directory. Files that already exist at the
right size are skipped.
