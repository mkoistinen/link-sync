from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from link_sync.utilities import gen_files_from_path, get_file_mtime
import pytest


@pytest.mark.parametrize(
    'suffixes, num_files', [
        (None, 8),
        (('.gcode', ), 4),
        (['.gcode', '.txt', ], 8),
        ({'.gcode', '.txt', '.exe', }, 8)
    ]
)
def test_gen_files_from_path(suffixes, num_files):
    """Test that gen_files_from_path works as expected."""
    file_hierarchy = Path(Path(__file__).parent, 'data', 'file_hierarchy')
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
        path = Path(temp_dir, 'tmp.txt')
        path.touch(exist_ok=True)
        m_time = get_file_mtime(path)
        assert int(m_time.timestamp()) == int(datetime.now().timestamp())
