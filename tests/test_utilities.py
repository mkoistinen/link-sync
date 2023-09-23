from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from link_sync.utilities import (
    gen_files_from_path,
    get_file_mtime,
    human_readable_transfer_speed,
    strfdelta,
)
import pytest


@pytest.mark.parametrize(
    "suffixes, num_files",
    [
        (None, 8),
        ((".gcode",), 4),
        (
            [
                ".gcode",
                ".txt",
            ],
            8,
        ),
        (
            {
                ".gcode",
                ".txt",
                ".exe",
            },
            8,
        ),
    ],
)
def test_gen_files_from_path(suffixes, num_files):
    """Test that gen_files_from_path works as expected."""
    file_hierarchy = Path(Path(__file__).parent, "data", "file_hierarchy")
    paths = gen_files_from_path(file_hierarchy, suffixes=suffixes)

    assert isinstance(paths, Iterator)

    paths = list(paths)
    assert len(paths) == num_files
    if suffixes:
        for path in paths:
            assert path.suffix in suffixes


def test_get_file_mtime():
    """Test that get_file_mtime works as expected."""
    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir, "tmp.txt")
        path.touch(exist_ok=True)
        m_time = get_file_mtime(path)
        assert int(m_time.timestamp()) == int(datetime.now().timestamp())


@pytest.mark.parametrize(
    "bytes, duration, expected_result",
    [
        (0, 1.0, "n/a B/sec."),
        (100, 0.0, "∞ B/sec."),
        (100, 1.0, "100.0 B/sec."),
        (100, 2.0, "50.0 B/sec."),
        (2000, 1.0, "2.0 KB/sec."),
        (2000, 2.0, "1,000.0 B/sec."),
        (10_000, 1.0, "9.8 KB/sec."),
        (100_000, 1.0, "97.7 KB/sec."),
        (2_000_000, 1.0, "1.9 MB/sec."),
        (30_000_000, 1.0, "28.6 MB/sec."),
        (400_000_000, 1.0, "381.5 MB/sec."),
        (5_000_000_000, 1.0, "4.7 GB/sec."),
    ],
)
def test_human_readable_transfer_speed(bytes, duration, expected_result):
    """Test that human_readable_transfer_speed works as expected."""
    result = human_readable_transfer_speed(bytes, duration)
    assert result == expected_result


@pytest.mark.parametrize(
    "seconds, output",
    (
        (0.0, "0h 0m 0.0s"),
        (1.1, "0h 0m 1.1s"),
        (100.24, "0h 1m 40.2s"),
        (1000.26, "0h 16m 40.3s"),
    ),
)
def test_strfdelta(seconds, output):
    """Test that strfdelta works as expected."""
    delta = timedelta(seconds=seconds)
    assert strfdelta(delta) == output
