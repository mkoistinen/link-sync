from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Generator

from link_sync.apis import ApiResponse, PrusaLinkApi
from link_sync.storage import FileNode, Storage, StorageException
import pytest


def test_file_node_str(root_node):
    """Test that str works as expected."""
    assert str(root_node) == 'File: "usb"'


def test_file_node_repr(root_node):
    """Test that repr works as expected."""
    assert repr(root_node) == '<File: "usb">'


def test_file_node_is_dir_yes(root_node):
    """Tests that is_dir returns True when expected."""
    assert root_node.is_dir is True


def test_file_node_is_dir_no(child_node):
    """Tests that is_dir returns False when expected."""
    assert child_node.is_dir is False


def test_file_node_m_datetime(child_node):
    """Test that m_datetime works as expected."""
    assert isinstance(child_node.m_datetime, datetime)


def test_file_node_m_datetime_for_none(child_node):
    """Test that m_datetime works as expected when m_timestamp is 0."""
    child_node.m_timestamp = 0
    assert child_node.m_datetime is None


def test_storage_str(storage):
    """Test that Storage.__str__ works as expected."""
    assert str(storage) == 'Storage: fake:usb'


def test_storage_str_without_root_node(storage):
    """Test that Storage.__str__ works as expected without root_node."""
    storage.root_node = None
    assert str(storage) == 'Storage: fake:UNDEFINED'


def test_storage_repr(storage):
    """Test that Storage.__repr__ works as expected."""
    assert repr(storage) == '<Storage: fake:usb>'


def test_get_root_node_ok(mocker, storage, mock_files_response):
    """Test that Storage._get_root_node works as expected."""
    mocker.patch('requests.Session.request', return_value=mock_files_response)
    root_node = storage._get_root_node()
    assert isinstance(storage._get_root_node(), FileNode)
    assert root_node


def test_get_root_node_not_ok(mocker):
    """Test that _get_root_node raises when expected."""
    mocker.patch.object(PrusaLinkApi, 'status_response',
                        return_value=ApiResponse(HTTPStatus.BAD_GATEWAY))
    with pytest.raises(StorageException) as e_info:
        Storage(name='fake', host='http://127.0.0.1', username='maker',
                password='fake_pw')
    assert "Could not get the root path for" in e_info.value.args[0]


def test_gen_nodes(storage, child_node):
    """Test that gen_nodes works as expected."""
    if child_node not in storage.root_node.child_nodes:
        storage.root_node.child_nodes.add(child_node)
    nodes = storage.gen_nodes()
    assert isinstance(nodes, Generator)
    nodes = list(nodes)
    assert len(nodes) == 2


def test_get_node_for_display_path(storage, child_node):
    """Test that get_node_for_path works as expected."""
    if child_node not in storage.root_node.child_nodes:
        storage.root_node.child_nodes.add(child_node)
    path_str = '/usb/Benchy.gcode'
    path = Path(path_str)

    # Ensure it works for string paths...
    node = storage.get_node_for_display_path(path_str)
    assert node == child_node

    # And for Path paths...
    node = storage.get_node_for_display_path(path)
    assert node == child_node

    # And for non-existent paths...
    node = storage.get_node_for_display_path('/usb/does_not_exist.zip')
    assert node is None


def test_get_shorter_path(storage):
    """Test that get_shorter_path works as expected."""
    dir_node = FileNode(
        display_name='long and complicated path',
        name='LONG~1',  # Simulated 8.3 short path
        m_timestamp=1690000000,
        parent_node=storage.root_node,
        ro=False,
        type="FOLDER",
    )
    dir_node2 = FileNode(
        display_name='another complicated path',
        name='ANOTHE~1',  # Simulated 8.3 short path
        m_timestamp=1690000000,
        parent_node=dir_node,
        ro=False,
        type="FOLDER",
    )
    # Ensure dir_node is part of the tree
    dir_node.child_nodes.add(dir_node2)
    storage.root_node.child_nodes.add(dir_node)

    # Test wuth string input
    path_str = '/usb/long and complicated path/another complicated path/NotBenchy.gcode'  # noqa
    shorter_path = storage.get_shorter_path(path_str)
    assert shorter_path == Path('/USB/LONG~1/ANOTHE~1/NotBenchy.gcode')

    # Test with path input
    full_path = Path(path_str)
    shorter_path = storage.get_shorter_path(full_path)
    assert shorter_path == Path('/USB/LONG~1/ANOTHE~1/NotBenchy.gcode')

    # Test with new directory and file
    shorter_path = storage.get_shorter_path('/usb/brand new path/new_benchy.gcode')  # noqa
    assert shorter_path == Path('/USB/brand new path/new_benchy.gcode')

    # Test with all new directory and file
    shorter_path = storage.get_shorter_path('/brand new path/new_benchy.gcode')  # noqa
    assert shorter_path == Path('/brand new path/new_benchy.gcode')
