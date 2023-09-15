import argparse
from concurrent.futures import as_completed, ThreadPoolExecutor
from itertools import chain
import logging
from multiprocessing import cpu_count
from pathlib import Path
from typing import Iterable, Optional, Set, Union

from rich import print

from .printers import IDLE_STATES, Printer
from .utilities import gen_files_from_path


__VERSION__ = "0.2.2"


logger = logging.getLogger(__name__)


def _sync(
    *,
    printer: Printer,
    local_files: Iterable[Path],
    relative_to_path: Path,
    destination_path: Path,
    ignore_state: bool = False,
    execute: bool = False,
) -> Printer:
    """
    Perform actions to synchronize the local_files with the printer.

    This is not called directly, it is called by the ThreadPoolExecutor from
    the `process()` function.

    The actions performed:
    - prune excess files
    - upload missing or stale files

    Parameters
    ----------
    printer : Printer instance
        The 3D Printer that will be actioned.
    local_files : iterable of Path
        The local iterable of file paths to sync to the printer.
    destination_path : Path
        The printer path to sync against.
    relative_to_path : Path
        If provided, prunes the local_file paths to this parent path.
    ignore_state : bool, default False
        If True, all printers, including those printing will be considered for
        file operations.
    execute : bool, default False
        If True, attempt to perform the changes on the remote printer.
        If False, print out steps that would be taken.
    """
    # Do not disturb busy printers with heavy file operations.
    printer_state = printer.get_state()
    if printer_state not in IDLE_STATES and not ignore_state:
        print(
            f"[yellow][bold]{printer.name}[/bold] is currently in state "
            f"{printer_state} and will not be accessed.[/yellow]"
        )
        return printer

    # Get an iterable of the missing files for this printer...
    excess_files: Set[Path] = printer.get_excess_files(
        local_files=local_files,
        destination_path=destination_path,
        relative_to_path=relative_to_path,
    )
    missing_files = set(
        printer.gen_missing_or_stale_files(
            local_files=local_files,
            destination_path=destination_path,
            relative_to_path=relative_to_path,
        )
    )

    # Print out what we're going to do (if `execute==True`)
    num_excess = len(excess_files)
    num_upload = len([f for f in missing_files if f.is_stale is False])
    num_stale = len([f for f in missing_files if f.is_stale is True])
    verb = "is" if num_excess == 1 else "are"
    plural_excess = "s" if num_excess != 1 else ""
    plural_stale = "s" if num_stale != 1 else ""
    print(
        f"[bold]{printer.name}[/bold] - There {verb} [bold]{num_excess} file"
        f"{plural_excess} to delete[/bold], [bold]{num_upload} missing to "
        f"upload[/bold] and [bold]{num_stale} stale file{plural_stale} to "
        f"refresh[/bold].",
        flush=True,
    )
    for missing in missing_files:
        print(
            f"To be [bold]{'refreshed' if missing.is_stale else 'uploaded'}"
            f"[/bold] to [bold]{printer.name}[/bold]: [magenta]"
            f"{missing.local_path}[/magenta] => [magenta]"
            f"{missing.remote_path}[/magenta].",
            flush=True,
        )
    for excess in excess_files:
        print(
            f"To be [bold]deleted[/bold] from [bold]{printer.name}[/bold]: "
            f"[magenta]{excess}[/magenta].",
            flush=True,
        )
    if not execute:
        return printer

    # Prune Excess Files
    for excess_path in excess_files:
        if node := printer.storage.get_node_for_display_path(excess_path):
            if printer.storage.delete_file(node):
                print(
                    f"File [magenta]{excess_path}[/magenta] [green]"
                    f"successfully [bold]deleted[/bold][/green] from printer: "
                    f"[bold]{printer.name}[/bold].",
                    flush=True,
                )
            else:
                print(
                    f"File [magenta]{excess_path}[/magenta] [red]failed to be "
                    f"deleted[/red] from printer: [bold]{printer.name}"
                    f"[/bold].",
                    flush=True,
                )
        else:
            print(
                f'File "[magenta]{excess_path}[/magenta] [yellow]does not '
                f"exist[/yellow] on printer: [bold]{printer.name}[/bold]",
                flush=True,
            )

    # Upload Missing Files
    for missing in missing_files:
        if missing.is_stale:
            if file_node := printer.storage.get_node_for_display_path(
                missing.remote_path
            ):
                printer.storage.delete_file(file_node)
        if printer.storage.upload_file(
            local_path=missing.local_path, remote_path=missing.remote_path
        ):
            verb = "refreshed" if missing.is_stale else "uploaded"
            print(
                f"File [magenta]{missing.local_path}[/magenta] [green]"
                f"successfully [bold]{verb}[/bold][/green] to printer: "
                f"[bold]{printer.name}[/bold].",
                flush=True,
            )
        else:
            verb = "refresh" if missing.is_stale else "upload"
            print(
                f"File [magenta]{missing.local_path}[/magenta] [red]failed to "
                f"{verb}[/red] to printer: [bold]{printer.name}[/bold].",
                flush=True,
            )

    # Reload the internal FileNode graph.
    printer.storage.reload()
    return printer


