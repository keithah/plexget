from pathlib import Path

from plexget.downloader import build_dest, sanitize_filename
from plexget.nodes import PartRef


def test_sanitize_strips_separators_and_illegal_chars():
    assert sanitize_filename("a/b:c*?.mkv") == "a_b_c__.mkv"
    assert sanitize_filename("../evil") == ".._evil"


def test_sanitize_never_empty():
    assert sanitize_filename("") == "download"
    assert sanitize_filename("///") != ""


def test_build_dest_flat():
    p = PartRef("u", "S01E01.mkv", 10, rel_dir=("Severance", "Season 01"))
    assert build_dest(Path("/out"), p, mirror=False) == Path("/out/S01E01.mkv")


def test_build_dest_mirrored():
    p = PartRef("u", "S01E01.mkv", 10, rel_dir=("Severance", "Season 01"))
    assert build_dest(Path("/out"), p, mirror=True) == Path(
        "/out/Severance/Season 01/S01E01.mkv"
    )


def test_build_dest_mirrored_sanitizes_dirs():
    p = PartRef("u", "f.mkv", 10, rel_dir=("Se/ve:re", ""))
    assert build_dest(Path("/out"), p, mirror=True) == Path("/out/Se_ve_re/f.mkv")
