from pathlib import Path

from plexget.downloader import download_part_segmented
from plexget.nodes import PartRef


class RangeResponse:
    def __init__(self, data):
        self._data = data
        self.status_code = 206

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class RangeSession:
    """Serves byte ranges out of a fixed payload."""

    def __init__(self, payload):
        self.payload = payload
        self.ranges = []

    def get(self, url, stream, timeout, headers=None):
        rng = headers["Range"]  # "bytes=start-end"
        spec = rng.split("=")[1]
        start, end = spec.split("-")
        start, end = int(start), int(end)
        self.ranges.append((start, end))
        return RangeResponse(self.payload[start : end + 1])


def test_segmented_reassembles_full_file(tmp_path):
    payload = bytes(range(256)) * 8  # 2048 bytes
    session = RangeSession(payload)
    dest = tmp_path / "big.mkv"

    ok = download_part_segmented(
        PartRef("http://s/big.mkv", "big.mkv", len(payload)),
        dest,
        session=session,
        segments=4,
    )

    assert ok is True
    assert dest.read_bytes() == payload
    assert len(session.ranges) == 4
    assert not dest.with_name("big.mkv.part").exists()


def test_segmented_skips_existing(tmp_path):
    payload = b"abcd" * 4
    dest = tmp_path / "f.mkv"
    dest.write_bytes(payload)
    session = RangeSession(payload)

    ok = download_part_segmented(
        PartRef("http://s/f.mkv", "f.mkv", len(payload)),
        dest,
        session=session,
        segments=4,
    )
    assert ok is False
    assert session.ranges == []