def process(
    *,
    config_path: Union[Path, str],
    included_printers: Optional[Iterable[str]],
    excluded_printers: Optional[Iterable[str]],
    source_path: Union[Path, str],
    relative_to_path: Optional[Union[Path, str]],
    destination_path: Optional[Union[Path, str]],
    suffixes: Optional[Iterable[str]] = None,
    ignore_state: bool = False,
    execute: bool = False,
) -> bool:
    """
    Given a configuration, start syncing files across all printers.

    Parameters
    ----------
    config_path : Path or str
        The path to the JSON or YAML printer configuration file.
    included_printers : Iterable of str or None, default None
        Optional. If set, provide a list of printers by name to process,
        excluded any printers in the configuration not provided here.
    excluded_printers : Iterable of str or None, default None
        Optional. If set and `printers` is not in use, process all of the
        printers in the configuration except those provided here.
    source_path : Path or str
        The location of local file heirarchy to sync to all configured
        printers. For example, `/home/fred/source_gcode/usb/`
    relative_to_path : Path or str
        If provided, prunes the local_file paths to this parent path.
    destination_path : Path or str
        The printer path to sync against.
    suffixes : iterable of str or None, default None
        Optional. An iterable of string file extensions. This will limit sync
        operations to only files that end with any of the given extensions. If
        none provided, will be set to contain only ".gcode".
    ignore_status : bool, default False
        If True, all printers, including those in any of the busy states will
        be processed. Use with caution as some printers or pre-release firmware
        may fail printing during heavy API usage.
    execute : bool, default False
        If False, only report what sorts of actions would be taken. If True
        perform them.

    Returns
    -------
    bool
        True on successful completion.
    """
    # Convert any given strings to Path instances.
    if not isinstance(source_path, Path):
        source_path = Path(source_path)
    source_path = source_path.expanduser().resolve()

    if relative_to_path:
        if isinstance(relative_to_path, Path):
            relative_to_path = relative_to_path.expanduser().resolve()
        else:
            relative_to_path = Path(relative_to_path).expanduser().resolve()
    else:
        relative_to_path = source_path

    if destination_path:
        if not isinstance(destination_path, Path):
            destination_path = Path(destination_path)
    else:
        destination_path = Path("")

    if config_path and not isinstance(config_path, Path):
        config_path = Path(config_path)

    if suffixes is None:
        suffixes = [".gcode"]

    all_printers = set(Printer.from_config(config_path))

    if included_printers:
        # Flatten and nested iterables and lower-case the strings.
        included_printers = set(map(str.lower, set(chain(*included_printers))))
        printers = {
            p for p in all_printers if p.name.lower() in included_printers
        }
    elif excluded_printers:
        # Flatten and nested iterables and lower-case the strings.
        excluded_printers = set(map(str.lower, set(chain(*excluded_printers))))
        printers = {
            p for p in all_printers if p.name.lower() not in excluded_printers
        }
    else:
        printers = all_printers

    source_path = source_path.expanduser().resolve()
    local_files = set(
        gen_files_from_path(local_path=Path(source_path), suffixes=suffixes)
    )

    if execute:
        print("The following actions will be taken.")
    else:
        print(
            "Dry run only. These actions will [bold]not[/bold] be performed. "
            "(use the [bold]-g/--execute[/bold] option to perform these "
            "actions.)"
        )

    try:
        with ThreadPoolExecutor(max_workers=cpu_count()) as pool:
            futures = {
                pool.submit(
                    _sync,
                    printer=printer,
                    destination_path=destination_path,
                    execute=execute,
                    ignore_state=ignore_state,
                    local_files=local_files,
                    relative_to_path=relative_to_path,
                )
                for printer in printers
            }
    except Exception:
        return False
    else:
        successes = set()
        for future in as_completed(futures):
            try:
                printer = future.result()
            except Exception:
                logger.exception("A thread raised an exception.")
                successes.add(False)
            else:
                print(f"[bold]{printer.name}[/bold] complete.")
                successes.add(True)

    return all(successes)


