from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Generator, Iterable, Optional


def gen_files_from_path(local_path: Path,
                        suffixes: Optional[Iterable[str]] = None
                        ) -> Generator[Path, None, None]:
    """
    Yield filenames from given `local_path`, recursing through sub-directories.

    Hidden files and directories are always ignored.

    Parameters
    ----------
    local_path : Path
        The path from which to start looking inside of.
    suffixes : Iterable of str or None, default None
        Optional. If provided, the files returned must have a suffix contained
        in `suffixes`. If not provided, all file objects (except hidden ones)
        will be returned.

    Yields
    ------
    Path
        A file found within the given `local_path`.
    """
    for path_obj in local_path.glob('*'):
        if (
            path_obj.is_file()
            and not path_obj.name.startswith('.')
            and (not suffixes or path_obj.suffix in suffixes)
        ):
            yield path_obj
        elif (
            path_obj.is_dir()
            and not path_obj.name.startswith('.')
        ):
            yield from gen_files_from_path(path_obj, suffixes=suffixes)


@lru_cache(maxsize=1000)
def get_file_mtime(local_file: Path) -> datetime:
    """
    Return the modification time-stamp for the given file as a datetime in UTC.

    This is cached so that we're not hitting the filesystem N times per file
    where N is the number of idle printers.
    """
    return datetime.fromtimestamp(local_file.stat().st_mtime)
