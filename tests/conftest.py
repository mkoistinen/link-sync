from http import HTTPStatus
from pathlib import Path

from link_sync.apis import PrusaLinkApi
from link_sync.printers import Printer, State
from link_sync.storage import FileNode, Storage
import pytest


DATA = Path(__file__).parent.joinpath('data')


@pytest.fixture()
def root_node():
    """Prepare a child FileNode instance."""
    return FileNode(
        display_name='usb',
        name='USB',
        m_timestamp=0,
        parent_node=None,
        ro=False,
        type="FOLDER",
    )


@pytest.fixture()
def child_node(root_node):
    """Prepare a child FileNode instance."""
    child_node = FileNode(
        display_name='Benchy.gcode',
        name='BENCHY.GCO',
        m_timestamp=1690000000,
        parent_node=root_node,
        ro=False,
        type="PRINT_FILE",
    )
    root_node.child_nodes = [child_node, ]
    return child_node


@pytest.fixture()
def storage(mocker, root_node):
    """Prepare a Storage instance."""
    mocker.patch.object(Storage, '_get_root_node', return_value=root_node)
    mocker.patch.object(Storage, '_build_storage', return_value=None)
    storage = Storage(name='fake', host='http://127.0.0.1',
                      username='maker', password='fake_pw')
    return storage


@pytest.fixture()
def api():
    """Prepare a PrusaLinkApi instance."""
    return PrusaLinkApi(name="Fixture", host="http://0.0.0.0",
                        username="tester", password="test_pw")


@pytest.fixture()
def mock_status_response(mocker):
    """Prepare a mock status response instance."""
    response = mocker.Mock()
    response.json = mocker.Mock(return_value={
        "storage": {
            "path": "/usb/",
            "name": "usb",
            "read_only": False
        },
        "printer": {
            "state": "IDLE",
            "temp_bed": 25.1,
            "target_bed": 0,
            "temp_nozzle": 26.5,
            "target_nozzle": 0,
            "axis_z": 56,
            "axis_x": 241,
            "axis_y": 170,
            "flow": 100,
            "speed": 100,
            "fan_hotend": 0,
            "fan_print": 0
        }
    })
    return response


@pytest.fixture()
def mock_files_response(mocker):
    """Prepare a mock status response instance."""
    response = mocker.Mock()
    response.json = mocker.Mock(return_value={
        "type": "FOLDER",
        "ro": False,
        "name": "usb",
        "children": [
            {
                "name": "BENCHY.GCO",
                "ro": False,
                "type": "PRINT_FILE",
                "m_timestamp": 1693502066,
                "refs": {
                    "icon": "/thumb/s/usb/BENCHY.GCO",
                    "thumbnail": "/thumb/l/usb/BENCHY.GCO",
                    "download": "/usb/BENCHY.GCO"
                },
                "display_name": "benchy.gcode"
            },
            {
                "name": "OTHER",
                "ro": False,
                "type": "FOLDER",
                "m_timestamp": 1693516266,
                "display_name": "Other"
            }
        ]
    })
    return response


@pytest.fixture()
def mock_files_put_response(mocker):
    """Prepare a mock status response instance."""
    response = mocker.Mock()
    response.status_code = HTTPStatus.OK
    response.json = mocker.Mock(return_value={
        'key': 'value'
    })
    return response


@pytest.fixture()
def printers(mocker, root_node):
    """Prepare a list of printers with mocked-out Storage."""
    mocker.patch.object(Printer, 'get_state', return_value=State['IDLE'])
    mocker.patch.object(Storage, '_get_root_node', return_value=root_node)
    mocker.patch.object(Storage, '_build_storage', return_value=None)
    return Printer.from_config(DATA.joinpath('printers.yml'))
