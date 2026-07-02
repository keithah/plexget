# Releasing plexget

Releases are automated: publishing a GitHub Release triggers
`.github/workflows/release.yml`, which builds a standalone binary on each
platform (Linux x86_64, macOS arm64, macOS x86_64, Windows x86_64) with
PyInstaller and attaches them to the release.

## Cut a release

1. Make sure `main` is green (the CI workflow runs tests on every push/PR).
2. Bump the version in `pyproject.toml` (`[project].version`) and in
   `plexget/__init__.py` (`__version__`) — keep them in sync — then commit:

   ```bash
   git commit -am "chore: release v0.1.0"
   git push
   ```

3. Tag and publish the release (this is what triggers the binary build):

   ```bash
   gh release create v0.1.0 \
     --title "v0.1.0" \
     --notes-file docs/release-notes/v0.1.0.md
   ```

   (Or run `gh release create v0.1.0 --generate-notes` to auto-generate notes
   from merged PRs/commits.)

4. Watch the build:

   ```bash
   gh run watch
   ```

   When it finishes, the four binaries appear under **Assets** on the release
   page. Each is a single self-contained executable — no Python required to run
   it.

## Versioning

We follow [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.
Tags are `vMAJOR.MINOR.PATCH` (the leading `v` matters — the workflow reads
`github.event.release.tag_name`).

## Writing release notes

Keep a section per release in `CHANGELOG.md` (Keep a Changelog format). Copy the
relevant section into `docs/release-notes/<tag>.md` for the GitHub Release body,
or use `--generate-notes`.
