# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-07-02

Initial release.

### Added
- Plex account login via the PIN / `plex.tv/link` flow, with the token cached
  locally so subsequent runs skip the prompt.
- Server picker for accounts with access to multiple Plex servers.
- Textual arrow-key TUI for browsing TV (Show → Season → Episode) and Movie
  libraries, with type-to-filter.
- Download a single episode/movie (Enter) or an entire show/season/movie folder
  (→ with a "N files, X GB?" confirmation).
- Streamed downloads of the original file with a live progress bar showing
  transfer speed (MB/s) and ETA.
- Optional `--segments N` parallel-range mode for faster single-file downloads.
- Whole-folder downloads mirror the `Show/Season/…` layout under `--out`;
  already-downloaded files (matching size) are skipped.
- Safety: filenames sanitized (no path traversal), partial `.part` files removed
  on interruption, one download at a time, retry on transient failure.

[0.1.0]: https://github.com/keithah/plexget/releases/tag/v0.1.0
