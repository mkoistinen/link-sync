# Link Sync

## Purpose

The goal of this project is to sync gcode files from a local "master" directory
to any number of Prusa printers on the local network running PrusaLink when
they are idle, simultaneously.

Transfering files is tediously slow, so the idea is to sync several printers
all at once. This is a powerful workflow for farm operators who may have a
new model that replaces an older one and negates the need to send it
individually to every printer, or, to manually fetch their USB stick/other
to for updating at your local machine.

Also, by removing files that aren't in the local "master" directory, once off
prints are automatically cleaned up from a printer's USB stick.


## Theory of Operation

Locally, a "master" file structure is maintained containing all the GCode files
required at the target machines. Also, configuration file in either YAML or
JSON format is kept on the local machine that contains the connection details
for each printer.

The program reads the configuration file, instantiates printer instances, then
for the printers that aren't currently busy, a thread is spawned which is
responsible for check what files should be deleted from the printer, or copied
to the printer to bring it into sync with the local "master" file-structure.

These threads then operate simultaneously to bring all idle printers into sync
at roughly the same time.

Note that PrusaLink running on the printer refuses to delete a file that is
actively being printed. This is a good thing.

Being a command-line program, it would be easy to set up with `cron` to run
every hour on the hour from 7pm to 7am (overnight) to ensure that all printers
get synced/cleaned up from the previous day's run and ready to go for the
next day.


## Currently Implemented Features

Printers currently supported:

- [x] Prusa MK4 running firmware 5.0.0 RC1

TODO:

- [ ] Prusa XL
- [ ] Prusa Mini
- [ ] Prusa MK3


Features:

- [x] Add new files that were found in local source but not in remote storage.
- [x] Delete excess files not found in local source but are in remote storage.
- [x] Optionally operate on printers that are not idle.
- [x] Replace stale files that have a modification date more recent (> 60 sec.)
      than the same file on the remote storage.

TODO:

- [ ] Optionally, copy files that exist on a printer that are unique back to
      the local filesystem.

## Example usage

### Scenario

The author maintains a set of files on his local workstation's filesystem at:

    ~/master_farm_files/usb

Within this directory, he adds all his GCode organized into directories, if
he so desires. He knows that PrusaLink has limits on how long filepaths can be
on the printer, so he keeps the directories shallow and with reasonably short
names. For example a directory structure like this:

    ~/master_farm_files/usb/
        apple/
            prusament pla/
                apple_0.4n_0.15mm_PLA_MK4IS_4h52m.gcode
            prusament petg/
                apple_0.4n_0.15mm_PETG_MK4IS_4h58m.gcode
        banana/
            prusament pla/
                banana_0.4n_0.15mm_PLA_MK4IS_2h12m.gcode
            prusament petg/
                banana_0.4n_0.15mm_PETG_MK4IS_2h13m.gcode

The author has a bank of 4 Original Prusa MK4 printers. He creates a
configuration file `~/printers.yml` somewhere that contains their details
as follows:

``` yml
Ash:
    printer_type: MK4
    host: http://192.168.0.1
    username: maker
    password: password1
Bishop:
    printer_type: MK4
    host: http://192.168.0.2
    username: maker
    password: password2
Call:
    printer_type: MK4
    host: http://192.168.0.3
    username: maker
    password: password3
David:
    printer_type: MK4
    host: http://192.168.0.4
    username: maker
    password: password4
```

Then, the author creates a virtual Python environment and installs `link-sync`.

    ❯ pip install link-sync

This Python package installs a command line utility called `link-sync` which
can be used like so:

    ❯ link-sync --config ~/printers.yml --source ~/master_farm_files/usb --destination /usb/

The program will show a preview of what *would* happen if the `--go` option was provided.

If the operations look correct, rerun the program with the `--go` argument:

    ❯ link-sync --config ~/printers.yml --source ~/master_farm_files/usb --destination /usb/ --execute

And the files will be copied across all printers at the same time.

Many of the arguments can be abbreviated. For example the above line could be:

    ❯ link-sync -c ~/printers.yml -s ~/master_farm_files/usb -d /usb/ -g

Note the short version of `--go` is `-g`.

You can use the built-in help function to see other options:

```
❯ link-sync --help
usage: link_sync [-h] [-c CONFIG_PATH] [-p [INCLUDED_PRINTERS ...]]
                 [-x [EXCLUDED_PRINTERS ...]] -s SOURCE_PATH
                 [-d DESTINATION_PATH] [-r RELATIVE_TO_PATH] [-g]
                 [--ignore-state]

options:
  -h, --help            show this help message and exit
  -c CONFIG_PATH, --config CONFIG_PATH
                        Path to a YAML or JSON file containing the
                        configuration of all printers. Default is
                        `printers.yml` in the current working directory.
  -p [INCLUDED_PRINTERS ...], --printer [INCLUDED_PRINTERS ...]
                        Explicitly name printers to INCLUDE for processing. By
                        default, all idle (see the `--ignore-state` option)
                        printers found in the will configuration be processed.
  -x [EXCLUDED_PRINTERS ...], --exclude [EXCLUDED_PRINTERS ...]
                        Explicitly name printers to EXCLUDE from processing.
                        By default, all idle (see the `--ignore-state option)
                        printers found in the configuration will be processed.
                        This option will be ignored if the `--printer` option
                        is used.
  -s SOURCE_PATH, --source SOURCE_PATH
                        The local path to the root of the files that should be
                        synced.
  -d DESTINATION_PATH, --destination DESTINATION_PATH
                        The relative path within the printers' storage where
                        the source files should be synchronized. Default is
                        the root of the printers' storage.
  -r RELATIVE_TO_PATH, --relative-to RELATIVE_TO_PATH
                        If provided, the SOURCE_PATH file paths will consider
                        only the portion of the path that is relative to this
                        given path. If not provided, it is set to the
                        SOURCE_PATH itself.
  -g, --go              Make the changes (do not do a dry-run).
  --ignore-state        If set, all printers, including busy printers, will be
                        processed. Use with caution as some printers may
                        experience print failures when printing and API calls
                        are received and processed.
```


Copyright (c) 2023, Martin Koistinen
