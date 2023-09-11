from http import HTTPStatus
from pathlib import Path
from typing import Generator, Sequence

from link_sync.apis import ApiResponse, PrusaLinkApi
from link_sync.printers import (
    MissingOrStaleFile,
    Printer,
    PrinterException,
    State,
)
from link_sync.storage import FileNode, Storage
from link_sync.utilities import gen_files_from_path
import pytest


DATA = Path(__file__).parent.joinpath('data')


@pytest.mark.parametrize(
    'config_path', (
        DATA.joinpath('printers.json'),
        DATA.joinpath('printers.yml'),
    ))
def test_from_config(mocker, config_path, root_node):
    """Ensure that `from_config()` works as expected."""
    mocker.patch.object(Printer, 'get_state', return_value='IDLE')
    mocker.patch.object(Storage, '_get_root_node', return_value=root_node)
    mocker.patch.object(Storage, '_build_storage', return_value=None)
    printers = Printer.from_config(config_path)
    assert len(printers) == 2
    assert isinstance(printers, Sequence)
    assert isinstance(printers[0], Printer)
    assert isinstance(printers[0].storage, Storage)


def test_from_config_dne(mocker):
    """Test when the file doesn't exist."""
    with pytest.raises(FileNotFoundError):
        Printer.from_config('non/existent.json')


def test_from_config_bad_extension(mocker):
    """Test when the file is not the right kind."""
    with pytest.raises(PrinterException):
        Printer.from_config(DATA.joinpath('printers.txt'))


def test_str(printers):
    """Test that str works as expected."""
    for printer in printers:
        assert str(printer) == f'Printer: "{printer.name}"'


def test_repr(printers):
    """Test that str works as expected."""
    for printer in printers:
        assert repr(printer) == f'<Printer: "{printer.name}">'


def test_get_status(mocker, printers, mock_status_response):
    """Test that the printers return status as expected."""
    mocker.patch('requests.Session.request', return_value=mock_status_response)
    for printer in printers:
        assert printer.get_state() == State['IDLE']


def test_get_status_not_found(mocker, root_node):
    """Test that the printers return status as expected."""
    mock_payload = mocker.Mock()
    mock_payload.json = mocker.Mock(return_value=None)
    mocker.patch.object(PrusaLinkApi, 'status_response',
                        return_value=ApiResponse(HTTPStatus.BAD_GATEWAY))
    mocker.patch.object(Storage, '_get_root_node', return_value=root_node)
    mocker.patch.object(Storage, '_build_storage', return_value=None)
    printer = Printer(name='fake', host='http:/127.0.0.1', username='un',
                      password='pw', printer_type='MK4')
    assert printer.get_state() is None


def test_full_short_path(storage, root_node, child_node):
    """Test that full_short_path works as expected."""
    assert storage.root_node.full_short_path == f'/{root_node.name}'
    root_node.child_nodes = {child_node, }
    children = list(storage.root_node.child_nodes)
    assert children
    child = children[0]
    assert child.full_short_path == f'/{root_node.name}/{child.name}'


def test_full_display_path(storage, root_node, child_node):
    """Test that full_display_path works as expected."""
    assert storage.root_node.full_display_path == f'/{root_node.display_name}'
    root_node.child_nodes = {child_node, }
    children = list(storage.root_node.child_nodes)
    assert children
    child = children[0]
    assert child.full_display_path == (
        f'/{root_node.display_name}/{child.display_name}')


def test_gen_missing_or_stale_files(printers):
    """Test that gen_missing_or_stale_files works as expected."""
    printer: Printer = printers[0]
    assert printer.storage.root_node
    local_file_path = DATA.joinpath('file_hierarchy')
    local_files = gen_files_from_path(local_file_path)
    files = printer.gen_missing_or_stale_files(
        local_files=local_files,
        relative_to_path=local_file_path,
        destination_path=Path('/usb/'),
    )
    assert isinstance(files, Generator)
    files = list(files)
    assert len(files) == 8
    assert isinstance(files[0], MissingOrStaleFile)


def test_get_excess_files(printers):
    """Test that get_excess_files works as intended."""
    printer: Printer = printers[0]
    assert printer.storage.root_node

    local_files_path = DATA.joinpath('file_hierarchy').joinpath('usb')
    assert local_files_path.exists()
    assert local_files_path.is_dir()

    # Create some (but not all) nodes that match the file_hierarchy.
    a_dir = FileNode(name='a', display_name='a', type="FOLDER", ro=False,
                     parent_node=printer.storage.root_node)
    a_gcode = FileNode(name='A~1.GCO', display_name='a.gcode', ro=False,
                       type="PRINT_FILE", parent_node=a_dir)
    a_dir.child_nodes.add(a_gcode)

    # Also, create some nodes that do NOT match the file_hierarchy.
    another_gcode = FileNode(name='ANOTHE~1.GCO', display_name='another.gcode',
                             ro=False, type="PRINT_FILE", parent_node=a_dir)
    a_dir.child_nodes.add(another_gcode)

    # "c/" does not exist in the file_hierarchy at all.
    c_dir = FileNode(name='c', type="FOLDER", ro=False,
                     parent_node=printer.storage.root_node)
    c_gcode = FileNode(name='A~1.GCO', display_name='a.gcode', ro=False,
                       type="PRINT_FILE", parent_node=c_dir)
    c_dir.child_nodes.add(c_gcode)
    canother_gcode = FileNode(name="CANOTH~1", display_name="canother.gcode",
                              ro=False, type="PRINT_FILE", parent_node=c_dir)
    c_dir.child_nodes.add(canother_gcode)

    # Attach these to the printer's storage file_hierarchy
    printer.storage.root_node.child_nodes.add(a_dir)
    printer.storage.root_node.child_nodes.add(c_dir)

    local_files = list(gen_files_from_path(local_files_path))
    excess_files = printer.get_excess_files(
        local_files=local_files,
        relative_to_path=local_files_path,
        destination_path=Path('/usb/')
    )

    assert isinstance(excess_files, set)
    assert len(excess_files) == 3
