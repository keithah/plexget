"""Generate the README demo GIF, fully headless (no browser/ttyd).

Drives `plexget --demo` through Textual's test pilot, exports an SVG per step,
renders each to PNG with `rsvg-convert` (librsvg), and assembles an animated GIF
with per-frame durations via Pillow.

Regenerate:
    .venv/bin/pip install pillow           # once
    brew install librsvg                    # once (provides rsvg-convert)
    .venv/bin/python docs/gen_demo.py       # writes docs/demo.gif
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from plexget.app import PlexGetApp
from plexget.demo import demo_nodes, demo_runner

HERE = Path(__file__).resolve().parent
OUT_GIF = HERE / "demo.gif"
PNG_WIDTH = 900


async def _capture(pilot, app, frames, tmp, ms):
    """Snapshot the current screen -> SVG -> PNG, holding it for `ms`."""
    await pilot.pause()
    idx = len(frames)
    svg_path = tmp / f"f{idx:03d}.svg"
    png_path = tmp / f"f{idx:03d}.png"
    svg_path.write_text(app.export_screenshot(title="plexget --demo"))
    subprocess.run(
        ["rsvg-convert", "-w", str(PNG_WIDTH), "-o", str(png_path), str(svg_path)],
        check=True,
    )
    frames.append((png_path, ms))


async def build_frames(tmp: Path):
    app = PlexGetApp(demo_nodes(), download_runner=demo_runner)
    frames: list[tuple[Path, int]] = []

    async def snap(ms):
        await _capture(pilot, app, frames, tmp, ms)

    async def progress_frames(n, per=180, ms=140):
        for _ in range(n):
            await asyncio.sleep(per / 1000)
            await snap(ms)

    async with app.run_test(size=(92, 28)) as pilot:
        await snap(1600)                       # top-level libraries
        await pilot.press("enter"); await snap(1300)     # -> TV Shows
        await pilot.press("down"); await snap(450)
        await pilot.press("down"); await snap(1100)      # highlight a show
        await pilot.press("enter"); await snap(1100)     # -> seasons
        await pilot.press("enter"); await snap(1100)     # -> episodes
        for ch in "e03":                       # type-to-filter
            await pilot.press(ch); await snap(420)
        await snap(1200)
        await pilot.press("enter")             # download the episode
        await progress_frames(8)               # live progress bar
        await snap(1900)                       # "Done"
        await pilot.press("backspace")
        await pilot.press("backspace")
        await pilot.press("backspace"); await snap(500)  # clear filter
        await pilot.press("left"); await snap(1100)      # back to seasons
        await pilot.press("right"); await snap(2200)     # confirm folder download
        await pilot.press("y")
        await progress_frames(7)               # folder download progress
        await snap(1900)

    return frames


def main():
    tmp = Path(tempfile.mkdtemp(prefix="plexget-demo-"))
    try:
        frames = asyncio.run(build_frames(tmp))
        images = [Image.open(p).convert("RGB") for p, _ in frames]
        durations = [ms for _, ms in frames]
        # normalize all frames to the first frame's size (defensive)
        base = images[0].size
        images = [im if im.size == base else im.resize(base) for im in images]
        images[0].save(
            OUT_GIF,
            save_all=True,
            append_images=images[1:],
            duration=durations,
            loop=0,
            optimize=True,
            disposal=2,
        )
        print(f"wrote {OUT_GIF} ({len(images)} frames, {sum(durations) / 1000:.1f}s)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
