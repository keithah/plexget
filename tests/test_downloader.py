from pathlib import Path

import pytest

from plexget.downloader import (
    DownloadResult,
    Progress,
    download_part,
    run_jobs,
)
from plexget.nodes import PartRef


class FakeResponse:
    def __init__(self, chunks, status=200):
        self._chunks = chunks
        self.status_code = status
        self.headers = {"content-length": str(sum(len(c) for c in chunks))}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeSession:
    def __init__(self, chunks, fail_times=0):
        self._chunks = chunks
        self._fail_times = fail_times
        self.calls = 0

    def get(self, url, stream, timeout):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise ConnectionError("boom")
        return FakeResponse(self._chunks)


def part(name, size, rel_dir=()):
    return PartRef(url=f"http://s/{name}", filename=name, size=size, rel_dir=rel_dir)


def test_download_writes_bytes_and_renames(tmp_path):
    session = FakeSession([b"aaaa", b"bbbb"])
    dest = tmp_path / "f.mkv"
    progress = []
    ticks = iter([0.0, 1.0, 2.0])

    result = download_part(
        part("f.mkv", 8),
        dest,
        session=session,
        on_progress=progress.append,
        now=lambda: next(ticks),
    )

    assert result is True
    assert dest.read_bytes() == b"aaaabbbb"
    assert not dest.with_suffix(".mkv.part").exists()
    assert progress[-1].done == 8
    assert progress[-1].total == 8


def test_download_skips_existing_same_size(tmp_path):
    dest = tmp_path / "f.mkv"
    dest.write_bytes(b"aaaabbbb")  # 8 bytes
    session = FakeSession([b"XXXX"])

    result = download_part(part("f.mkv", 8), dest, session=session)

    assert result is False
    assert session.calls == 0
    assert dest.read_bytes() == b"aaaabbbb"  # untouched


def test_run_jobs_sets_index_and_count(tmp_path):
    session = FakeSession([b"aa"])
    seen = []
    run_jobs(
        [part("a.mkv", 2), part("b.mkv", 2)],
        tmp_path,
        mirror=False,
        session=session,
        on_progress=seen.append,
    )
    counts = {(p.index, p.count) for p in seen}
    assert (1, 2) in counts
    assert (2, 2) in counts


def test_run_jobs_retries_then_succeeds(tmp_path):
    session = FakeSession([b"aa"], fail_times=1)
    result = run_jobs([part("a.mkv", 2)], tmp_path, mirror=False, session=session)
    assert len(result.succeeded) == 1
    assert result.failed == []
    assert session.calls == 2  # 1 fail + 1 success


def test_run_jobs_records_failure_after_retries(tmp_path):
    session = FakeSession([b"aa"], fail_times=99)
    result = run_jobs(
        [part("a.mkv", 2)], tmp_path, mirror=False, session=session, retries=1
    )
    assert result.succeeded == []
    assert len(result.failed) == 1
    assert result.failed[0][0].filename == "a.mkv"