def main():
    """Parse input and pass control to `process()`."""
    # Parse any command line options
    parser = argparse.ArgumentParser("link_sync")
    parser.add_argument(
        "-c",
        "--config",
        action="store",
        dest="config_path",
        required=False,
        default="printers.json",
        help=(
            "Path to a YAML or JSON file containing the configuration of all "
            "printers. Default is `printers.yml` in the current "
            "working directory."
        ),
    )
    parser.add_argument(
        "-p",
        "--printer",
        action="append",
        nargs="*",
        dest="included_printers",
        required=False,
        help=(
            "Explicitly name printers to INCLUDE for processing. By default, "
            "all idle (see the `--ignore-state` option) printers found in the "
            "will configuration be processed."
        ),
    )
    parser.add_argument(
        "-x",
        "--exclude",
        action="append",
        nargs="*",
        dest="excluded_printers",
        required=False,
        help=(
            "Explicitly name printers to EXCLUDE from processing. By "
            "default, all idle (see the `--ignore-state option) printers "
            "found in the configuration will be processed. This option will "
            "be ignored if the `--printer` option is used."
        ),
    )
    parser.add_argument(
        "-s",
        "--source",
        action="store",
        dest="source_path",
        required=True,
        help="The local path to the root of the files that should be synced.",
    )
    parser.add_argument(
        "-d",
        "--destination",
        action="store",
        dest="destination_path",
        required=False,
        default=None,
        help=(
            "The relative path within the printers' storage where the source "
            "files should be synchronized. Default is the root of the "
            "printers' storage."
        ),
    )
    parser.add_argument(
        "-r",
        "--relative-to",
        action="store",
        dest="relative_to_path",
        required=False,
        default=None,
        help=(
            "If provided, the SOURCE_PATH file paths will consider only the "
            "portion of the path that is relative to this given path. If not "
            "provided, it is set to the SOURCE_PATH itself."
        ),
    )
    parser.add_argument(
        "-g",
        "--go",
        action="store_true",
        default=False,
        dest="execute",
        help="Make the changes (do not do a dry-run).",
    )
    parser.add_argument(
        "--ignore-state",
        action="store_true",
        dest="ignore_state",
        required=False,
        default=False,
        help=(
            "If set, all printers, including busy printers, will be "
            "processed. Use with caution as some printers may experience "
            "print failures when printing and API calls are received "
            "and processed."
        ),
    )
    options = parser.parse_args()
    process(**vars(options))


if __name__ == "__main__":
    main()
