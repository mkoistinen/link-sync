from datetime import datetime, timedelta
from functools import lru_cache
import math
from pathlib import Path
from string import Formatter
from typing import Generator, Iterable, Optional, Union


def gen_files_from_path(
    local_path: Path, suffixes: Optional[Iterable[str]] = None
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
    for path_obj in local_path.glob("*"):
        if (
            path_obj.is_file()
            and not path_obj.name.startswith(".")
            and (not suffixes or path_obj.suffix in suffixes)
        ):
            yield path_obj
        elif path_obj.is_dir() and not path_obj.name.startswith("."):
            yield from gen_files_from_path(path_obj, suffixes=suffixes)


@lru_cache(maxsize=1000)
def get_file_mtime(local_file: Path) -> datetime:
    """
    Return the modification time-stamp for the given file as a datetime in UTC.

    This is cached so that we're not hitting the filesystem N times per file
    where N is the number of idle printers.
    """
    return datetime.fromtimestamp(local_file.stat().st_mtime)


class Timer:
    """Context manager to measure duration of the execution of the body."""

    def __init__(self):
        """Initialize the new timer instance."""
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        """Start the context manager."""
        self.start_time = datetime.now()
        return self

    def __exit__(self, *args):
        """End the context manager."""
        self.end_time = datetime.now()

    @property
    def duration(self) -> Union[timedelta, None]:
        """Return the duration as a timedelta."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return datetime.now() - self.start_time
        else:
            return None

    @property
    def seconds(self) -> Union[float, None]:
        """Return the duration as seconds."""
        if elapsed := self.duration:
            return elapsed.total_seconds()
        return None


def strfdelta(delta: timedelta, fmt: str = "{H:01}h {M:01}m {S:01.1f}s"):
    """
    Format a timedelta instance to string.

    Adapted from: https://stackoverflow.com/a/63198084 by `tomatoeshift`

    Parameters
    ----------
    delta : timedelta
        A timedelta instance.
    fmt : str, default: "{H:02}h {M:02}m {S:01.0f}s"
        A format string.
    """
    # Convert timedelta to float seconds.
    remainder = delta.total_seconds()

    f = Formatter()
    desired_fields = [field_tuple[1] for field_tuple in f.parse(fmt)]
    possible_fields = ("Y", "m", "W", "D", "H", "M", "S", "mS", "µS")
    constants = {
        "Y": 86400 * 365.24,
        "m": 86400 * 30.44,
        "W": 604800,
        "D": 86400,
        "H": 3600,
        "M": 60,
        "S": 1,
        "mS": 1 / pow(10, 3),
        "µS": 1 / pow(10, 6),
    }
    values = {}
    for field in possible_fields:
        if field in desired_fields and field in constants:
            Quotient, remainder = divmod(remainder, constants[field])
            if (
                field == "S"
                and "mS" not in desired_fields
                and "µS" not in desired_fields
            ):
                values[field] = Quotient + remainder
            else:
                values[field] = int(Quotient)
    return f.format(fmt, **values)


def human_readable_transfer_speed(bytes: int, duration: float) -> str:
    """Return the transfer speed in human readable binary units."""
    UNITS = "KMGTP"

    if bytes and duration:
        raw_speed = bytes / duration
        magnitude = math.floor(math.log(raw_speed, 1024))
        # magnitude = math.floor(math.pow(raw_speed, 1 / 1024))
        if magnitude == 0:
            return f"{raw_speed:,.1f} B/sec."
        else:
            return (
                f"{raw_speed / math.pow(1024, magnitude):,.1f} "
                f"{UNITS[magnitude - 1]}B/sec."
            )
    elif duration:
        return "n/a B/sec."
    else:
        return "∞ B/sec."
