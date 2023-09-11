from datetime import datetime, timedelta
from enum import auto, Enum
import json
import logging
from pathlib import Path
from typing import Generator, Iterable, List, Set

import yaml

from .storage import FileNode, Storage


logger = logging.getLogger(__name__)


class PrinterException(Exception):
    """An exception specific to Printer instances."""


class State(Enum):
    """Enumeration of known printer states."""

    BUSY = auto()
    FINISHED = auto()
    STOPPED = auto()
    IDLE = auto()
    PAUSED = auto()
    PRINTING = auto()
    READY = auto()


# It should be safe to interact with the printer's API while in these states.
IDLE_STATES = {
    State.FINISHED,
    State.IDLE,
    State.READY
}


class MissingOrStaleFile:
    """
    Lightweight class to represent a missing or stale file.

    Parameters
    ----------
    local_path : Path
        The local path of the missing or stale file.
    remote_path : Path
        The remote path of the missing or stale file.
    is_stale : bool
        If True, the file is returned because it is out-of-date.
    """

    __slots__ = ('local_path', 'remote_path', 'is_stale')

    def __init__(self, local_path: Path, remote_path: Path,
                 is_stale: bool):
        self.local_path = local_path
        self.remote_path = remote_path
        self.is_stale = is_stale


class Printer:
    """
    Encapsulate a Printer instance.

    Parameters
    ----------
    host : str
        The hostname or IP address of the printer.
    name : str
        The given name of the printer.
    password : str
        The password of the printer.
    printer_type : str
        The model of the printer (MK4, XL, etc.)
    username : str
        The username of the printer.
    """

    @classmethod
    def from_config(cls, config_file_path: Path | str
                    ) -> List['Printer']:
        """
        Return a list of Printer instances from the given configuation file.

        JSON and YML configuration files are supported.

        Parameters
        ----------
        config_file_path: Path or str
            The path to the configuration file which should be either JSON or
            YAML formatted.

        Returns
        -------
        list of Printer
            The list of Printer instances found in the configuration file.

        Raises
        ------
        PrinterException
            If the given `config_file_path` does not have a suffix matching
            {'.json', '.jso', '.jsn', '.yaml', or '.yml}
        FileNotFoundError
            If the given `config_file_path` does not seem to exist.
        """
        if not isinstance(config_file_path, Path):
            config_file_path = Path(config_file_path)
        if config_file_path.exists():
            with open(config_file_path, mode='r') as config_file:
                if config_file_path.suffix.lower() in ['.jso', '.jsn', '.json']:  # noqa
                    printer_list = json.load(config_file)
                elif config_file_path.suffix.lower() in ['.yml', '.yaml']:
                    """Do YAML loading here."""
                    printer_list = yaml.safe_load(config_file)
                else:
                    raise PrinterException(
                        'Only JSON and YAML configuration files are supported.'
                    )
        else:
            raise FileNotFoundError(
                'The given `config_file_path` does not exist.')

        return [
            cls(name=name, **config)
            for name, config in printer_list.items()
        ]

    def __init__(self, *, host: str, name: str, password: str,
                 printer_type: str, username: str):
        self.name = name
        self.printer_type = printer_type
        self.storage = Storage(name=self.name,
                               host=host,
                               username=username,
                               password=password)

    def __str__(self):
        """Return a human-consumable representation for this printer."""
        return f'Printer: "{self.name}"'

    def __repr__(self):
        """Return an instance representation for this printer."""
        return f"<{str(self)}>"

    def get_state(self) -> State | None:
        """Get the printer's status from its API."""
        response = self.storage.api.status_response()
        if response.success and isinstance(response.payload, dict):
            try:
                state = response.payload['printer']['state'].upper()
            except Exception:
                logger.warning(f"Unable to get printer state for {self}'s.")
                return None
            else:
                try:
                    printer_state = State[state]
                except KeyError:
                    logger.warning(f'Unrecognized printer State: "{state}"')
                else:
                    return printer_state

    def gen_missing_or_stale_files(
        self,
        *,
        destination_path: Path,
        local_files: Iterable[Path],
        relative_to_path: Path,
    ) -> Generator[MissingOrStaleFile, None, None]:
        """
        Yield local files that are not present on the printer.

        Files that are present, but "stale" are also yielded. A stale file is
        one that is more than 60 seconds older that the timestamp of the
        corresponding local file.

        Parameters
        ----------
        destination_path : Path
            The path to consider the "root" on the remote storage.
        local_files : iterable of Path
            An iterable of Path instances representing the local files.
        relative_to_path : Path
            Prunes the local_file paths to this parent path.

        Yields
        ------
        MissingOrStaleFile
            Information about the missing or stale file.
        """
        for local_file in local_files:
            relative_file = local_file.relative_to(relative_to_path)
            if destination_path:
                remote_path = Path(self.storage.root_node.full_display_path,
                                   destination_path, relative_file)
            else:
                remote_path = Path(self.storage.root_node.full_display_path,
                                   relative_file)
            if node := self.storage.get_node_for_display_path(remote_path):
                # Looks like the file already exists, check if it is stale.
                # Stale requires that the remote_file be more than 60 seconds
                # older than the local file.
                local_mt = datetime.fromtimestamp(
                    local_file.stat().st_mtime)
                if node_mt := node.m_datetime:
                    if local_mt > node_mt + timedelta(seconds=60):
                        yield MissingOrStaleFile(
                            local_path=local_file,
                            remote_path=remote_path,
                            is_stale=True
                        )
            else:
                yield MissingOrStaleFile(
                    local_path=local_file,
                    remote_path=remote_path,
                    is_stale=False
                )

    def get_excess_files(self,
                         *,
                         destination_path: Path,
                         local_files: Iterable[Path],
                         relative_to_path: Path
                         ) -> Set[Path]:
        """
        Return the set of nodes that are in excess of what is in `local_files`.

        Parameters
        ----------
        destination_path : Path
            The remote path to start from to consider for excess files.
        local_files : iterable of Path
            The local files to compare when checking for remote excess files.
        relative_to_path : Path
            Prunes the local_file paths to this parent path.

        Returns
        -------
        Set of Path
            The set of files that are on the printer but are not in the set of
            local files.
        """
        # If not given an absolute path, make it relative to the root_node.
        if destination_path.absolute:
            dest_node_path = str(destination_path)
        else:
            dest_node_path = (f'{self.storage.root_node.full_display_path}/'
                              f'{destination_path}')

        if dest_node := self.storage.get_node_for_display_path(dest_node_path):
            # Start with all the nodes (as their full_display_names).
            excess_nodes = set(
                node.full_display_path
                for node in self.storage.gen_nodes()
                if (
                    node.full_short_path.startswith(dest_node.full_short_path)
                    and not node.is_dir
                )
            )
        else:
            return set()

        # Build the set of nodes that represent local_files.
        remote_nodes: Set[FileNode] = set()
        for local_file in local_files:
            relative_file = local_file.relative_to(relative_to_path)
            remote_path = Path(destination_path, relative_file)
            if node := self.storage.get_node_for_display_path(remote_path):
                remote_nodes.add(node)

        # Eliminate the remote_nodes that represent local files.
        for node in remote_nodes:
            try:
                excess_nodes.remove(node.full_display_path)
            except KeyError:
                pass

        # Return remaining nodes as tuples of short and display Paths.
        return {Path(node) for node in excess_nodes}
